import pytest
import asyncio
from typing import Generator, AsyncGenerator
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.main import app
from app.db.base import Base
from app.core.deps import get_db
from app.core.config import settings
from app.services.auth_service import AuthService
from app.services.user_service import UserService
from app.services.event_service import EventService
from app.models.user_models import User
from app.schemas.user import UserRegister

# Test database URL
TEST_DATABASE_URL = "sqlite:///./test_planetal.db"

# Create test engine
test_engine = create_engine(
    TEST_DATABASE_URL,
    connect_args={
        "check_same_thread": False,
    },
    poolclass=StaticPool,
)

# Create test session
TestSessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=test_engine
)

@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()

@pytest.fixture(scope="function")
def db_session():
    """Create a fresh database session for each test."""
    # Create all tables
    Base.metadata.create_all(bind=test_engine)
    
    # Create session
    session = TestSessionLocal()
    
    try:
        yield session
    finally:
        session.close()
        # Drop all tables after test
        Base.metadata.drop_all(bind=test_engine)

@pytest.fixture(scope="function")
def client(db_session) -> Generator[TestClient, None, None]:
    """Create a test client with database session override."""
    
    def get_test_db():
        try:
            yield db_session
        finally:
            pass
    
    app.dependency_overrides[get_db] = get_test_db
    
    with TestClient(app) as test_client:
        yield test_client
    
    app.dependency_overrides.clear()

@pytest.fixture
def auth_service(db_session):
    """Create an AuthService instance for testing."""
    return AuthService(db_session)

@pytest.fixture
def user_service(db_session):
    """Create a UserService instance for testing."""
    return UserService(db_session)

@pytest.fixture
def event_service(db_session):
    """Create an EventService instance for testing."""
    return EventService(db_session)

@pytest.fixture
def test_user_data():
    """Sample user data for testing."""
    return {
        "email": "test@example.com",
        "password": "testpassword123",
        "confirm_password": "testpassword123",
        "full_name": "Test User",
        "username": "testuser"
    }

@pytest.fixture
def test_user(db_session, auth_service, test_user_data) -> User:
    """Create a test user in the database."""
    user_register = UserRegister(**test_user_data)
    user = auth_service.register_user(user_register)
    return user

@pytest.fixture
def test_user_token(client, test_user_data):
    """Create a test user and return authentication token."""
    # Register user
    client.post("/api/v1/auth/register", json=test_user_data)
    
    # Login and get token
    login_response = client.post("/api/v1/auth/login", json={
        "email": test_user_data["email"],
        "password": test_user_data["password"]
    })
    
    token_data = login_response.json()
    return token_data["access_token"]

@pytest.fixture
def authenticated_client(client, test_user_token):
    """Create a test client with authentication headers."""
    client.headers.update({"Authorization": f"Bearer {test_user_token}"})
    return client

@pytest.fixture
def test_event_data():
    """Sample event data for testing."""
    from datetime import datetime, timedelta
    
    start_time = datetime.utcnow() + timedelta(days=7)
    end_time = start_time + timedelta(hours=3)
    
    return {
        "title": "Test Event",
        "description": "A test event for unit testing",
        "event_type": "party",
        "start_datetime": start_time.isoformat(),
        "end_datetime": end_time.isoformat(),
        "venue_name": "Test Venue",
        "venue_city": "Test City",
        "is_public": False,
        "max_attendees": 50
    }

@pytest.fixture
def test_task_data():
    """Sample task data for testing."""
    from datetime import datetime, timedelta
    
    due_date = datetime.utcnow() + timedelta(days=3)
    
    return {
        "title": "Test Task",
        "description": "A test task for unit testing",
        "priority": "medium",
        "due_date": due_date.isoformat(),
        "category": "planning",
        "estimated_cost": 100.0
    }

@pytest.fixture
def test_expense_data():
    """Sample expense data for testing."""
    from datetime import datetime
    
    return {
        "title": "Test Expense",
        "description": "A test expense for unit testing",
        "amount": 150.0,
        "currency": "USD",
        "category": "venue",
        "vendor_name": "Test Vendor",
        "expense_date": datetime.utcnow().isoformat(),
        "is_shared": True,
        "split_equally": True
    }

# Test data factories
class UserFactory:
    """Factory for creating test users."""
    
    @staticmethod
    def create_user_data(email: str = None, username: str = None):
        import uuid
        unique_id = str(uuid.uuid4())[:8]
        
        return {
            "email": email or f"user_{unique_id}@example.com",
            "password": "testpassword123",
            "confirm_password": "testpassword123",
            "full_name": f"Test User {unique_id}",
            "username": username or f"user_{unique_id}"
        }
    
    @staticmethod
    def create_user(auth_service: AuthService, **kwargs):
        user_data = UserFactory.create_user_data(**kwargs)
        user_register = UserRegister(**user_data)
        return auth_service.register_user(user_register)

class EventFactory:
    """Factory for creating test events."""
    
    @staticmethod
    def create_event_data(title: str = None, **kwargs):
        from datetime import datetime, timedelta
        import uuid
        
        unique_id = str(uuid.uuid4())[:8]
        start_time = datetime.utcnow() + timedelta(days=7)
        end_time = start_time + timedelta(hours=3)
        
        default_data = {
            "title": title or f"Test Event {unique_id}",
            "description": f"Test event description {unique_id}",
            "event_type": "party",
            "start_datetime": start_time,
            "end_datetime": end_time,
            "venue_name": "Test Venue",
            "venue_city": "Test City",
            "is_public": False
        }
        
        default_data.update(kwargs)
        return default_data
    
    @staticmethod
    def create_event(event_service: EventService, creator_id: int, **kwargs):
        from app.schemas.event import EventCreate
        
        event_data = EventFactory.create_event_data(**kwargs)
        event_create = EventCreate(**event_data)
        return event_service.create_event(event_create, creator_id)

# Pytest configuration
pytest_plugins = []

# Async test support
@pytest.fixture(scope="session")
def anyio_backend():
    return "asyncio"

# Mock external services
@pytest.fixture
def mock_email_service(monkeypatch):
    """Mock email service for testing."""
    emails_sent = []
    
    def mock_send_email(to_email, subject, body):
        emails_sent.append({
            "to": to_email,
            "subject": subject,
            "body": body
        })
        return True
    
    # monkeypatch.setattr("app.services.email_service.send_email", mock_send_email)
    return emails_sent

@pytest.fixture
def mock_file_storage(monkeypatch, tmp_path):
    """Mock file storage for testing."""
    uploaded_files = []
    
    def mock_upload_file(file, filename):
        file_path = tmp_path / filename
        with open(file_path, "wb") as f:
            f.write(file.read())
        
        uploaded_files.append({
            "filename": filename,
            "path": str(file_path),
            "size": file_path.stat().st_size
        })
        
        return str(file_path)
    
    # monkeypatch.setattr("app.services.file_service.upload_file", mock_upload_file)
    return uploaded_files

# Performance testing fixtures
@pytest.fixture
def performance_timer():
    """Timer for performance testing."""
    import time
    
    class Timer:
        def __init__(self):
            self.start_time = None
            self.end_time = None
        
        def start(self):
            self.start_time = time.time()
        
        def stop(self):
            self.end_time = time.time()
        
        @property
        def elapsed(self):
            if self.start_time and self.end_time:
                return self.end_time - self.start_time
            return None
    
    return Timer()