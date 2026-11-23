"""B2: configuration is read from the environment and never exposes secrets."""

import pytest
from pydantic import ValidationError

from credit_risk.settings import Settings

# Obviously fake values, so that neither a person nor gitleaks mistakes them for real ones.
FAKE_PASSWORD = "fake-test-password-not-a-secret"
ENV = {
    "POSTGRES_HOST": "db.example.test",
    "POSTGRES_PORT": "6543",
    "POSTGRES_DB": "credit_risk_test",
    "POSTGRES_USER": "test_user",
    "POSTGRES_PASSWORD": FAKE_PASSWORD,
}


@pytest.fixture
def clean_env(monkeypatch: pytest.MonkeyPatch) -> pytest.MonkeyPatch:
    """Remove any POSTGRES_* variable of the machine so only the test decides."""
    for name in ENV:
        monkeypatch.delenv(name, raising=False)
    return monkeypatch


@pytest.fixture
def full_env(clean_env: pytest.MonkeyPatch) -> None:
    for name, value in ENV.items():
        clean_env.setenv(name, value)


# B2
@pytest.mark.usefixtures("full_env")
def test_settings_read_from_env() -> None:
    settings = Settings()

    assert settings.postgres_host == "db.example.test"
    assert settings.postgres_port == 6543
    assert settings.postgres_db == "credit_risk_test"
    assert settings.postgres_user == "test_user"
    assert settings.postgres_conninfo() == (
        "host=db.example.test port=6543 dbname=credit_risk_test "
        f"user=test_user password={FAKE_PASSWORD}"
    )


@pytest.mark.parametrize("missing", ["POSTGRES_DB", "POSTGRES_USER", "POSTGRES_PASSWORD"])
def test_settings_missing_variable_fails_clearly(
    full_env: None, monkeypatch: pytest.MonkeyPatch, missing: str
) -> None:
    monkeypatch.delenv(missing)

    with pytest.raises(ValidationError) as excinfo:
        Settings()

    assert missing.lower() in str(excinfo.value)


@pytest.mark.usefixtures("full_env")
def test_settings_never_expose_password() -> None:
    settings = Settings()

    assert FAKE_PASSWORD not in str(settings)
    assert FAKE_PASSWORD not in repr(settings)
    assert FAKE_PASSWORD not in settings.model_dump_json()
    assert settings.postgres_password.get_secret_value() == FAKE_PASSWORD
