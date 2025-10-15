from sqlalchemy import create_engine, MetaData
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from app.core.config import settings

# Create SQLAlchemy engine
engine = create_engine(
    settings.DATABASE_URL,
    connect_args={"check_same_thread": False} if "sqlite" in settings.DATABASE_URL else {}
)

# Create SessionLocal class
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Create Base class for models
Base = declarative_base()

# Metadata for migrations (renamed to avoid conflicts)
db_metadata = MetaData()

# This is important for Alembic migrations
def import_models():
    """Import all models to register them with SQLAlchemy"""
    from app.models import user_models 
    from app.models import event_models
    from app.models import media_models
    from app.models import shared_models
    from app.models import ai_chat_models
    from app.models import calendar_models
    from app.models import creative_models
    from app.models import message_models
    from app.models import notification_models
    from app.models import subscription_models
    from app.models import timeline_models
    from app.models import vendor_models
    from app.models import invite_models
    from app.core import idempotency  # Import idempotency models