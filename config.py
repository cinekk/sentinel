from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    anthropic_api_key: str = ""
    elevenlabs_api_key: str = ""
    ollama_base_url: str = "http://localhost:11434"
    database_url: str = "sqlite+aiosqlite:///./sentinel.db"
    usemaps_base_url: str = ""
    usemaps_login: str = ""
    usemaps_password: str = ""
    openrouter_api_key: str = ""
    openrouter_model: str = "qwen/qwen3-8b"


settings = Settings()
