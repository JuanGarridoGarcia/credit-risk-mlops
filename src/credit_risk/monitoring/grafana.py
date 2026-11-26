"""What the project needs from Grafana's side of the database and of the dashboards.

- The read-only role Grafana connects with (D-155) is created, with its grants, by a
  migration; its login and password come from the environment, so no password is ever
  in a migration. :func:`set_login` gives it both, once the migrations ran
  (``make migrate`` calls ``python -m credit_risk.monitoring.grafana``).
- The dashboards are the JSON files of ``grafana/dashboards`` (D-153). :func:`queries`
  takes out the SQL of every panel, so a test can run each one against the database
  (T32.2): a column renamed by a migration breaks CI, not the dashboard.
"""

import json
import logging
import re
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final

import psycopg
from psycopg import sql
from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

from credit_risk.settings import Settings

log = logging.getLogger(__name__)

#: The role Grafana reads with (D-155).
READER: Final = "grafana_reader"
#: Where the dashboards are provisioned from (D-153).
DASHBOARDS: Final = Path("grafana/dashboards")
#: Grafana macros a panel query may use, and what stands in for each when a test runs the
#: query: the dashboard's time range covers the whole simulation (D-152).
MACROS: Final[dict[str, str]] = {
    r"\$__timeFilter\((\w+(?:\.\w+)?)\)": r"\1 BETWEEN '2007-01-01' AND '2019-12-31'",
    r"\$__timeFrom\(\)": "'2007-01-01'::timestamptz",
    r"\$__timeTo\(\)": "'2019-12-31'::timestamptz",
}


class GrafanaSettings(BaseSettings):
    """The password of the read-only role, from ``GRAFANA_DB_PASSWORD``."""

    model_config = SettingsConfigDict(frozen=True, extra="ignore", env_prefix="GRAFANA_")

    db_password: SecretStr


def set_login(conn: psycopg.Connection[Any], password: SecretStr) -> None:
    """Let the read-only role log in with ``password`` (its grants come from migrations)."""
    conn.execute(
        sql.SQL("ALTER ROLE {} LOGIN PASSWORD {}").format(
            sql.Identifier(READER), sql.Literal(password.get_secret_value())
        )
    )


@dataclass(frozen=True)
class Query:
    """The SQL of one panel (one target) of a dashboard."""

    dashboard: str
    panel: str
    ref: str
    sql: str


def _panels(panels: list[dict[str, Any]]) -> Iterator[dict[str, Any]]:
    for panel in panels:
        yield panel
        yield from _panels(panel.get("panels", []))  # the panels inside a row


def queries(folder: Path = DASHBOARDS) -> list[Query]:
    """Every SQL query of every panel of every dashboard in ``folder``."""
    found = []
    for path in sorted(folder.glob("*.json")):
        dashboard = json.loads(path.read_text())
        for panel in _panels(dashboard.get("panels", [])):
            for target in panel.get("targets", []):
                text = target.get("rawSql")
                if text:
                    found.append(
                        Query(dashboard["uid"], panel.get("title", ""), target["refId"], text)
                    )
    return found


def runnable(text: str, variables: dict[str, str] | None = None) -> str:
    """The query with Grafana's macros and the dashboard's variables replaced."""
    for pattern, value in MACROS.items():
        text = re.sub(pattern, value, text)
    for name, value in (variables or {}).items():
        text = text.replace(f"${{{name}}}", value).replace(f"${name}", value)
    return text


def main() -> None:  # pragma: no cover - thin command line, run by make migrate
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    with psycopg.connect(Settings().postgres_conninfo(), autocommit=True) as conn:
        set_login(conn, GrafanaSettings().db_password)
    log.info("role %s can log in", READER)


if __name__ == "__main__":  # pragma: no cover
    main()
