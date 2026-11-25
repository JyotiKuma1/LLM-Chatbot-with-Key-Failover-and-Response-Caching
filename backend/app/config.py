import os
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    llm_api_keys: str = ""
    llm_model: str = "gemini/gemini-3-flash-preview"
    llm_models: str = (
        "gemini/gemini-3-flash-preview,"
        "gemini/gemini-3.6-flash,"
        "gemini/gemini-3.1-flash-lite-preview"
    )
    llm_fallback_models: str = ""
    database_url: str = "sqlite:///./app.db"
    allowed_origins: str = "http://localhost:3000,http://localhost:5173"
    enable_failure_simulation: bool = True
    default_system_prompt: str = "You are a helpful assistant."
    llm_timeout_seconds: float = 30.0

    model_config = SettingsConfigDict(
        env_file=(".env", "../.env"),
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    @property
    def keys(self) -> list[str]:
        raw = os.getenv("LLM_API_KEYS", self.llm_api_keys)
        return [k.strip() for k in raw.split(",") if k.strip()]

    @property
    def origins(self) -> list[str]:
        raw = os.getenv("ALLOWED_ORIGINS", self.allowed_origins)
        return [o.strip() for o in raw.split(",") if o.strip()]

    @property
    def simulation_enabled(self) -> bool:
        env_val = os.getenv("ENABLE_FAILURE_SIMULATION")
        if env_val is not None:
            return env_val.strip().lower() == "true"
        return self.enable_failure_simulation

    @property
    def db_url(self) -> str:
        return os.getenv("DATABASE_URL", self.database_url)

    @property
    def model(self) -> str:
        return os.getenv("LLM_MODEL", self.llm_model)

    @property
    def models(self) -> list[str]:
        raw = os.getenv("LLM_MODELS", self.llm_models)
        items = [m.strip() for m in raw.split(",") if m.strip()]
        if self.model and self.model not in items:
            items.insert(0, self.model)
        return items

    @property
    def fallback_models(self) -> list[str]:
        raw = os.getenv("LLM_FALLBACK_MODELS", self.llm_fallback_models)
        return [m.strip() for m in raw.split(",") if m.strip() and m.strip() != self.model]

    @property
    def system_prompt(self) -> str:
        return os.getenv("DEFAULT_SYSTEM_PROMPT", self.default_system_prompt)

    @property
    def timeout_seconds(self) -> float:
        env_val = os.getenv("LLM_TIMEOUT_SECONDS")
        if env_val is not None:
            try:
                return float(env_val)
            except ValueError:
                pass
        return self.llm_timeout_seconds


def get_settings() -> Settings:
    return Settings()
