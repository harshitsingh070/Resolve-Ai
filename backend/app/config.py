"""
config.py — Loads settings from backend/.env (gitignored).
Uses pydantic-settings so missing GROQ_API_KEY fails fast.
DATABASE_URL is SQLite file next to backend/ (see database.md).
"""
from pydantic_settings import BaseSettings, SettingsConfigDict
from pathlib import Path

# backend/.env is one level above app/  (backend/.env)
ENV_PATH = Path(__file__).resolve().parent.parent / ".env"


class Settings(BaseSettings):
    # Groq — required for Phase 6+, but DB/tests work without it
    GROQ_API_KEY: str = ""  # empty = not configured (allowed until Phase 6)
    GROQ_MODEL: str = "llama-3.1-8b-instant"

    # DB — SQLite file relative to backend/ ; absolute URL works on Windows too
    DATABASE_URL: str = "sqlite:///./resolveai.db"

    # Server
    HOST: str = "0.0.0.0"
    PORT: int = 8000

    model_config = SettingsConfigDict(
        env_file=str(ENV_PATH),
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()


def require_groq() -> None:
    """Call before any Groq request — fails with clear message if not set."""
    if not settings.GROQ_API_KEY or settings.GROQ_API_KEY == "your_groq_api_key_here":
        raise RuntimeError(
            "GROQ_API_KEY not configured. Set it in backend/.env (see .env.example). "
            "Get a key at https://console.groq.com/keys"
        )
