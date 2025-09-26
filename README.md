# Plan et al - Ultimate Co-planner Backend

A comprehensive event planning platform backend built with FastAPI, designed to make event planning collaborative, stress-free, and enjoyable.

## 🚀 Features

### Core Features
- **Event Management**: Create, organize, and manage events of all types
- **Guest Management**: Invite guests, track RSVPs, and manage attendee lists
- **Task Management**: Create and assign tasks with deadlines and priorities
- **Budget Tracking**: Track expenses and split costs among participants
- **Real-time Collaboration**: Comments, polls, and collaborative planning
- **Media Sharing**: Upload and share photos, videos, and documents

### Advanced Features
- **AI-Powered Suggestions**: Smart recommendations for venues, vendors, and planning
- **Social Features**: Friend connections and event discovery
- **Notification System**: Email and push notifications for important updates
- **Calendar Integration**: Sync with Google/Apple Calendar
- **Mobile-Friendly API**: RESTful API designed for mobile and web clients

## 🛠 Tech Stack

- **Framework**: FastAPI 0.104+
- **Database**: SQLAlchemy with SQLite/PostgreSQL
- **Authentication**: JWT with refresh tokens
- **Validation**: Pydantic v2
- **Background Tasks**: Celery with Redis
- **File Storage**: Local/GCP Cloud Storage support
- **Documentation**: Auto-generated OpenAPI/Swagger

## 📋 Prerequisites

- Python 3.10+
- pip or poetry
- Redis (for background tasks)
- PostgreSQL (optional, SQLite by default)

## 🚀 Quick Start

### 1. Clone the Repository
```bash
git clone <repository-url>
cd UltimateCo-planner-Backend
```

### 2. Set Up Virtual Environment
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

### 3. Install Dependencies
```bash
pip install -r requirements.txt
```

### 4. Environment Configuration
```bash
cp .env.example .env
# Edit .env with your configuration
```

### 5. Initialize Database
```bash
# Initialize Alembic
alembic init app/db/migrations

# Create first migration
alembic revision --autogenerate -m "Initial migration"

# Apply migrations
alembic upgrade head
```

### 6. Run the Application
```bash
uvicorn app.main:app --reload
```

The API will be available at `http://localhost:8000`

## 🐳 Docker Setup

### Development with Docker Compose
```bash
# Start all services
docker-compose up -d

# View logs
docker-compose logs -f api

# Stop services
docker-compose down
```

### Production Deployment
```bash
# Build and run with production profile
docker-compose --profile production up -d
```

##  API Documentation

Once the server is running, visit:
- **Swagger UI**: `http://localhost:8000/docs`
- **ReDoc**: `http://localhost:8000/redoc`
- **OpenAPI JSON**: `http://localhost:8000/openapi.json`

## 🔧 Configuration

### Environment Variables

Key configuration options in `.env`:

```env
# Database
DATABASE_URL=sqlite:///./planetal.db

# Security
SECRET_KEY=your-secret-key
ACCESS_TOKEN_EXPIRE_MINUTES=30

# Email
SMTP_HOST=smtp.gmail.com
SMTP_USER=your-email@gmail.com
SMTP_PASSWORD=your-app-password

# External APIs
OPENAI_API_KEY=your-openai-key
GOOGLE_MAPS_API_KEY=your-maps-key
```

## 🏗 Project Structure

```
app/
├── api/                    # API routes
│   ├── v1/
│   │   ├── routers/
│   │   │   ├── auth.py     # Authentication endpoints
│   │   │   ├── users.py    # User management
│   │   │   └── events.py   # Event management
│   │   └── api_router.py   # Main API router
│   └── health.py           # Health check endpoints
├── core/                   # Core functionality
│   ├── deps.py            # Dependencies
│   ├── security.py        # Security utilities
│   └── errors.py          # Error handling
├── db/                     # Database
│   ├── base.py            # Database base
│   ├── session.py         # Database sessions
│   └── migrations/        # Alembic migrations
├── models/                 # SQLAlchemy models
│   ├── user_models.py     # User-related models
│   ├── event_models.py    # Event-related models
│   ├── media_models.py    # Media models
│   └── shared_models.py   # Shared models and enums
├── schemas/                # Pydantic schemas
│   ├── user.py            # User schemas
│   ├── event.py           # Event schemas
│   └── pagination.py      # Pagination schemas
├── services/               # Business logic
│   ├── auth_service.py    # Authentication service
│   ├── user_service.py    # User service
│   └── event_service.py   # Event service
├── repositories/           # Data access layer
│   ├── user_repo.py       # User repository
│   └── event_repo.py      # Event repository
├── tasks/                  # Background tasks
│   ├── celery_app.py      # Celery configuration
│   └── reminder_tasks.py  # Reminder tasks
├── utils/                  # Utilities
├── tests/                  # Test files
├── config.py              # Configuration
└── main.py                # FastAPI application
```

##  Authentication

The API uses JWT tokens with refresh token rotation:

1. **Register**: `POST /api/v1/auth/register`
2. **Login**: `POST /api/v1/auth/login`
3. **Refresh**: `POST /api/v1/auth/refresh`
4. **Logout**: `POST /api/v1/auth/logout`


##  Database Schema

### Key Models

- **User**: User accounts and profiles
- **Event**: Event information and settings
- **EventInvitation**: Guest invitations and RSVPs
- **Task**: Event tasks and assignments
- **Expense**: Budget tracking and expense splitting
- **Media**: File uploads and media sharing
- **Comment**: Event discussions
- **Poll**: Decision-making polls

##  Testing

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=app

# Run specific test file
pytest tests/test_auth.py

# Development
ENVIRONMENT=development
DEBUG=true

# Production
ENVIRONMENT=production
DEBUG=false
```


### Database Migrations

```bash
# Create migration
alembic revision --autogenerate -m "Description"

# Apply migrations
alembic upgrade head

# Rollback migration
alembic downgrade -1
```

### Background Tasks

```bash
# Start Celery worker
celery -A app.tasks.celery_app worker --loglevel=info

# Start Celery beat (scheduler)
celery -A app.tasks.celery_app beat --loglevel=info

# Monitor tasks
celery -A app.tasks.celery_app flower
```

## Monitoring

### Health Checks

- **Basic**: `GET /health/`
- **Detailed**: `GET /health/detailed`
- **Readiness**: `GET /health/ready`
- **Liveness**: `GET /health/live`

### Logging

Logs are structured and include:
- Request/response logging
- Error tracking
- Performance metrics
- Security events

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests
5. Run quality checks
6. Submit a pull request

##  License

This project is licensed under the MIT License - see the LICENSE file for details.

##  Support

For support and questions:
- Create an issue on GitHub
- Check the documentation
- Review the API docs at `/docs`


**Plan et al** - Making event planning collaborative and stress-free! 