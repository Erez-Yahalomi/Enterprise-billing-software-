from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg://billing:billing@localhost:5432/billing"
    jwt_secret: str = "dev-secret-change-me"
    jwt_algorithm: str = "HS256"
    jwt_expires_minutes: int = 60 * 12

    kafka_bootstrap_servers: str = "localhost:9092"
    kafka_usage_topic: str = "usage.recorded"
    usage_pipeline: str = "sync"  # sync (default, tests/CI) | kafka (docker-compose demo)
    lake_path: str = "./data/lake"
    opa_url: str = "http://localhost:8181"
    opa_mode: str = "embedded"  # embedded (default, tests/CI) | http (docker-compose demo)

    ai_provider: str = "mock"  # gemini | ollama | mock
    gemini_api_key: str | None = None
    # Tried in order; free-tier quotas are per model, so a 429/404 on one moves to the next.
    gemini_models: str = "gemini-3.8-flash,gemini-3.7-flash,gemini-3.5-flash,gemini-3.1-flash-lite,gemini-3.5-flash-lite"

    @property
    def gemini_model(self) -> str:
        return self.gemini_models.split(",")[0].strip()

    @property
    def gemini_model_list(self) -> list[str]:
        return [m.strip() for m in self.gemini_models.split(",") if m.strip()]
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "llama3.2:1b"

    demo_random_seed: int = 42

    environment: str = "development"


@lru_cache
def get_settings() -> Settings:
    return Settings()
