"""The FastAPI application (step 5.1, D-008, D-110 to D-121).

Endpoints:

- ``POST /predict``: one listing, as delivered by the provider (D-116), with its PD, LGD,
  expected loss, expected return, the buy threshold (D-112), four reasons (D-083) and the
  versions used;
- ``POST /predict/batch``: up to ``API_MAX_BATCH`` listings, one result per listing in
  the same order, each a prediction or its errors (D-117);
- ``POST /admin/reload``: load the champions now if an alias moved (D-111);
- ``GET /health``: whether the API can answer (champions loaded, database reachable);
  ``GET /health/live``: whether the process runs (Docker's healthcheck).

Prediction and admin endpoints need an API key in ``X-API-Key`` (D-118). Every request
to them leaves one row in ``serving.requests`` and every request a JSON line in the log
(D-115); predictions are written before they are answered (D-121).
"""

import json
import logging
import threading
import time
import uuid
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from typing import Annotated, Any, Final

import psycopg
from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, Response
from psycopg_pool import PoolTimeout
from pydantic import BaseModel, ConfigDict, Field, ValidationError, create_model

from credit_risk import __version__
from credit_risk.api.champions import Holder, NotReadyError, poll
from credit_risk.api.scoring import NOT_COVERED, Champions, cleaning_errors, frame_of, score
from credit_risk.api.settings import ApiSettings, client_of, parse_keys
from credit_risk.api.store import Answer, RequestRow, Saver
from credit_risk.contracts import LISTING_COLUMNS
from credit_risk.features import INPUTS

log = logging.getLogger(__name__)
access = logging.getLogger("credit_risk.api.access")

PREDICT: Final = "/predict"
BATCH: Final = "/predict/batch"
RELOAD: Final = "/admin/reload"
#: Endpoints whose every request is recorded in ``serving.requests`` (D-115).
RECORDED: Final = frozenset({PREDICT, BATCH, RELOAD})

# ---------------------------------------------------------------- input (D-116)


def _field(column: str) -> tuple[Any, Any]:
    if column == "id":
        return (str, ...)
    if column in INPUTS:
        return (str | None, ...)  # the key must be there; its value may be missing
    return (str | None, None)


#: One listing as the provider delivers it: every value as text, as in the monthly
#: delivery. The columns the model reads must be present (their value may be null); the
#: rest of the contract is optional; anything else is refused, so a change of the
#: provider's format shows up as an error instead of being ignored.
Listing: type[BaseModel] = create_model(  # type: ignore[call-overload]
    "Listing",
    __config__=ConfigDict(extra="forbid", strict=True),
    **{c: _field(c) for c in LISTING_COLUMNS},
)


class Batch(BaseModel):
    """Listings to score together; each is checked on its own (D-117)."""

    model_config = ConfigDict(extra="forbid")

    loans: list[dict[str, Any]] = Field(min_length=1)


def _pydantic_errors(error: ValidationError | RequestValidationError) -> list[dict[str, Any]]:
    out = []
    for e in error.errors():
        loc = [str(x) for x in e.get("loc", ()) if x != "body"]
        out.append({"column": loc[-1] if loc else None, "message": e["msg"], "type": e["type"]})
    return out


# ---------------------------------------------------------------- output


def _answer(a: Answer) -> dict[str, Any]:
    v = a.values
    covered = bool(v["covered"])
    return {
        "loan_id": v["loan_id"],
        "covered": covered,
        "note": None if covered else NOT_COVERED,
        "pd": v["pd"],
        "lgd": v["lgd"],
        "ead": v["ead"],
        "expected_loss": v["expected_loss"],
        "el_rate": v["el_rate"],
        "expected_return": v["expected_return"],
        "threshold": {
            "available": v["minimum"] is not None,
            "minimum": v["minimum"],
            "passes": v["passes"],
        }
        if covered
        else None,
        "reasons": v["reasons"] or [],
        "versions": {
            "pd": v["pd_version"],
            "lgd": v["lgd_version"],
            "buy_rule": v["rule_version"],
            "api": v["api_version"],
        },
        "stored_earlier": a.stored_earlier,
    }


# ---------------------------------------------------------------- the application


def _log_line(record: dict[str, Any]) -> None:
    access.info(json.dumps(record, default=str, separators=(",", ":")))


def create_app(
    settings: ApiSettings,
    holder: Holder,
    store: Saver,
    *,
    polling: bool = True,
) -> FastAPI:
    """The application, with its champions holder and its database store."""
    predict_keys = parse_keys(settings.keys_predict)
    admin_keys = parse_keys(settings.keys_admin)
    stop = threading.Event()

    @asynccontextmanager
    async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
        store.open()
        try:
            await run_in_threadpool(holder.refresh)
        except Exception as error:  # noqa: BLE001 - not ready; the poller keeps trying
            log.warning("champions not loaded at start: %r", error)
        thread = None
        if polling:
            thread = threading.Thread(
                target=poll, args=(holder, settings.reload_seconds, stop), daemon=True
            )
            thread.start()
        yield
        stop.set()
        if thread is not None:
            thread.join(timeout=5)
        store.close()

    app = FastAPI(
        title="Credit risk API",
        version=__version__,
        summary="PD, LGD, expected loss and buy threshold of Lending Club listings.",
        lifespan=lifespan,
    )

    # ------------------------------------------------------------ every request

    @app.middleware("http")
    async def record_every_request(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        request.state.request_id = uuid.uuid4()
        request.state.started = time.perf_counter()
        request.state.client = None
        request.state.saved = False
        request.state.row = None
        response = await call_next(request)
        latency = (time.perf_counter() - request.state.started) * 1000
        path = request.url.path
        row: RequestRow | None = request.state.row
        if path in RECORDED and not request.state.saved:
            row = row or RequestRow(request.state.request_id, path, __version__)
            row.status, row.latency_ms, row.client = (
                response.status_code,
                latency,
                (request.state.client),
            )
            await run_in_threadpool(store.record, row)
        versions = row.versions if row is not None else None
        _log_line(
            {
                "request_id": str(request.state.request_id),
                "method": request.method,
                "path": path,
                "status": response.status_code,
                "latency_ms": round(latency, 3),
                "client": request.state.client,
                "loans": row.loans if row is not None else None,
                "rejected": row.rejected if row is not None else None,
                "versions": versions,
            }
        )
        response.headers["X-Request-ID"] = str(request.state.request_id)
        return response

    @app.exception_handler(RequestValidationError)
    async def invalid(request: Request, error: RequestValidationError) -> JSONResponse:
        errors = _pydantic_errors(error)
        row = RequestRow(request.state.request_id, request.url.path, __version__)
        row.body, row.errors, row.rejected = error.body, errors, 1
        request.state.row = row
        return JSONResponse(
            {"request_id": str(request.state.request_id), "errors": errors}, status_code=422
        )

    # ------------------------------------------------------------ keys (D-118)

    def key(keys: dict[str, str], other: dict[str, str]) -> Callable[..., str]:
        def check(request: Request, x_api_key: Annotated[str | None, Header()] = None) -> str:
            client = client_of(x_api_key, keys)
            if client is None:
                if client_of(x_api_key, other) is not None:
                    request.state.client = client_of(x_api_key, other)
                    raise HTTPException(403, "this key may not use this endpoint")
                raise HTTPException(401, "a valid X-API-Key is needed")
            request.state.client = client
            return client

        return check

    predict_key = Depends(key(predict_keys, admin_keys))
    admin_key = Depends(key(admin_keys, predict_keys))

    # ------------------------------------------------------------ scoring

    def champions_or_503() -> Champions:
        try:
            return holder.current
        except NotReadyError as error:
            raise HTTPException(503, "no champion models loaded yet") from error

    def save(request: Request, row: RequestRow, scored: list[Any]) -> list[Answer]:
        row.latency_ms = (time.perf_counter() - request.state.started) * 1000
        row.client = request.state.client
        try:
            answers = store.save(row, scored)
        except (psycopg.OperationalError, PoolTimeout) as error:
            log.error("database unavailable: %r", error)
            raise HTTPException(503, "database unavailable: nothing was predicted") from error
        request.state.saved = True
        return answers

    @app.post(PREDICT, dependencies=[predict_key])
    def predict(listing: Listing, request: Request) -> Any:
        """Score one listing."""
        champions = champions_or_503()
        row = RequestRow(request.state.request_id, PREDICT, __version__, loans=1)
        row.versions = champions.versions()
        request.state.row = row
        item = listing.model_dump()
        raw = frame_of([item])
        typed, errors = cleaning_errors(raw)
        if errors[0]:
            row.loans, row.rejected, row.body, row.errors = 0, 1, item, errors[0]
            return JSONResponse(
                {"request_id": str(request.state.request_id), "errors": errors[0]},
                status_code=422,
            )
        answers = save(request, row, score(champions, typed, raw))
        return {"request_id": str(request.state.request_id), **_answer(answers[0])}

    @app.post(BATCH, dependencies=[predict_key])
    def predict_batch(batch: Batch, request: Request) -> Any:
        """Score up to ``API_MAX_BATCH`` listings; one result per listing, in order."""
        if len(batch.loans) > settings.max_batch:
            raise RequestValidationError(
                [
                    {
                        "loc": ("body", "loans"),
                        "msg": f"at most {settings.max_batch} loans per batch",
                        "type": "too_long",
                    }
                ],
                body={"loans": f"{len(batch.loans)} loans"},
            )
        champions = champions_or_503()
        row = RequestRow(request.state.request_id, BATCH, __version__)
        row.versions = champions.versions()
        request.state.row = row
        errors: dict[int, list[dict[str, Any]]] = {}
        valid: list[tuple[int, dict[str, Any]]] = []
        for i, item in enumerate(batch.loans):
            try:
                valid.append((i, Listing.model_validate(item).model_dump()))
            except ValidationError as error:
                errors[i] = _pydantic_errors(error)
        raw = frame_of([item for _, item in valid])
        typed, cleaning = cleaning_errors(raw)
        keep = []
        for (i, _), errs in zip(valid, cleaning, strict=True):
            if errs:
                errors[i] = errs
            else:
                keep.append(i)
        mask = [not errs for errs in cleaning]
        scored = score(champions, typed.filter(mask), raw.filter(mask)) if keep else []
        row.loans, row.rejected = len(keep), len(errors)
        if errors:
            row.body = {"items": {str(i): batch.loans[i] for i in sorted(errors)}}
            row.errors = {str(i): errors[i] for i in sorted(errors)}
        answers = dict(zip(keep, save(request, row, scored), strict=True))
        results = [
            {"index": i, "prediction": _answer(answers[i])}
            if i in answers
            else {"index": i, "errors": errors[i]}
            for i in range(len(batch.loans))
        ]
        return {"request_id": str(request.state.request_id), "results": results}

    # ------------------------------------------------------------ operations

    @app.post(RELOAD, dependencies=[admin_key])
    def reload(request: Request) -> Any:
        """Load the champions now if an alias moved (D-111)."""
        try:
            changed = holder.refresh()
        except Exception as error:  # noqa: BLE001 - reported to the caller
            kept = holder.current.versions() if holder.ready else None
            return JSONResponse(
                {"changed": False, "error": repr(error), "versions": kept}, status_code=503
            )
        versions = holder.current.versions()
        row = RequestRow(request.state.request_id, RELOAD, __version__)
        row.versions = versions
        request.state.row = row
        return {"changed": changed, "versions": versions}

    @app.get("/health/live")
    def live() -> Any:
        """200 while the process runs: Docker's healthcheck (liveness, not readiness)."""
        return {"status": "alive", "api_version": __version__}

    @app.get("/health")
    def health() -> Any:
        """200 when the champions are loaded and the database answers, else 503."""
        database = store.alive()
        body = {
            "status": "ok" if holder.ready and database else "unavailable",
            "models": holder.current.versions() if holder.ready else None,
            "loaded_at": holder.loaded_at.isoformat() if holder.loaded_at else None,
            "database": database,
            "api_version": __version__,
        }
        return JSONResponse(body, status_code=200 if body["status"] == "ok" else 503)

    return app
