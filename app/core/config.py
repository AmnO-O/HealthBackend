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

    # Gemini Configuration (read securely via environment variables)
    # Support multiple keys separated by commas for rotation
    GEMINI_API_KEY: str = os.environ.get("GEMINI_API_KEY", "")
    GEMINI_MODEL_NAME: str = os.environ.get("GEMINI_MODEL_NAME", "gemini-3.5-flash-lite")

    @property
    def gemini_api_keys(self) -> List[str]:
        """Returns a list of cleaned API keys from the comma-separated string."""
        if not self.GEMINI_API_KEY:
            return []
        return [k.strip() for k in self.GEMINI_API_KEY.split(",") if k.strip()]

    # CORS Configuration
    BACKEND_CORS_ORIGINS: List[str] = ["*"]

    model_config = SettingsConfigDict(
        env_file=ENV_FILE,
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore"
    )

settings = Settings()
