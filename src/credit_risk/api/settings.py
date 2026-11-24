"""Configuration of the API, from environment variables (prefix ``API_``).

API keys (D-118) come as ``name:key`` pairs separated by commas, one list per
permission: ``API_KEYS_PREDICT`` for ``/predict`` and ``/predict/batch``,
``API_KEYS_ADMIN`` for ``/admin/reload``. Several keys may be valid at once, which is
how a key is rotated without stopping the service: add the new one, move the clients to
it, remove the old one. The name is what the logs and ``serving.requests`` record;
the key itself never leaves this module.
"""

import hmac
from typing import Final

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

#: A key shorter than this is refused at start-up: it could be guessed.
MIN_KEY_LENGTH: Final = 32


class KeysError(ValueError):
    """A list of API keys is malformed."""


def parse_keys(secret: SecretStr) -> dict[str, str]:
    """``name:key,name:key`` to {key: name}; refuses short keys, empty names, repeats."""
    keys: dict[str, str] = {}
    for item in secret.get_secret_value().split(","):
        if not item.strip():
            continue
        name, sep, key = item.strip().partition(":")
        if not sep or not name:
            raise KeysError("each API key must be written as name:key")
        if len(key) < MIN_KEY_LENGTH:
            raise KeysError(f"the API key of {name!r} is shorter than {MIN_KEY_LENGTH} characters")
        if key in keys:
            raise KeysError(f"the API key of {name!r} is repeated")
        keys[key] = name
    if not keys:
        raise KeysError("no API key configured")
    return keys


def client_of(given: str | None, keys: dict[str, str]) -> str | None:
    """The name of the client whose key is ``given``, or None.

    Every configured key is compared, in constant time, so the answer takes as long
    whether the key is right, nearly right or wrong.
    """
    found = None
    candidate = (given or "").encode()
    for key, name in keys.items():
        if hmac.compare_digest(candidate, key.encode()):
            found = name
    return found


class ApiSettings(BaseSettings):
    """Every field maps to ``API_<FIELD>``, e.g. ``API_RELOAD_SECONDS``."""

    model_config = SettingsConfigDict(frozen=True, extra="ignore", env_prefix="API_")

    keys_predict: SecretStr
    keys_admin: SecretStr
    #: How often the API asks MLflow whether a champion changed (D-111).
    reload_seconds: float = Field(default=60.0, gt=0)
    #: Put before the registered model names; tests use it to keep their models apart.
    model_prefix: str = ""
    #: Most loans in one batch (D-117).
    max_batch: int = Field(default=1_000, ge=1)
    #: Connections to Postgres kept open.
    pool_size: int = Field(default=10, ge=1)
