"""Runtime configuration, read from environment variables (Twelve-Factor style).

Nothing that changes between environments (laptop, docker compose, CI, AWS)
is written in the code. Secrets are typed as ``SecretStr`` so they never
appear in ``str()``, ``repr()`` or logs (test B2).
"""

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Connection settings for the project's Postgres database.

    Every field maps to an environment variable of the same name in upper
    case (``postgres_host`` -> ``POSTGRES_HOST``). Required fields have no
    default, so a missing variable fails at start-up with its name in the
    error message instead of failing later on the first query.
    """

    model_config = SettingsConfigDict(frozen=True, extra="ignore")

    postgres_host: str = "localhost"
    postgres_port: int = Field(default=5432, ge=1, le=65535)
    postgres_db: str
    postgres_user: str
    postgres_password: SecretStr

    def postgres_conninfo(self) -> str:
        """Return a libpq connection string, including the real password.

        The result contains the secret: pass it straight to the driver and
        never log it.
        """
        return (
            f"host={self.postgres_host} port={self.postgres_port} "
            f"dbname={self.postgres_db} user={self.postgres_user} "
            f"password={self.postgres_password.get_secret_value()}"
        )
