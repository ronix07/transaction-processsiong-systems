from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql://txnuser:txnpass@postgres:5432/txndb"
    redis_url: str = "redis://redis:6379/0"
    gemini_api_key: str = ""


settings = Settings()
