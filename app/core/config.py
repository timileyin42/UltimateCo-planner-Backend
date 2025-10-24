from typing import List, Optional, Union
from pydantic import field_validator
from pydantic_settings import BaseSettings
import os

class Settings(BaseSettings):
    # API Configuration
    API_V1_STR: str
    PROJECT_NAME: str
    
    # CORS Configuration
    BACKEND_CORS_ORIGINS: Union[List[str], str] = []
    
    @field_validator("BACKEND_CORS_ORIGINS", mode="before")
    @classmethod
    def assemble_cors_origins(cls, v):
        if isinstance(v, str) and v:
            if not v.startswith("["):
                return [i.strip() for i in v.split(",")]
            else:
                import json
                return json.loads(v)
        elif isinstance(v, list):
            return v
        return []
    
    # Database Configuration
    DATABASE_URL: str
    ASYNC_DATABASE_URL: str
    
    # Read Replica Configuration
    READ_REPLICA_URLS: List[str] = []
    
    @field_validator("READ_REPLICA_URLS", mode="before")
    @classmethod
    def assemble_read_replicas(cls, v):
        if isinstance(v, str) and v:
            if not v.startswith("["):
                return [i.strip() for i in v.split(",")]
            else:
                import json
                return json.loads(v)
        elif isinstance(v, list):
            return v
        return []
    
    # Database Performance Settings
    DB_CONNECTION_POOL_SIZE: int = 20
    DB_MAX_OVERFLOW: int = 40
    DB_POOL_TIMEOUT: int = 30
    DB_POOL_RECYCLE: int = 3600  # 1 hour
    DB_SLOW_QUERY_THRESHOLD_MS: int = 500  # Log queries taking longer than this
    
    # Security Configuration
    SECRET_KEY: str 
    ALGORITHM: str
    ACCESS_TOKEN_EXPIRE_MINUTES: int
    REFRESH_TOKEN_EXPIRE_DAYS: int
    
    # Rate Limiting Configuration
    REDIS_URL: str
    RATE_LIMIT_ENABLED: bool
    
    # Celery Configuration
    CELERY_BROKER_URL: str
    CELERY_RESULT_BACKEND: str
    
    # Default rate limits (requests per minute)
    RATE_LIMIT_AUTH: str
    RATE_LIMIT_API: str
    RATE_LIMIT_AI: str
    RATE_LIMIT_PAYMENTS: str
    RATE_LIMIT_UPLOADS: str
    
    # Circuit Breaker Configuration
    CIRCUIT_BREAKER_ENABLED: bool
    CIRCUIT_BREAKER_FAILURE_THRESHOLD: int
    CIRCUIT_BREAKER_RECOVERY_TIMEOUT: int
    CIRCUIT_BREAKER_EXPECTED_EXCEPTION: tuple = (Exception,)
    
    # Email Configuration (Resend)
    RESEND_API_KEY: Optional[str] = None
    EMAILS_FROM_EMAIL: str
    EMAILS_FROM_NAME: str
    SUPPORT_EMAIL: str
    
    # Frontend URL for email links
    FRONTEND_URL: str
    
    
    # File Upload Configuration
    UPLOAD_FOLDER: str
    MAX_FILE_SIZE: int
    ALLOWED_EXTENSIONS: Union[List[str], str] = []
    
    @field_validator("ALLOWED_EXTENSIONS", mode="before")
    @classmethod
    def assemble_allowed_extensions(cls, v):
        if isinstance(v, str) and v:
            if not v.startswith("["):
                return [i.strip() for i in v.split(",")]
            else:
                import json
                return json.loads(v)
        elif isinstance(v, list):
            return v
        return []
    
    # External API Keys
    OPENAI_API_KEY: Optional[str] = None
    GOOGLE_MAPS_API_KEY: Optional[str] = None
    
    # SMS Configuration - Termii
    TERMII_API_KEY: Optional[str] = None
    TERMII_SENDER_ID: Optional[str] = None
    TERMII_BASE_URL: str
    
    # Push Notifications - Firebase Cloud Messaging
    FIREBASE_CREDENTIALS_PATH: Optional[str] = None
    FIREBASE_CREDENTIALS_JSON: Optional[str] = None
    
    # File Storage - GCP Storage
    GCP_PROJECT_ID: Optional[str] = None
    GCP_STORAGE_BUCKET: Optional[str] = None
    GCP_STORAGE_REGION: str
    GOOGLE_APPLICATION_CREDENTIALS: Optional[str] = None
    
    # Google OAuth Configuration
    GOOGLE_CLIENT_ID: Optional[str] = None
    GOOGLE_CLIENT_SECRET: Optional[str] = None
    
    # Calendar Integration Configuration
    # Google Calendar
    GOOGLE_CALENDAR_SCOPES: Union[List[str], str] = []
    GOOGLE_CALENDAR_REDIRECT_URI: Optional[str] = None
    
    # Apple Calendar (CalDAV)
    APPLE_CALENDAR_SERVER_URL: Optional[str] = None
    APPLE_CALENDAR_PRINCIPAL_URL: Optional[str] = None
    
    @field_validator("GOOGLE_CALENDAR_SCOPES", mode="before")
    @classmethod
    def assemble_google_calendar_scopes(cls, v):
        if isinstance(v, str) and v:
            return [scope.strip() for scope in v.split(",")]
        elif isinstance(v, list):
            return v
        return []
    
    # Calendar Sync Configuration
    CALENDAR_SYNC_FREQUENCY_MINUTES: int
    CALENDAR_SYNC_MAX_RETRIES: int
    CALENDAR_WEBHOOK_BASE_URL: Optional[str] = None
    
    # Stripe Configuration
    STRIPE_SECRET_KEY: Optional[str] = None
    STRIPE_PUBLISHABLE_KEY: Optional[str] = None
    STRIPE_WEBHOOK_SECRET: Optional[str] = None
    STRIPE_PRICE_ID_PRO_MONTHLY: Optional[str] = None
    STRIPE_PRICE_ID_PRO_YEARLY: Optional[str] = None
    
    # Environment
    ENVIRONMENT: str
    DEBUG: bool
    
    model_config = {
        "env_file": ".env",
        "case_sensitive": True,
        "env_file_encoding": "utf-8",
        "str_strip_whitespace": True,
        "extra": "ignore",
    }

settings = Settings()

def get_settings() -> Settings:
    """Get application settings instance"""
    return settings