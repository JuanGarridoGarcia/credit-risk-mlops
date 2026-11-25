"""The simulated investor: each month it sends the listings to the API and buys (old step
4.2, D-098, D-123 to D-129).

It belongs to the simulated world, like the clock (D-043): in production the investor is
a client of the API, outside the system. ``advance`` runs it after publishing a month and
before the system's flow for that month (D-123), so a loan is decided by the champions
that existed when it was listed (trained up to the month before).

Each month after T0 (D-127) it:

1. reads the month's listings as the provider delivered them and sends them to
   ``/predict/batch`` in batches of 1,000 (D-117);
2. applies its rule (D-085): K is 10% of the loans listed the month before; among the
   loans the API says pass the buy threshold, it buys in listing order until K, one 25
   dollar note each;
3. reports the purchases to ``/purchases`` (D-124), each by an order number made of the
   month and the loan (D-129), so a repeat of the month buys nothing twice;
4. records the month in ``sim.invested``.

The API not answering (no connection, a 5xx answer) is retried, three times, after 10, 30
and 90 seconds, and then stops the clock (D-125); a listing the API refuses is not bought
and is counted. A month already in ``sim.invested`` is not sent again: when the clock
repeats a month because the system's flow failed, the investor already acted on it.
"""

import json
import logging
import math
import urllib.request
from datetime import date
from pathlib import Path
from typing import Any, Final
from urllib.error import HTTPError, URLError

import polars as pl
import psycopg
from prefect import task
from prefect.client.schemas.objects import State, TaskRun
from prefect.tasks import Task
from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

from credit_risk import business
from credit_risk.contracts import LISTINGS, delivery_path
from credit_risk.ingest import read_delivery
from credit_risk.settings import Settings

log = logging.getLogger(__name__)

#: Listings per request, the API's limit (D-117).
BATCH: Final = 1_000
#: One note per loan bought (D-085, D-128).
NOTE: Final = 25
#: Answers of the API that mean "not now" (D-125).
UNAVAILABLE: Final = frozenset({500, 502, 503, 504})
RETRIES: Final = 3
RETRY_DELAYS: Final = (10, 30, 90)
TIMEOUT_SECONDS: Final = 120


class ApiUnavailableError(Exception):
    """The API did not answer, or answered that it cannot now: worth trying again."""


class InvestorError(Exception):
    """Something trying again will not fix: no API configured, a purchase refused."""


class InvestorSettings(BaseSettings):
    """Where the API is and the investor's key (D-118)."""

    model_config = SettingsConfigDict(frozen=True, extra="ignore", env_prefix="API_")

    url: str = ""
    predict_key: SecretStr | None = None


def _post(settings: InvestorSettings, path: str, body: dict[str, Any]) -> dict[str, Any]:
    if not settings.url or settings.predict_key is None:
        raise InvestorError("API_URL and API_PREDICT_KEY are needed to send listings")
    request = urllib.request.Request(  # noqa: S310 - the URL is our own setting
        f"{settings.url.rstrip('/')}{path}",
        data=json.dumps(body, default=str).encode(),
        headers={
            "Content-Type": "application/json",
            "X-API-Key": settings.predict_key.get_secret_value(),
        },
        method="POST",
    )
    # The API is inside our network: never through a proxy of the environment.
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    try:
        with opener.open(request, timeout=TIMEOUT_SECONDS) as response:
            answer: dict[str, Any] = json.loads(response.read())
            return answer
    except HTTPError as error:
        if error.code in UNAVAILABLE:
            raise ApiUnavailableError(f"{path}: {error.code}") from error
        raise InvestorError(f"{path}: {error.code} {error.read()[:500]!r}") from error
    except (URLError, TimeoutError, ConnectionError) as error:
        raise ApiUnavailableError(f"{path}: {error!r}") from error


def k_of(month: date, listed_before: int) -> int:
    """K of ``month``: 10% of the loans listed the month before, rounded down (D-085)."""
    return business.caps({business.previous(month): listed_before}, [month])[month]


def choose(predictions: list[dict[str, Any]], month: date, k: int) -> list[dict[str, Any]]:
    """The predictions bought: those that pass the threshold, in listing order, up to K.

    The API already judged each loan against the buy rule of its answer (D-112); the
    investor keeps those that pass and applies its cap with :func:`business.buy`.
    """
    if not predictions:
        return []
    candidates = pl.DataFrame(
        {
            "id": [p["loan_id"] for p in predictions],
            "issue_d": [month] * len(predictions),
            "expected_return": [
                p["expected_return"] if (p.get("threshold") or {}).get("passes") else None
                for p in predictions
            ],
        },
        schema={"id": pl.Int64, "issue_d": pl.Date, "expected_return": pl.Float64},
    )
    bought = set(business.buy(candidates, -math.inf, {month: k})["id"].to_list())
    return sorted((p for p in predictions if p["loan_id"] in bought), key=lambda p: p["loan_id"])


def _done(month: date) -> bool:
    with psycopg.connect(Settings().postgres_conninfo()) as conn:
        row = conn.execute("SELECT 1 FROM sim.invested WHERE month = %s", (month,)).fetchone()
    return row is not None


def _record(month: date, summary: dict[str, Any]) -> None:
    with psycopg.connect(Settings().postgres_conninfo()) as conn:
        conn.execute(
            "INSERT INTO sim.invested (month, listings, scored, refused, k, bought)"
            " VALUES (%s, %s, %s, %s, %s, %s) ON CONFLICT (month) DO NOTHING",
            (month, summary["listings"], summary["scored"], summary["refused"],
             summary["k"], summary["bought"]),
        )  # fmt: skip


def invest(period: str, landing: str, start: str) -> dict[str, Any]:
    """Send the month ``period`` to the API and buy; ``start`` is T0 (D-127)."""
    month = date.fromisoformat(f"{period}-01")
    summary: dict[str, Any] = {"period": period, "invested": False}
    if month <= date.fromisoformat(f"{start}-01"):
        log.info("investor: %s is not after T0 %s, nothing sent", period, start)
        return summary
    if _done(month):
        log.info("investor: %s was already sent and bought", period)
        return {**summary, "earlier": True}
    settings = InvestorSettings()
    listings = read_delivery(delivery_path(Path(landing), month, LISTINGS), LISTINGS)
    before = read_delivery(
        delivery_path(Path(landing), business.previous(month), LISTINGS), LISTINGS
    )
    items = listings.to_dicts()
    predictions, refused = [], 0
    for first in range(0, len(items), BATCH):
        answer = _post(settings, "/predict/batch", {"loans": items[first : first + BATCH]})
        for result in answer["results"]:
            if "prediction" in result:
                predictions.append(result["prediction"])
            else:
                refused += 1
    k = k_of(month, before.height)
    bought = choose(predictions, month, k)
    orders = [
        {"order_id": f"{period}-{p['loan_id']}", "prediction_id": p["prediction_id"],
         "amount": NOTE}
        for p in bought
    ]  # fmt: skip
    for first in range(0, len(orders), BATCH):
        answer = _post(settings, "/purchases", {"purchases": orders[first : first + BATCH]})
        wrong = [r for r in answer["results"] if r["status"] == "refused"]
        if wrong:
            raise InvestorError(f"{len(wrong)} purchases refused, first: {wrong[0]}")
    summary.update(
        invested=True, listings=len(items), scored=len(predictions), refused=refused, k=k,
        bought=len(bought),
    )  # fmt: skip
    _record(month, summary)
    log.info("investor: %s", summary)
    return summary


def retry_unavailable(_task: Task[Any, Any], _run: TaskRun, state: State[Any]) -> bool:
    """Prefect's ``retry_condition_fn``: retry only when the API was not available."""
    error = state.data if isinstance(state.data, BaseException) else None
    if error is None:
        try:
            state.result(raise_on_failure=True)
        except BaseException as raised:  # noqa: BLE001 - classified right below
            error = raised
    retry = isinstance(error, ApiUnavailableError)
    log.info("investor failed %r: %s", error, "retrying" if retry else "stopping")
    return retry


RETRY: Final[dict[str, Any]] = {
    "retries": RETRIES,
    "retry_delay_seconds": list(RETRY_DELAYS),
    "retry_condition_fn": retry_unavailable,
}


@task(name="invest", **RETRY)
def invest_task(period: str, landing: str, start: str) -> dict[str, Any]:
    """The investor's month (D-123); see :func:`invest`."""
    return invest(period, landing, start)
