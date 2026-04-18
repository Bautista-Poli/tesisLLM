from pydantic_settings import BaseSettings
from typing import List

class Settings(BaseSettings):
    APP_NAME: str = "Chatbot Turnos Médicos"
    DEBUG: bool = False
    ALLOWED_ORIGINS: List[str] = ["*"]
    DATABASE_URL: str = "sqlite+aiosqlite:///./turnos.db"
    WHATSAPP_TOKEN: str = "PLACEHOLDER_TOKEN"
    WHATSAPP_PHONE_NUMBER_ID: str = "PLACEHOLDER_PHONE_ID"
    WHATSAPP_VERIFY_TOKEN: str = "mi_verify_token_secreto"
    OCR_ENABLED: bool = False
    OCR_SERVICE_URL: str = ""
    OCR_API_KEY: str = ""
    NLU_MODE: str = "mock"
    NLU_SERVICE_URL: str = ""

    class Config:
        env_file = ".env"
        case_sensitive = True

settings = Settings()
