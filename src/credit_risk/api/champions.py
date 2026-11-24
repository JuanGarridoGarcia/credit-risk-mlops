"""Which models the API serves, and how it learns of new champions (D-110, D-111).

The API loads the champions from the MLflow registry by their alias (D-110): the PD, the
LGD and the buy rule. It learns of a new champion in two ways (D-111): the monthly flow
calls ``/admin/reload`` right after a promotion, and every ``API_RELOAD_SECONDS`` a
thread asks the registry whether an alias moved, in case that call never arrived.

Replacing is atomic: the three are loaded first and then swapped in one assignment, and
a request takes the current set once, so no request ever mixes versions. A load that
fails leaves the set in use untouched and records a ``model_load_failed`` alert (once
while the same failure repeats).
"""

import logging
import threading
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Protocol

from credit_risk import alerts, registry
from credit_risk.api.scoring import Champions
from credit_risk.buy_rule import NAME as RULE
from credit_risk.buy_rule import BuyRule
from credit_risk.model import LGDModel, PDModel

log = logging.getLogger(__name__)

Versions = tuple[str | None, str | None, str | None]


class NotReadyError(RuntimeError):
    """No champions are loaded yet."""


class Source(Protocol):
    """Where champions come from: the MLflow registry, or a dictionary in tests."""

    def versions(self) -> Versions: ...

    def load(self, kind: str, version: str) -> Any: ...


@dataclass(frozen=True)
class Registry:
    """How the holder reaches the registry; tests replace it with a dictionary."""

    prefix: str = ""

    def versions(self) -> Versions:
        """Versions the aliases point to now: PD, LGD, buy rule."""
        return (
            registry.champion(f"{self.prefix}pd"),
            registry.champion(f"{self.prefix}lgd"),
            registry.champion(f"{self.prefix}{RULE}"),
        )

    def load(self, kind: str, version: str) -> Any:
        name = f"{self.prefix}{RULE}" if kind == "buy_rule" else f"{self.prefix}{kind}"
        return registry.load(name, version)


class Holder:
    """The champions in use; :meth:`refresh` replaces them when an alias moved."""

    def __init__(
        self, source: Source, alert: Callable[[alerts.Alert], Any] = alerts.record
    ) -> None:
        self.source = source
        self.alert = alert
        self._current: Champions | None = None
        self._loaded_at: datetime | None = None
        self._lock = threading.Lock()  # one refresh at a time; reading needs no lock
        # The last failure alerted: the same failure repeating every poll alerts once.
        self._last_failure: tuple[Versions, str] | None = None

    @property
    def current(self) -> Champions:
        champions = self._current
        if champions is None:
            raise NotReadyError("no champion models loaded yet")
        return champions

    @property
    def ready(self) -> bool:
        return self._current is not None

    @property
    def loaded_at(self) -> datetime | None:
        return self._loaded_at

    def _same(self, versions: Versions) -> bool:
        c = self._current
        return c is not None and (c.pd_version, c.lgd_version, c.rule_version) == versions

    def refresh(self) -> bool:
        """Load the champions if any alias moved; return whether the set was replaced.

        Raises when the registry cannot be read or a model cannot be loaded; the set in
        use, if any, stays as it was and an alert is recorded.
        """
        with self._lock:
            versions: Versions = (None, None, None)
            try:
                versions = self.source.versions()
                if self._same(versions):
                    return False
                pd_version, lgd_version, rule_version = versions
                if pd_version is None or lgd_version is None:
                    raise NotReadyError(f"no champion: pd {pd_version}, lgd {lgd_version}")
                pd_model = self.source.load("pd", pd_version)
                lgd_model = self.source.load("lgd", lgd_version)
                rule = self.source.load("buy_rule", rule_version) if rule_version else None
                if not isinstance(pd_model, PDModel) or not isinstance(lgd_model, LGDModel):
                    raise TypeError("the registry returned something that is not a model")
                if rule is not None and not isinstance(rule, BuyRule):
                    raise TypeError("the registry returned something that is not a buy rule")
            except Exception as error:
                self._failed(versions, error)
                raise
            previous = self._current
            # One assignment: a request sees either the old set or the new one.
            self._current = Champions(
                pd_model, lgd_model, pd_version, lgd_version, rule, rule_version
            )
            self._loaded_at = datetime.now(UTC)
            self._last_failure = None
            log.warning(
                "champions loaded: pd %s, lgd %s, buy rule %s (before: %s)",
                pd_version, lgd_version, rule_version,
                previous.versions() if previous else "none",
            )  # fmt: skip
            return True

    def _failed(self, versions: Versions, error: Exception) -> None:
        log.error("could not load the champions %s: %r", versions, error)
        key = (versions, type(error).__name__)
        if key == self._last_failure:
            return
        self._last_failure = key
        kept = self._current.versions() if self._current else None
        try:
            self.alert(
                alerts.Alert(
                    "model_load_failed",
                    f"the API could not load the champions {versions}: {error!r}; "
                    f"kept {kept or 'nothing'}",
                    model="api",
                    details={"wanted": list(versions), "kept": kept, "error": repr(error)},
                )
            )
        except Exception:
            log.exception("could not record the model_load_failed alert")


def poll(holder: Holder, seconds: float, stop: threading.Event) -> None:
    """Refresh every ``seconds`` until ``stop``; while nothing is loaded, every 5 s at most.

    Failures are logged (and alerted by the holder) and never stop the loop.
    """
    while True:
        wait = seconds if holder.ready else min(seconds, 5.0)
        if stop.wait(wait):
            return
        try:
            holder.refresh()
        except Exception as error:  # noqa: BLE001 - the loop must survive anything
            log.warning("polling the registry failed: %r", error)
