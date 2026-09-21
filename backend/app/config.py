import os
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """
    Application settings. All values can be overridden via environment
    variables (see docker-compose.yml / .env.example).
    """

    APP_NAME: str = "RMFT Performance & Pipeline Dashboard"

    # Postgres connection. Defaults match docker-compose.yml service names.
    DATABASE_URL: str = os.environ.get(
        "DATABASE_URL",
        "postgresql+psycopg2://rmft:rmft_password@localhost:5432/rmft_dashboard",
    )

    JWT_SECRET: str = os.environ.get("JWT_SECRET", "CHANGE_ME_IN_PRODUCTION")
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 12  # 12 hours, mobile-friendly

    # Outflow alert thresholds (IDR) — section 29
    OUTFLOW_HIGH_THRESHOLD: int = 500_000_000
    OUTFLOW_MEDIUM_THRESHOLD: int = 100_000_000

    CORS_ORIGINS: list[str] = ["*"]

    class Config:
        env_file = ".env"


settings = Settings()
