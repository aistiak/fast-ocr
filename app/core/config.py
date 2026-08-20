from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "fast-ocr"
    app_env: str = "development"
    host: str = "0.0.0.0"
    port: int = 8000

    google_cloud_project: str | None = None
    google_application_credentials: str | None = None


settings = Settings()
