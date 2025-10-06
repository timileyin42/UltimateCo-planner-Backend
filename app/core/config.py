from typing import List, Optional
from pydantic import validator
from pydantic_settings import BaseSettings
import os

class Settings(BaseSettings):
    # API Configuration
    API_V1_STR: str = "/api/v1"
    PROJECT_NAME: str = "Plan et al - Ultimate Co-planner"
    
    # CORS Configuration
    BACKEND_CORS_ORIGINS: List[str] = []
    
    @validator("BACKEND_CORS_ORIGINS", pre=True)
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
    DATABASE_URL: Optional[str] = None
    ASYNC_DATABASE_URL: Optional[str] = None
    
    # Security Configuration
    SECRET_KEY: str 
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    
    # Rate Limiting Configuration
    REDIS_URL: Optional[str] = "redis://localhost:6379"
    RATE_LIMIT_ENABLED: bool = True
    
    # Default rate limits (requests per minute)
    RATE_LIMIT_AUTH: str = "5/minute"  # Login, register, password reset
    RATE_LIMIT_API: str = "100/minute"  # General API endpoints
    RATE_LIMIT_AI: str = "10/minute"  # AI chat endpoints
    RATE_LIMIT_PAYMENTS: str = "20/minute"  # Payment endpoints
    RATE_LIMIT_UPLOADS: str = "30/minute"  # File upload endpoints
    
    # Circuit Breaker Configuration
    CIRCUIT_BREAKER_ENABLED: bool = True
    CIRCUIT_BREAKER_FAILURE_THRESHOLD: int = 5
    CIRCUIT_BREAKER_RECOVERY_TIMEOUT: int = 60  # seconds
    CIRCUIT_BREAKER_EXPECTED_EXCEPTION: tuple = (Exception,)
    
    # Email Configuration (Resend)
    RESEND_API_KEY: Optional[str] = None
    EMAILS_FROM_EMAIL: Optional[str] = "noreply@planetal.com"
    EMAILS_FROM_NAME: Optional[str] = "Plan et al"
    SUPPORT_EMAIL: Optional[str] = "support@planetal.com"
    
    # Frontend URL for email links
    FRONTEND_URL: Optional[str] = None
    
    
    # File Upload Configuration
    UPLOAD_FOLDER: str = "uploads"
    MAX_FILE_SIZE: int = 10 * 1024 * 1024  # 10MB
    ALLOWED_EXTENSIONS: List[str] = ["jpg", "jpeg", "png", "gif", "pdf", "doc", "docx"]
    
    # External API Keys
    OPENAI_API_KEY: Optional[str] = None
    GOOGLE_MAPS_API_KEY: Optional[str] = None
    
    # SMS Configuration - Termii
    TERMII_API_KEY: Optional[str] = None
    TERMII_SENDER_ID: Optional[str] = None
    TERMII_BASE_URL: Optional[str] = "https://api.ng.termii.com/api"
    
    # Push Notifications - Firebase Cloud Messaging
    FIREBASE_CREDENTIALS_PATH: Optional[str] = None
    FIREBASE_CREDENTIALS_JSON: Optional[str] = None
    
    # File Storage - GCP Storage
    GCP_PROJECT_ID: Optional[str] = None
    GCP_STORAGE_BUCKET: Optional[str] = None
    GCP_STORAGE_REGION: str = "us-central1"
    GOOGLE_APPLICATION_CREDENTIALS: Optional[str] = None
    
    # Google OAuth Configuration
    GOOGLE_CLIENT_ID: Optional[str] = None
    GOOGLE_CLIENT_SECRET: Optional[str] = None
    
    # Calendar Integration Configuration
    # Google Calendar
    GOOGLE_CALENDAR_SCOPES: List[str] = []
    GOOGLE_CALENDAR_REDIRECT_URI: Optional[str] = None
    
    # Apple Calendar (CalDAV)
    APPLE_CALENDAR_SERVER_URL: Optional[str] = None
    APPLE_CALENDAR_PRINCIPAL_URL: Optional[str] = None
    
    @validator("GOOGLE_CALENDAR_SCOPES", pre=True)
    def assemble_google_calendar_scopes(cls, v):
        if isinstance(v, str) and v:
            return [scope.strip() for scope in v.split(",")]
        elif isinstance(v, list):
            return v
        return []
    
    # Calendar Sync Configuration
    CALENDAR_SYNC_FREQUENCY_MINUTES: int = 15
    CALENDAR_SYNC_MAX_RETRIES: int = 3
    CALENDAR_WEBHOOK_BASE_URL: Optional[str] = None
    
    # Stripe Configuration
    STRIPE_SECRET_KEY: Optional[str] = None
    STRIPE_PUBLISHABLE_KEY: Optional[str] = None
    STRIPE_WEBHOOK_SECRET: Optional[str] = None
    STRIPE_PRICE_ID_PRO_MONTHLY: Optional[str] = None
    STRIPE_PRICE_ID_PRO_YEARLY: Optional[str] = None
    
    # Environment
    ENVIRONMENT: str = "development"
    DEBUG: bool = True
    
    class Config:
        env_file = ".env"
        case_sensitive = True
        env_file_encoding = 'utf-8'

settings = Settings()

def get_settings() -> Settings:
    """Get application settings instance"""
    return settings