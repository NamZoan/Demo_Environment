from pydantic import BaseModel
import os


class Settings(BaseModel):
    database_url: str = os.getenv(
        "DATABASE_URL",
        "postgresql://monitor:monitor@localhost:5432/environment",
    )
    cors_origins: list[str] = os.getenv("CORS_ORIGINS", "*").split(",")
    ftp_host: str = os.getenv("FTP_HOST", "127.0.0.1")
    ftp_port: int = int(os.getenv("FTP_PORT", "21"))
    ftp_user: str = os.getenv("FTP_USER", "station")
    ftp_password: str = os.getenv("FTP_PASSWORD", "stationpass")
    ftp_timeout_seconds: int = int(os.getenv("FTP_TIMEOUT_SECONDS", "5"))
    ftp_credentials_key: str = os.getenv("FTP_CREDENTIALS_KEY", "development-only-change-me")


settings = Settings()
