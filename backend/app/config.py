from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BACKEND_DIR / "data"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(BACKEND_DIR.parent / ".env", BACKEND_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    mock_mode: bool = True

    azure_openai_endpoint: str = ""
    azure_openai_api_key: str = ""
    azure_openai_deployment: str = "gpt-4o"
    azure_openai_api_version: str = "2024-10-21"

    azure_speech_key: str = ""
    azure_speech_region: str = "eastus"

    azure_maps_key: str = ""

    # Local Whisper STT used when Azure Speech is not configured. Disable to
    # fall back to the deterministic mock transcriber (used in tests).
    local_stt: bool = True
    whisper_model: str = "base.en"

    memory_db_path: str = str(DATA_DIR / "memory.sqlite")


@lru_cache
def get_settings() -> Settings:
    return Settings()
