"""Configuration management using environment variables."""
from pydantic_settings import BaseSettings
from typing import Optional
import os


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    # Database settings
    DB_HOST: str = "localhost"
    DB_PORT: int = 5432
    DB_NAME: str = "rfm_db"
    DB_USER: str = "rfm_user"
    DB_PASSWORD: str = "rfm_password"
    
    # RFM & Clustering settings
    RFM_WINDOW_DAYS: int = 365
    DEFAULT_K: int = 5
    
    # Data ingestion settings
    DATA_DIR: str = "./data/input"
    
    # API settings
    API_HOST: str = "0.0.0.0"
    API_PORT: int = 8000
    
    @property
    def database_url(self) -> str:
        """Construct PostgreSQL database URL."""
        return f"postgresql://{self.DB_USER}:{self.DB_PASSWORD}@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"
    
    class Config:
        env_file = ".env"
        case_sensitive = True


# Global settings instance
settings = Settings()

