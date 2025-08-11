from typing import Optional
from pydantic_settings import BaseSettings
from pydantic import validator


class Settings(BaseSettings):
    # Project
    PROJECT_NAME: str = "HWP to PDF API"
    VERSION: str = "0.1.0"
    API_V1_PREFIX: str = "/api/v1"
    
    # Server
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    
    # CORS
    BACKEND_CORS_ORIGINS: list[str] = ["*"]
    
    # File upload
    MAX_UPLOAD_SIZE: int = 10 * 1024 * 1024  # 10MB
    MAX_FILE_SIZE: int = 10 * 1024 * 1024  # 10MB (alias for compatibility)
    ALLOWED_EXTENSIONS: set[str] = {".hwp", ".hwpx"}
    
    # Storage
    UPLOAD_DIR: str = "uploads"
    OUTPUT_DIR: str = "outputs"
    
    # Processing
    PROCESS_TIMEOUT: int = 300  # 5 minutes
    
    # Database (Phase 2)
    DATABASE_URL: Optional[str] = None
    
    # Redis (Phase 2)
    REDIS_URL: Optional[str] = None
    
    # Logging
    LOG_LEVEL: str = "INFO"
    LOG_FORMAT: str = "json"  # json or plain
    
    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()

def get_settings():
    return settings