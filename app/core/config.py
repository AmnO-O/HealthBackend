import os
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import List

# Get the directory where config.py is located, then go up to the backend root
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
ENV_FILE = os.path.join(BASE_DIR, ".env")

class Settings(BaseSettings):
    PROJECT_NAME: str = "Vitalis Health AI Security Proxy"
    VERSION: str = "1.0.0"
    API_V1_STR: str = "/api/v1"

    # Gemini Configuration (read securely via environment variables for Render / Cloud Run)
    GEMINI_API_KEY: str = os.environ.get("GEMINI_API_KEY", "")
    GEMINI_MODEL_NAME: str = os.environ.get("GEMINI_MODEL_NAME", "gemini-2.5-flash")

    # CORS Configuration
    BACKEND_CORS_ORIGINS: List[str] = ["*"]

    model_config = SettingsConfigDict(
        env_file=ENV_FILE,
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore"
    )

settings = Settings()
