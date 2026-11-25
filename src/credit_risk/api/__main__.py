"""``python -m credit_risk.api``: serve the API with uvicorn on port 8000.

One process per container: ``/admin/reload`` must reach the process that serves, so the
API scales by running more containers, never more workers in one (D-111).
"""

import argparse
import logging
import sys

import uvicorn

from credit_risk.api.app import create_app
from credit_risk.api.champions import Holder, Registry
from credit_risk.api.settings import ApiSettings
from credit_risk.api.store import Store
from credit_risk.settings import Settings

PORT = 8000


def main(argv: list[str] | None = None) -> None:  # pragma: no cover - a server; T18.13, T18.14
    parser = argparse.ArgumentParser(description="Serve the prediction API (step 5.1).")
    parser.add_argument("--port", type=int, default=PORT)
    args = parser.parse_args(argv)
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter("%(message)s"))
    access = logging.getLogger("credit_risk.api.access")
    access.addHandler(handler)
    access.propagate = False
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    settings = ApiSettings()
    app = create_app(
        settings,
        Holder(Registry(settings.model_prefix)),
        Store(Settings().postgres_conninfo(), settings.pool_size),
    )
    uvicorn.run(app, host="0.0.0.0", port=args.port, access_log=False, log_config=None)  # noqa: S104


if __name__ == "__main__":
    main()
