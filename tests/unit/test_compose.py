"""T22.6: the admin key of the API in compose, read from ``docker-compose.yml`` (E-056).

After a promotion, the monthly flow tells the API to load the new champions with the
admin key (D-111). The flow runs in two services, the worker and the clock: each needs
the key, and no other service may have it (keys per permission, D-118). The tests of the
flow and of the clock set the key in their own process, so only this check reads compose.
"""

from pathlib import Path
from typing import Any, Final

import yaml

COMPOSE: Final = Path(__file__).parents[2] / "docker-compose.yml"
TRAIN: Final = "${TRAIN_IMAGE:-credit-risk:train}"
#: The commands of the services that run the monthly flow, and so promote champions.
RUN_THE_FLOW: Final = {
    "worker": ["python", "-m", "credit_risk.flows", "serve"],
    "clock": ["python", "-m", "credit_risk.simulator.clock", "serve"],
}
#: Services of the train image that never run the monthly flow.
DO_NOT_RUN_IT: Final = {"mlflow", "prefect"}


def _services() -> dict[str, dict[str, Any]]:
    services: dict[str, dict[str, Any]] = yaml.safe_load(COMPOSE.read_text())["services"]
    return services


# T22.6
def test_every_service_of_the_train_image_is_classified() -> None:
    train = {name for name, service in _services().items() if service.get("image") == TRAIN}
    assert train == set(RUN_THE_FLOW) | DO_NOT_RUN_IT, (
        "a service of the train image was added or removed: decide whether it runs the "
        "monthly flow, and put it in RUN_THE_FLOW or DO_NOT_RUN_IT"
    )


def test_the_services_that_run_the_flow_can_tell_the_api_to_reload() -> None:
    services = _services()
    for name, command in RUN_THE_FLOW.items():
        assert services[name]["command"] == command, f"{name} no longer runs {command}"
        environment = services[name]["environment"]
        assert environment.get("API_URL") == "http://api:8000", name
        assert environment.get("API_ADMIN_KEY") == "${API_ADMIN_KEY:?set API_ADMIN_KEY in .env}", (
            f"{name} runs the monthly flow but cannot tell the API to reload (E-056)"
        )


def test_no_other_service_has_the_admin_key() -> None:
    for name, service in _services().items():
        if name not in RUN_THE_FLOW:
            assert "API_ADMIN_KEY" not in service.get("environment", {}), (
                f"{name} does not run the monthly flow and must not have the admin key (D-118)"
            )
