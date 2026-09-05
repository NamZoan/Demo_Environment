from pydantic import BaseModel
import os


class Settings(BaseModel):
    database_url: str = os.getenv(
        "DATABASE_URL",
        "postgresql://monitor:monitor@localhost:5432/environment",
    )
    cors_origins: list[str] = os.getenv("CORS_ORIGINS", "*").split(",")


settings = Settings()

