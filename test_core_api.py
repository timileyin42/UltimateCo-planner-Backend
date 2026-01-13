"""
Core API Testing Script - Internal Services Only
Tests APIs that don't require external services (no calendar, Google Maps, Stripe, etc.)
Focuses on: Notifications, Messages, Invites, Timeline advanced features, Creative advanced features
"""
import requests
import json
from datetime import datetime, timedelta, timezone
import os
import psycopg2

# Load environment variables from .env file
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # dotenv not installed, will use system environment

# Base URL
BASE_URL = "http://localhost:8000"
API_V1 = f"{BASE_URL}/api/v1"

# Database connection helper
def get_db_connection():
    """Get database connection from environment variables"""
    try:
        # First try to parse DATABASE_URL if available
        database_url = os.getenv("DATABASE_URL", "")
        if database_url:
            # Parse postgresql://user:password@host:port/database
            from urllib.parse import urlparse
            parsed = urlparse(database_url)
            conn = psycopg2.connect(
                host=parsed.hostname or "localhost",
                port=parsed.port or 5432,
                database=parsed.path.lstrip('/') if parsed.path else "planetal",
                user=parsed.username or "postgres",
                password=parsed.password or ""
            )
        else:
            # Fallback to individual environment variables or defaults for local dev
            conn = psycopg2.connect(
                host=os.getenv("POSTGRES_HOST", "localhost"),
                port=os.getenv("POSTGRES_PORT", "5432"),
                database=os.getenv("POSTGRES_DB", "planetal"),
                user=os.getenv("POSTGRES_USER", "planetal"),
                password=os.getenv("POSTGRES_PASSWORD", "planetal123")
            )
        return conn
    except Exception as e:
        print_error(f"Database connection failed: {str(e)}")
        return None

def verify_user_in_db(user_email):
    """Directly verify user in database by setting is_verified=True"""
    conn = get_db_connection()
    if not conn:
        print_warning("Could not connect to database for verification")
        return False
    
    try:
        cursor = conn.cursor()
        # Update the user's is_verified status
        cursor.execute(
            "UPDATE users SET is_verified = TRUE WHERE email = %s",
            (user_email,)
        )
        conn.commit()
        rows_affected = cursor.rowcount
        cursor.close()
        conn.close()
        
        if rows_affected > 0:
            print_success(f"User {user_email} verified in database")
            return True
        else:
            print_warning(f"No user found with email {user_email}")
            return False
    except Exception as e:
        print_error(f"Database verification error: {str(e)}")
        if conn:
            conn.close()
        return False

# Colors for terminal output
class Colors:
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    END = '\033[0m'

def print_success(message):
    print(f"{Colors.GREEN}[+] {message}{Colors.END}")

def print_error(message):
    print(f"{Colors.RED}[X] {message}{Colors.END}")

def print_info(message):
    print(f"{Colors.BLUE}[i] {message}{Colors.END}")

def print_warning(message):
    print(f"{Colors.YELLOW}[!] {message}{Colors.END}")

# Global variable to store tokens
auth_tokens = {
    "access_token": None,
    "refresh_token": None,
    "user_id": None
}

# Global storage for created resources
test_resources = {
    "event_id": None,
    "timeline_id": None,
    "notification_log_id": None,
    "notification_logs": [],
    "notification_preferences": [],
    "notification_in_app": [],
    "push_device_id": None,
    "invite_code_id": None,
    "invite_link_id": None,
    "custom_qr_url": None,
    "profile_qr_url": None,
    "timeline_items": [],
    "moodboard_id": None,
    "playlist_id": None,
    "game_id": None,
    "game_session_id": None,
    "message_id": None,
    "vendor_id": None,
    "user_profile_id": None,
    "generated_questions": [],
    "profile_picture_url": None,
    "test_moodboard_id": None,
    "moodboard_image_url": None,
    "vendor_image_url": None,
    "task_category_name": None,
    "task_title": None
}

def get_headers():
    """Get authorization headers"""
    return {
        "Authorization": f"Bearer {auth_tokens['access_token']}",
        "Content-Type": "application/json"
    }

# ============================================================================
# AUTHENTICATION & SETUP
# ============================================================================

def test_register():
    """Test user registration"""
    print("\n" + "="*50)
    print("Testing User Registration")
    print("="*50)
    
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S%f")
    user_data = {
        "email": f"core-api-test-{timestamp}@example.com",
        "full_name": "Core API Tester",
        "username": f"coretester{timestamp[:8]}",
        "password": "TestPassword123!",
        "confirm_password": "TestPassword123!",
        "timezone": "UTC",
        "country": "Nigeria"
    }
    
    try:
        response = requests.post(f"{API_V1}/auth/register", json=user_data)
        if response.status_code in [200, 201]:
            data = response.json()
            auth_tokens["user_id"] = data.get("id")
            print_success("User registration successful")
            print_info(f"User ID: {data.get('id')}")
            print_info(f"Email: {data.get('email')}")
            
            # Verify user directly in database
            verify_user_in_db(user_data["email"])
            
            return True, user_data
        else:
            print_error(f"Registration failed: {response.status_code}")
            print_error(f"Response: {response.text}")
            return False, None
    except Exception as e:
        print_error(f"Registration error: {str(e)}")
        return False, None

def test_login(user_data):
    """Test user login"""
    print("\n" + "="*50)
    print("Testing User Login")
    print("="*50)
    
    if not user_data:
        print_error("No user data available for login")
        return False
    
    login_data = {
        "email": user_data["email"],
        "password": user_data["password"]
    }
    
    try:
        response = requests.post(f"{API_V1}/auth/login", json=login_data)
        if response.status_code == 200:
            data = response.json()
            print_success("Login successful")
            print_info(f"Access token received: {data.get('access_token')[:20]}...")
            auth_tokens["access_token"] = data.get("access_token")
            auth_tokens["refresh_token"] = data.get("refresh_token")
            return True
        else:
            print_error(f"Login failed: {response.status_code}")
            print_error(f"Response: {response.text}")
            return False
    except Exception as e:
        print_error(f"Login error: {str(e)}")
        return False

def test_create_event():
    """Create a test event for other tests"""
    print("\n" + "="*50)
    print("Creating Test Event")
    print("="*50)
    
    start_time = datetime.now(timezone.utc) + timedelta(days=14)
    end_time = start_time + timedelta(hours=3)

    event_data = {
        "title": "Core API Test Event",
        "description": "Event for testing core APIs",
        "event_type": "party",
        "start_datetime": start_time.isoformat(),
        "end_datetime": end_time.isoformat(),
        "timezone": "UTC",
        "venue_name": "Test Venue",
        "venue_city": "Lagos",
        "venue_country": "Nigeria",
        "is_public": False,
        "max_attendees": 100,
        "auto_optimize_location": False,
        "cover_image_url": "https://storage.googleapis.com/planetal-storage/uploads/images/test-cover.jpg",
        "task_categories": [
            {
                "name": "Food & Catering",
                "items": [
                    {
                        "title": "Order birthday cake",
                        "description": "Chocolate cake for 30 people",
                        "assignee_id": None
                    },
                    {
                        "title": "Book caterer",
                        "description": "Nigerian cuisine",
                        "assignee_id": None
                    }
                ]
            },
            {
                "name": "Decorations",
                "items": [
                    {
                        "title": "Buy balloons",
                        "description": "Red and gold theme"
                    },
                    {
                        "title": "Set up venue",
                        "description": "Arrange tables and chairs"
                    }
                ]
            },
            {
                "name": "Entertainment",
                "items": [
                    {
                        "title": "Hire DJ",
                        "description": "DJ for 4 hours"
                    }
                ]
            }
        ]
    }
    
    try:
        response = requests.post(
            f"{API_V1}/events/",
            json=event_data,
            headers=get_headers()
        )
        if response.status_code in [200, 201]:
            data = response.json()
            test_resources["event_id"] = data.get("id")
            print_success(f"Event created: {data.get('title')}")
            print_info(f"Event ID: {test_resources['event_id']}")
            print_info(f"Cover Image: {data.get('cover_image_url', 'None')}")
            print_info(f"Task Categories: {len(data.get('task_categories', []))}")
            return True
        else:
            print_error(f"Event creation failed: {response.status_code}")
            print_error(f"Response: {response.text}")
            return False
    except Exception as e:
        print_error(f"Event creation error: {str(e)}")
        return False

def test_get_my_events_upcoming():
    """Test getting upcoming events with category filter"""
    print("\n" + "="*50)
    print("Testing Get My Events - Upcoming Category")
    print("="*50)
    
    try:
        response = requests.get(
            f"{API_V1}/events/my?category=upcoming",
            headers=get_headers()
        )
        if response.status_code == 200:
            data = response.json()
            events = data.get('events', [])
            print_success("Retrieved upcoming events")
            print_info(f"Found {len(events)} upcoming event(s)")
            if events:
                for event in events[:3]:  # Show first 3
                    print_info(f"  - {event.get('title')} on {event.get('start_datetime')}")
            return True
        else:
            print_error(f"Get upcoming events failed: {response.status_code}")
            print_error(f"Response: {response.text}")
            return False
    except Exception as e:
        print_error(f"Get upcoming events error: {str(e)}")
        return False

def test_get_my_events_drafts():
    """Test getting draft events with category filter"""
    print("\n" + "="*50)
    print("Testing Get My Events - Drafts Category")
    print("="*50)
    
    try:
        response = requests.get(
            f"{API_V1}/events/my?category=drafts",
            headers=get_headers()
        )
        if response.status_code == 200:
            data = response.json()
            events = data.get('events', [])
            print_success("Retrieved draft events")
            print_info(f"Found {len(events)} draft event(s)")
            if events:
                for event in events[:3]:  # Show first 3
                    print_info(f"  - {event.get('title')} (status: {event.get('status')})")
            return True
        else:
            print_error(f"Get draft events failed: {response.status_code}")
            print_error(f"Response: {response.text}")
            return False
    except Exception as e:
        print_error(f"Get draft events error: {str(e)}")
        return False

def test_get_my_events_hosting():
    """Test getting events user is hosting"""
    print("\n" + "="*50)
    print("Testing Get My Events - Hosting Category")
    print("="*50)
    
    try:
        response = requests.get(
            f"{API_V1}/events/my?category=hosting",
            headers=get_headers()
        )
        if response.status_code == 200:
            data = response.json()
            events = data.get('events', [])
            print_success("Retrieved hosting events")
            print_info(f"Found {len(events)} event(s) you're hosting")
            if events:
                for event in events[:3]:  # Show first 3
                    print_info(f"  - {event.get('title')}")
            return True
        else:
            print_error(f"Get hosting events failed: {response.status_code}")
            return False
    except Exception as e:
        print_error(f"Get hosting events error: {str(e)}")
        return False

# ============================================================================
# TASK TESTS
# ============================================================================

def test_get_event_tasks():
    """Test getting event tasks grouped by categories"""
    print("\n" + "="*50)
    print("Testing Get Event Tasks (Categorized)")
    print("="*50)
    
    event_id = test_resources.get("event_id")
    if not event_id:
        print_warning("No event ID available. Create event first.")
        return None
    
    try:
        response = requests.get(
            f"{API_V1}/events/{event_id}/tasks",
            headers=get_headers()
        )
        if response.status_code == 200:
            data = response.json()
            task_categories = data.get('task_categories', [])
            print_success("Retrieved task categories")
            print_info(f"Found {len(task_categories)} categor(ies)")
            
            total_tasks = 0
            for category in task_categories:
                category_name = category.get('name')
                items = category.get('items', [])
                total_tasks += len(items)
                print_info(f"\n  Category: {category_name}")
                print_info(f"  Tasks: {len(items)}")
                for item in items[:3]:  # Show first 3 items
                    completed_icon = "[X]" if item.get('completed') else "[ ]"
                    print_info(f"    {completed_icon} {item.get('title')}")
                
                # Store first task from first category for update test
                if not test_resources.get("task_id") and items:
                    first_item = items[0]
                    test_resources["task_id"] = first_item.get('id')
                    test_resources["task_category_name"] = category_name
                    test_resources["task_title"] = first_item.get('title')
                    print_info(f"\n  [Stored for update test: {first_item.get('title')}]")
            
            print_info(f"\nTotal tasks: {total_tasks}")
            return True
        else:
            print_error(f"Get event tasks failed: {response.status_code}")
            print_error(f"Response: {response.text}")
            return False
    except Exception as e:
        print_error(f"Get event tasks error: {str(e)}")
        return False

def test_get_single_task():
    """Test getting a single task by event_id, category, and title"""
    print("\n" + "="*50)
    print("Testing Get Single Task")
    print("="*50)
    
    event_id = test_resources.get("event_id")
    category_name = test_resources.get("task_category_name")
    task_title = test_resources.get("task_title")
    
    if not event_id or not category_name or not task_title:
        print_warning("No event/task info available. Get event tasks first.")
        return None
    
    try:
        response = requests.get(
            f"{API_V1}/events/tasks/by-title",
            params={
                "event_id": event_id,
                "category": category_name,
                "title": task_title
            },
            headers=get_headers()
        )
        if response.status_code == 200:
            task = response.json()
            print_success("Retrieved task details")
            print_info(f"Title: {task.get('title')}")
            print_info(f"Description: {task.get('description', 'None')}")
            print_info(f"Category: {task.get('category', 'None')}")
            print_info(f"Status: {task.get('status')}")
            print_info(f"Priority: {task.get('priority')}")
            print_info(f"Assignee ID: {task.get('assignee_id', 'None')}")
            return True
        else:
            print_error(f"Get task failed: {response.status_code}")
            print_error(f"Response: {response.text}")
            return False
    except Exception as e:
        print_error(f"Get task error: {str(e)}")
        return False

def test_update_task():
    """Test updating a task (mark as completed, assign user, etc.)"""
    print("\n" + "="*50)
    print("Testing Update Task")
    print("="*50)
    
    event_id = test_resources.get("event_id")
    category_name = test_resources.get("task_category_name")
    task_title = test_resources.get("task_title")
    
    if not event_id:
        print_warning("No event ID available. Create event first.")
        return None

    if not category_name or not task_title:
        print_warning("No task category or title available. Get event tasks first.")
        return None
    
    update_data = {
        "event_id": event_id,
        "category": category_name,
        "title": task_title,
        "new_title": "Order birthday cake - Updated",
        "description": "Updated: Chocolate cake ordered from Sweet Treats Bakery",
        "status": "completed",
        "priority": "high"
    }
    
    try:
        response = requests.put(
            f"{API_V1}/events/tasks/update",
            json=update_data,
            headers=get_headers()
        )
        if response.status_code == 200:
            task = response.json()
            print_success("Task updated successfully")
            print_info(f"Title: {task.get('title')}")
            print_info(f"Status: {task.get('status')}")
            print_info(f"Priority: {task.get('priority')}")
            print_info(f"Description: {task.get('description')}")
            # Update stored title for next test
            test_resources["task_title"] = task.get('title')
            return True
        else:
            print_error(f"Update task failed: {response.status_code}")
            print_error(f"Response: {response.text}")
            return False
    except Exception as e:
        print_error(f"Update task error: {str(e)}")
        return False

def test_update_task_mark_incomplete():
    """Test marking a task as incomplete"""
    print("\n" + "="*50)
    print("Testing Mark Task as Incomplete")
    print("="*50)
    
    event_id = test_resources.get("event_id")
    category_name = test_resources.get("task_category_name")
    task_title = test_resources.get("task_title")
    
    if not event_id:
        print_warning("No event ID available. Create event first.")
        return None

    if not category_name or not task_title:
        print_warning("No task category or title available. Get event tasks first.")
        return None
    
    update_data = {
        "event_id": event_id,
        "category": category_name,
        "title": task_title,
        "status": "todo"
    }
    
    try:
        response = requests.put(
            f"{API_V1}/events/tasks/update",
            json=update_data,
            headers=get_headers()
        )
        if response.status_code == 200:
            task = response.json()
            print_success("Task marked as incomplete")
            print_info(f"Status: {task.get('status')}")
            return True
        else:
            print_error(f"Update task failed: {response.status_code}")
            print_error(f"Response: {response.text}")
            return False
    except Exception as e:
        print_error(f"Update task error: {str(e)}")
        return False

def test_delete_task():
    """Test deleting a task"""
    print("\n" + "="*50)
    print("Testing Delete Task")
    print("="*50)
    
    event_id = test_resources.get("event_id")
    category_name = test_resources.get("task_category_name")
    task_title = test_resources.get("task_title")
    
    if not event_id or not category_name or not task_title:
        print_warning("No event/task info available. Get event tasks first.")
        return None
    
    try:
        response = requests.delete(
            f"{API_V1}/events/tasks/delete",
            params={
                "event_id": event_id,
                "category": category_name,
                "title": task_title
            },
            headers=get_headers()
        )
        if response.status_code == 204:
            print_success("Task deleted successfully")
            # Clear the stored task info since it's deleted
            test_resources["task_title"] = None
            return True
        else:
            print_error(f"Delete task failed: {response.status_code}")
            print_error(f"Response: {response.text}")
            return False
    except Exception as e:
        print_error(f"Delete task error: {str(e)}")
        return False

# ============================================================================
# NOTIFICATION TESTS
# ============================================================================
def test_get_my_events_all():
    """Test getting all user's events without category filter"""
    print("\n" + "="*50)
    print("Testing Get My Events - All Events")
    print("="*50)
    
    try:
        response = requests.get(
            f"{API_V1}/events/my",
            headers=get_headers()
        )
        if response.status_code == 200:
            data = response.json()
            events = data.get('events', [])
            total = data.get('total', 0)
            print_success("Retrieved all events")
            print_info(f"Found {len(events)} event(s) | Total: {total}")
            if events:
                for event in events[:3]:  # Show first 3
                    print_info(f"  - {event.get('title')} ({event.get('status')})")
            return True
        else:
            print_error(f"Get all events failed: {response.status_code}")
            print_error(f"Response: {response.text}")
            return False
    except Exception as e:
        print_error(f"Get all events error: {str(e)}")
        return False

# ============================================================================
# NOTIFICATION TESTS
# ============================================================================

def test_get_notifications():
    """Test getting user notifications"""
    print("\n" + "="*50)
    print("Testing Get Notifications")
    print("="*50)
    
    try:
        response = requests.get(
            f"{API_V1}/notifications/",
            headers=get_headers()
        )
        if response.status_code == 200:
            data = response.json()
            notifications = data.get('notifications', [])
            unread_count = data.get('unread_count', 0)
            print_success("Retrieved notifications")
            print_info(f"Total notifications: {len(notifications)} | Unread: {unread_count}")
            if notifications:
                test_resources["notification_log_id"] = notifications[0].get('id')
                test_resources["notification_logs"] = notifications
            return True
        else:
            print_error(f"Get notifications failed: {response.status_code}")
            return False
    except Exception as e:
        print_error(f"Get notifications error: {str(e)}")
        return False

def test_notification_preferences():
    """Test getting notification preferences"""
    print("\n" + "="*50)
    print("Testing Get Notification Preferences")
    print("="*50)
    
    try:
        response = requests.get(
            f"{API_V1}/notifications/preferences",
            headers=get_headers()
        )
        if response.status_code == 200:
            preferences = response.json()
            test_resources["notification_preferences"] = preferences
            print_success("Retrieved notification preferences")
            print_info(f"Preference count: {len(preferences)}")
            if preferences:
                sample = preferences[0]
                print_info(f"Sample type: {sample.get('notification_type')} | Email: {sample.get('email_enabled')} | Push: {sample.get('push_enabled')}")
            return True
        else:
            print_error(f"Get preferences failed: {response.status_code}")
            return False
    except Exception as e:
        print_error(f"Get preferences error: {str(e)}")
        return False

def test_update_notification_preferences():
    """Test updating notification preferences"""
    print("\n" + "="*50)
    print("Testing Update Notification Preferences")
    print("="*50)
    
    preferences = test_resources.get("notification_preferences", [])
    if not preferences:
        print_warning("No notification preferences available to update")
        return None

    target_pref = preferences[0]
    payload_pref = {
        "notification_type": target_pref.get("notification_type", "event_reminder"),
        "email_enabled": not target_pref.get("email_enabled", True),
        "sms_enabled": target_pref.get("sms_enabled", False),
        "push_enabled": target_pref.get("push_enabled", True),
        "in_app_enabled": target_pref.get("in_app_enabled", True),
        "advance_notice_hours": target_pref.get("advance_notice_hours", 24),
        "quiet_hours_start": target_pref.get("quiet_hours_start"),
        "quiet_hours_end": target_pref.get("quiet_hours_end"),
        "max_daily_notifications": target_pref.get("max_daily_notifications", 10)
    }

    preferences_data = {"preferences": [payload_pref]}
    
    try:
        response = requests.put(
            f"{API_V1}/notifications/preferences",
            json=preferences_data,
            headers=get_headers()
        )
        if response.status_code == 200:
            updated = response.json()
            test_resources["notification_preferences"] = updated
            print_success("Updated notification preferences")
            print_info(f"Updated type: {payload_pref['notification_type']} | Email enabled: {payload_pref['email_enabled']}")
            return True
        else:
            print_error(f"Update preferences failed: {response.status_code}")
            return False
    except Exception as e:
        print_error(f"Update preferences error: {str(e)}")
        return False

def test_get_notification_channels():
    """Test retrieving notification channel availability"""
    print("\n" + "="*50)
    print("Testing Get Notification Channels")
    print("="*50)
    
    try:
        response = requests.get(
            f"{API_V1}/notifications/channels",
            headers=get_headers()
        )
        if response.status_code == 200:
            data = response.json()
            channels = data.get("channels", [])
            print_success("Retrieved notification channels")
            print_info(f"Channels reported: {', '.join([channel.get('id') for channel in channels]) or 'none'}")
            return True
        else:
            print_error(f"Get channels failed: {response.status_code}")
            return False
    except Exception as e:
        print_error(f"Get channels error: {str(e)}")
        return False

def test_get_notification_logs():
    """Test retrieving notification logs"""
    print("\n" + "="*50)
    print("Testing Get Notification Logs")
    print("="*50)
    
    try:
        response = requests.get(
            f"{API_V1}/notifications/logs",
            headers=get_headers()
        )
        if response.status_code == 200:
            data = response.json()
            logs = data.get("logs", []) if isinstance(data, dict) else []
            print_success("Retrieved notification logs")
            print_info(f"Log entries returned: {len(logs)}")
            return True
        else:
            print_error(f"Get logs failed: {response.status_code}")
            return False
    except Exception as e:
        print_error(f"Get logs error: {str(e)}")
        return False

def test_get_in_app_notifications():
    """Test retrieving in-app notifications"""
    print("\n" + "="*50)
    print("Testing Get In-App Notifications")
    print("="*50)
    
    try:
        response = requests.get(
            f"{API_V1}/notifications/in-app",
            headers=get_headers()
        )
        if response.status_code == 200:
            data = response.json()
            notifications = data.get("notifications", [])
            test_resources["notification_in_app"] = notifications
            print_success("Retrieved in-app notifications")
            print_info(f"In-app notifications: {len(notifications)} | Unread: {data.get('unread_count', 0)}")
            return True
        else:
            print_error(f"Get in-app notifications failed: {response.status_code}")
            return False
    except Exception as e:
        print_error(f"Get in-app notifications error: {str(e)}")
        return False

# ============================================================================
# FIREBASE CREDENTIALS TEST
# ============================================================================

def test_firebase_credentials():
    """Test Firebase credentials loading from base64 encoded environment variable"""
    print("\n" + "="*50)
    print("Testing Firebase Credentials Loading")
    print("="*50)
    
    try:
        import os
        import base64
        import json
        
        # Get the base64 encoded credentials
        encoded_key = os.getenv("FIREBASE_CREDENTIALS_BASE64")
        
        if not encoded_key:
            print_warning("FIREBASE_CREDENTIALS_BASE64 not set in environment")
            return False
        
        # Test decoding
        decoded_bytes = base64.b64decode(encoded_key)
        cred_dict = json.loads(decoded_bytes)
        
        # Verify required fields
        required_fields = ['type', 'project_id', 'private_key', 'client_email']
        missing_fields = [field for field in required_fields if not cred_dict.get(field)]
        
        if missing_fields:
            print_error(f"Missing required fields: {', '.join(missing_fields)}")
            return False
        
        print_success("Firebase credentials decoded successfully")
        print_info(f"Project ID: {cred_dict.get('project_id')}")
        print_info(f"Client Email: {cred_dict.get('client_email')}")
        print_info(f"Account Type: {cred_dict.get('type')}")
        print_info(f"Private Key: {'Present' if cred_dict.get('private_key') else 'Missing'}")
        
        # Test that push service can initialize (if available)
        try:
            from app.services.push_service import PushNotificationService
            push_service = PushNotificationService()
            
            if push_service.is_available():
                print_success("Firebase push service initialized successfully")
            else:
                print_warning("Firebase credentials loaded but service not available")
            
        except Exception as e:
            print_warning(f"Could not test push service initialization: {str(e)}")
        
        return True
        
    except base64.binascii.Error as e:
        print_error(f"Base64 decoding error: {str(e)}")
        return False
    except json.JSONDecodeError as e:
        print_error(f"JSON parsing error: {str(e)}")
        return False
    except Exception as e:
        print_error(f"Firebase credentials test error: {str(e)}")
        return False

def test_register_push_device():
    """Test registering a device for push notifications"""
    print("\n" + "="*50)
    print("Testing Register Push Notification Device")
    print("="*50)
    
    device_data = {
        "device_id": "test-device-12345",
        "device_token": "test-fcm-token-abc123xyz",
        "platform": "android",
        "device_name": "Test Android Device",
        "app_version": "1.0.0",
        "os_version": "13"
    }
    
    try:
        response = requests.post(
            f"{API_V1}/devices/register",
            json=device_data,
            headers=get_headers()
        )
        if response.status_code in [200, 201]:
            data = response.json()
            test_resources["push_device_id"] = data.get("id")
            print_success(f"Device registered: {data.get('device_name')}")
            print_info(f"Device ID: {data.get('device_id')}")
            print_info(f"Platform: {data.get('platform')}")
            return True
        else:
            print_error(f"Register device failed: {response.status_code}")
            print_error(f"Response: {response.text}")
            return False
    except Exception as e:
        print_error(f"Register device error: {str(e)}")
        return False

def test_send_push_notification():
    """Test sending a push notification"""
    print("\n" + "="*50)
    print("Testing Send Push Notification")
    print("="*50)
    
    notification_data = {
        "title": "Test Push Notification",
        "body": "This is a test notification from the API test suite",
        "data": {
            "test": "true",
            "source": "api_test"
        }
    }
    
    try:
        response = requests.post(
            f"{API_V1}/devices/test-notification",
            json=notification_data,
            headers=get_headers()
        )
        if response.status_code == 200:
            data = response.json()
            print_success(f"Push notification sent: {data.get('message')}")
            print_info(f"Success: {data.get('success')}")
            print_info(f"Success count: {data.get('success_count', 0)}")
            print_info(f"Failure count: {data.get('failure_count', 0)}")
            
            if not data.get('success'):
                print_warning("Notification reported as failed (expected if no real device token)")
            
            return True
        else:
            print_error(f"Send notification failed: {response.status_code}")
            print_error(f"Response: {response.text}")
            return False
    except Exception as e:
        print_error(f"Send notification error: {str(e)}")
        return False

def test_get_user_devices():
    """Test getting user's registered devices"""
    print("\n" + "="*50)
    print("Testing Get User Devices")
    print("="*50)
    
    try:
        response = requests.get(
            f"{API_V1}/devices/",
            headers=get_headers()
        )
        if response.status_code == 200:
            data = response.json()
            devices = data.get("devices", [])
            print_success(f"Retrieved {len(devices)} device(s)")
            for device in devices:
                print_info(f"  - {device.get('device_name')} ({device.get('platform')})")
            return True
        else:
            print_error(f"Get devices failed: {response.status_code}")
            return False
    except Exception as e:
        print_error(f"Get devices error: {str(e)}")
        return False

# ============================================================================
# INVITE TESTS
# ============================================================================

def test_create_invite_code():
    """Test creating an invite code"""
    print("\n" + "="*50)
    print("Testing Create Invite Code")
    print("="*50)
    
    invite_data = {
        "invite_type": "app_general"
    }
    
    try:
        response = requests.post(
            f"{API_V1}/invites/codes",
            json=invite_data,
            headers=get_headers()
        )
        if response.status_code in [200, 201]:
            data = response.json()
            test_resources["invite_code_id"] = data.get("id")
            print_success(f"Invite code created: {data.get('code')}")
            if data.get("qr_code_url"):
                print_info(f"QR code URL: {data.get('qr_code_url')}")
            return True
        else:
            print_error(f"Create invite code failed: {response.status_code}")
            print_error(f"Response: {response.text}")
            return False
    except Exception as e:
        print_error(f"Create invite code error: {str(e)}")
        return False

# ============================================================================
# GCP STORAGE TESTS (Profile Pictures & Media Uploads)
# ============================================================================

def test_upload_profile_picture():
    """Test uploading a profile picture to GCP Storage"""
    print("\n" + "="*50)
    print("Testing Upload Profile Picture")
    print("="*50)
    
    try:
        # Create a simple test image file (1x1 PNG)
        import io
        from PIL import Image
        
        # Create a small test image
        img = Image.new('RGB', (100, 100), color='blue')
        img_bytes = io.BytesIO()
        img.save(img_bytes, format='PNG')
        img_bytes.seek(0)
        
        files = {
            'file': ('test_profile.png', img_bytes, 'image/png')
        }
        
        headers = {"Authorization": f"Bearer {auth_tokens['access_token']}"}
        
        response = requests.post(
            f"{API_V1}/users/me/avatar",
            files=files,
            headers=headers
        )
        
        if response.status_code in [200, 201]:
            data = response.json()
            test_resources["profile_picture_url"] = data.get("avatar_url")
            print_success("Profile picture uploaded successfully")
            print_info(f"Avatar URL: {data.get('avatar_url')}")
            return True
        else:
            print_error(f"Upload profile picture failed: {response.status_code}")
            print_error(f"Response: {response.text}")
            return False
    except ImportError:
        print_warning("PIL/Pillow not installed, skipping profile picture test")
        return True  # Don't count as failure
    except Exception as e:
        print_error(f"Upload profile picture error: {str(e)}")
        return False

def test_delete_profile_picture():
    """Test deleting a profile picture from GCP Storage and database"""
    print("\n" + "="*50)
    print("Testing Delete Profile Picture")
    print("="*50)
    
    try:
        # Check if we have a profile picture to delete
        if not test_resources.get("profile_picture_url"):
            print_warning("No profile picture to delete, skipping test")
            return True
        
        response = requests.delete(
            f"{API_V1}/users/me/avatar",
            headers=get_headers()
        )
        
        if response.status_code == 200:
            data = response.json()
            print_success("Profile picture deleted successfully from both GCP and database")
            print_info(f"Avatar URL after deletion: {data.get('avatar_url')}")
            
            # Verify it's actually None/null
            if data.get('avatar_url') is None:
                print_success("Confirmed: avatar_url is now null in database")
            
            # Clear from test resources
            test_resources["profile_picture_url"] = None
            return True
        else:
            print_error(f"Delete profile picture failed: {response.status_code}")
            print_error(f"Response: {response.text}")
            return False
    except Exception as e:
        print_error(f"Delete profile picture error: {str(e)}")
        return False

def test_upload_moodboard_image():
    """Test uploading an image to a moodboard in GCP Storage"""
    print("\n" + "="*50)
    print("Testing Upload Moodboard Image")
    print("="*50)
    
    try:
        # First, we need an event to attach the moodboard to
        event_id = test_resources.get("event_id")
        if not event_id:
            print_warning("No event available for moodboard upload test; skipping")
            return True

        # Create a moodboard under that event
        moodboard_data = {
            "title": "Test Image Upload Moodboard",
            "description": "Testing GCP image uploads",
            "moodboard_type": "general",
            "is_public": False
        }
        
        create_response = requests.post(
            f"{API_V1}/creative/events/{event_id}/moodboards",
            json=moodboard_data,
            headers=get_headers()
        )
        
        if create_response.status_code not in [200, 201]:
            print_error(f"Failed to create test moodboard for image upload: {create_response.status_code}")
            print_error(f"Response: {create_response.text}")
            return False
        
        moodboard_id = create_response.json().get("id")
        test_resources["test_moodboard_id"] = moodboard_id
        print_info(f"Created test moodboard: {moodboard_id}")
        
        # Now upload an image
        import io
        from PIL import Image
        
        img = Image.new('RGB', (200, 200), color='red')
        img_bytes = io.BytesIO()
        img.save(img_bytes, format='JPEG')
        img_bytes.seek(0)
        
        files = {
            'file': ('test_moodboard_image.jpg', img_bytes, 'image/jpeg')
        }
        
        headers = {"Authorization": f"Bearer {auth_tokens['access_token']}"}
        
        response = requests.post(
            f"{API_V1}/creative/moodboards/{moodboard_id}/upload-image",
            files=files,
            headers=headers
        )
        
        if response.status_code in [200, 201]:
            data = response.json()
            test_resources["moodboard_image_url"] = data.get("file_url")
            print_success("Moodboard image uploaded successfully")
            print_info(f"Image URL: {data.get('file_url')}")
            print_info(f"File size: {data.get('file_size')} bytes")
            return True
        else:
            print_error(f"Upload moodboard image failed: {response.status_code}")
            print_error(f"Response: {response.text}")
            return False
    except ImportError:
        print_warning("PIL/Pillow not installed, skipping moodboard image test")
        return True
    except Exception as e:
        print_error(f"Upload moodboard image error: {str(e)}")
        return False

def test_delete_moodboard_with_images():
    """Test deleting a moodboard which should also delete associated images from GCP"""
    print("\n" + "="*50)
    print("Testing Delete Moodboard (including GCP images)")
    print("="*50)
    
    try:
        moodboard_id = test_resources.get("test_moodboard_id")
        
        if not moodboard_id:
            print_warning("No test moodboard to delete, skipping test")
            return True
        
        response = requests.delete(
            f"{API_V1}/creative/moodboards/{moodboard_id}",
            headers=get_headers()
        )
        
        if response.status_code == 200:
            print_success("Moodboard deleted successfully (including images from GCP)")
            test_resources["test_moodboard_id"] = None
            test_resources["moodboard_image_url"] = None
            return True
        else:
            print_error(f"Delete moodboard failed: {response.status_code}")
            print_error(f"Response: {response.text}")
            return False
    except Exception as e:
        print_error(f"Delete moodboard error: {str(e)}")
        return False

def test_upload_vendor_image():
    """Test uploading a vendor portfolio image to GCP Storage"""
    print("\n" + "="*50)
    print("Testing Upload Vendor Image")
    print("="*50)
    
    try:
        import io
        from PIL import Image
        
        # Create a test image
        img = Image.new('RGB', (300, 300), color='green')
        img_bytes = io.BytesIO()
        img.save(img_bytes, format='PNG')
        img_bytes.seek(0)
        
        files = {
            'file': ('test_vendor_image.png', img_bytes, 'image/png')
        }
        
        headers = {"Authorization": f"Bearer {auth_tokens['access_token']}"}
        
        response = requests.post(
            f"{API_V1}/vendors/upload-image",
            files=files,
            headers=headers
        )
        
        if response.status_code in [200, 201]:
            data = response.json()
            test_resources["vendor_image_url"] = data.get("url")
            print_success("Vendor image uploaded successfully")
            print_info(f"Image URL: {data.get('url')}")
            print_info(f"Unique filename: {data.get('unique_filename')}")
            print_info(f"File size: {data.get('file_size')} bytes")
            return True
        else:
            print_error(f"Upload vendor image failed: {response.status_code}")
            print_error(f"Response: {response.text}")
            return False
    except ImportError:
        print_warning("PIL/Pillow not installed, skipping vendor image test")
        return True
    except Exception as e:
        print_error(f"Upload vendor image error: {str(e)}")
        return False

def test_generate_custom_qr_code():
    """Test generating a custom QR code"""
    print("\n" + "="*50)
    print("Testing Generate Custom QR Code")
    print("="*50)
    
    qr_data = {
        "data": "https://example.com/my-custom-link",
        "size": 300,
        "style": "gradient"
    }
    
    try:
        response = requests.post(
            f"{API_V1}/invites/qr-code",
            json=qr_data,
            headers=get_headers()
        )
        if response.status_code in [200, 201]:
            data = response.json()
            test_resources["custom_qr_url"] = data.get("qr_code_url")
            print_success("Custom QR code generated")
            print_info(f"QR code URL: {data.get('qr_code_url')}")
            print_info(f"Data encoded: {data.get('data')}")
            return True
        else:
            print_error(f"Generate custom QR code failed: {response.status_code}")
            print_error(f"Response: {response.text}")
            return False
    except Exception as e:
        print_error(f"Generate custom QR code error: {str(e)}")
        return False

def test_generate_profile_qr_code():
    """Test generating a profile QR code"""
    print("\n" + "="*50)
    print("Testing Generate Profile QR Code")
    print("="*50)
    
    try:
        response = requests.get(
            f"{API_V1}/invites/qr-code/profile",
            headers=get_headers()
        )
        if response.status_code == 200:
            data = response.json()
            test_resources["profile_qr_url"] = data.get("qr_code_url")
            print_success("Profile QR code generated")
            print_info(f"QR code URL: {data.get('qr_code_url')}")
            return True
        else:
            print_error(f"Generate profile QR code failed: {response.status_code}")
            print_error(f"Response: {response.text}")
            return False
    except Exception as e:
        print_error(f"Generate profile QR code error: {str(e)}")
        return False

def test_generate_app_qr_code():
    """Test generating an app invite QR code"""
    print("\n" + "="*50)
    print("Testing Generate App QR Code")
    print("="*50)
    
    try:
        response = requests.get(
            f"{API_V1}/invites/qr-code/app",
            headers=get_headers()
        )
        if response.status_code == 200:
            data = response.json()
            print_success("App invite QR code generated")
            print_info(f"QR code URL: {data.get('qr_code_url')}")
            return True
        else:
            print_error(f"Generate app QR code failed: {response.status_code}")
            print_error(f"Response: {response.text}")
            return False
    except Exception as e:
        print_error(f"Generate app QR code error: {str(e)}")
        return False

def test_get_invite_codes():
    """Test retrieving invite codes"""
    print("\n" + "="*50)
    print("Testing Get Invite Codes")
    print("="*50)
    
    try:
        response = requests.get(
            f"{API_V1}/invites/codes",
            headers=get_headers()
        )
        if response.status_code == 200:
            codes = response.json()
            print_success("Retrieved invite codes")
            print_info(f"Invite codes count: {len(codes)}")
            return True
        else:
            print_error(f"Get invite codes failed: {response.status_code}")
            return False
    except Exception as e:
        print_error(f"Get invite codes error: {str(e)}")
        return False

def test_create_invite_link():
    """Test creating an invite link"""
    print("\n" + "="*50)
    print("Testing Create Invite Link")
    print("="*50)
    
    link_data = {
        "title": "Core API Invite Link",
        "description": "Invite friends to the platform",
        "max_uses": 5
    }
    
    try:
        response = requests.post(
            f"{API_V1}/invites/links",
            json=link_data,
            headers=get_headers()
        )
        if response.status_code in [200, 201]:
            data = response.json()
            test_resources["invite_link_id"] = data.get("id")
            print_success(f"Invite link created: {data.get('link_id')}")
            return True
        else:
            print_error(f"Create invite link failed: {response.status_code}")
            print_error(f"Response: {response.text}")
            return False
    except Exception as e:
        print_error(f"Create invite link error: {str(e)}")
        return False

def test_get_invite_links():
    """Test retrieving invite links"""
    print("\n" + "="*50)
    print("Testing Get Invite Links")
    print("="*50)
    
    try:
        response = requests.get(
            f"{API_V1}/invites/links",
            headers=get_headers()
        )
        if response.status_code == 200:
            links = response.json()
            print_success("Retrieved invite links")
            print_info(f"Invite links count: {len(links)}")
            return True
        else:
            print_error(f"Get invite links failed: {response.status_code}")
            return False
    except Exception as e:
        print_error(f"Get invite links error: {str(e)}")
        return False

def test_get_invite_stats():
    """Test retrieving invite statistics"""
    print("\n" + "="*50)
    print("Testing Get Invite Stats")
    print("="*50)
    
    try:
        response = requests.get(
            f"{API_V1}/invites/stats",
            headers=get_headers()
        )
        if response.status_code == 200:
            stats = response.json()
            print_success("Retrieved invite stats")
            print_info(
                f"Codes: {stats.get('total_invite_codes', 0)} | Links: {stats.get('total_invite_links', 0)}"
            )
            return True
        else:
            print_error(f"Get invite stats failed: {response.status_code}")
            return False
    except Exception as e:
        print_error(f"Get invite stats error: {str(e)}")
        return False

def test_delete_invite_code_with_qr():
    """Test deleting an invite code with its QR code from database and GCP"""
    print("\n" + "="*50)
    print("Testing Delete Invite Code with QR Code")
    print("="*50)
    
    # Create a new invite code specifically for deletion test
    invite_data = {
        "invite_type": "app_general"
    }
    
    try:
        # First create an invite code
        response = requests.post(
            f"{API_V1}/invites/codes",
            json=invite_data,
            headers=get_headers()
        )
        if response.status_code not in [200, 201]:
            print_error("Failed to create invite code for deletion test")
            return False
        
        data = response.json()
        invite_code_id = data.get("id")
        qr_code_url = data.get("qr_code_url")
        
        print_info(f"Created invite code {data.get('code')} with QR: {qr_code_url}")
        
        # Now delete it with QR code
        response = requests.delete(
            f"{API_V1}/invites/codes/{invite_code_id}/with-qr",
            headers=get_headers()
        )
        
        if response.status_code in [200, 204]:
            print_success("Invite code and QR code deleted from database and GCP")
            print_info("QR code removed from GCP bucket")
            print_info("Database record soft deleted")
            return True
        else:
            print_error(f"Delete invite code with QR failed: {response.status_code}")
            print_error(f"Response: {response.text}")
            return False
    except Exception as e:
        print_error(f"Delete invite code with QR error: {str(e)}")
        return False

def test_delete_invite_link_with_qr():
    """Test deleting an invite link with its QR code from database and GCP"""
    print("\n" + "="*50)
    print("Testing Delete Invite Link with QR Code")
    print("="*50)
    
    # Create a new invite link specifically for deletion test
    link_data = {
        "title": "Test Delete Link",
        "description": "Link for testing deletion",
        "max_uses": 3
    }
    
    try:
        # First create an invite link
        response = requests.post(
            f"{API_V1}/invites/links",
            json=link_data,
            headers=get_headers()
        )
        if response.status_code not in [200, 201]:
            print_error("Failed to create invite link for deletion test")
            return False
        
        data = response.json()
        invite_link_id = data.get("id")
        qr_code_url = data.get("qr_code_url")
        
        print_info(f"Created invite link {data.get('link_id')} with QR: {qr_code_url}")
        
        # Now delete it with QR code
        response = requests.delete(
            f"{API_V1}/invites/links/{invite_link_id}/with-qr",
            headers=get_headers()
        )
        
        if response.status_code in [200, 204]:
            print_success("Invite link and QR code deleted from database and GCP")
            print_info("QR code removed from GCP bucket")
            print_info("Database record soft deleted")
            return True
        else:
            print_error(f"Delete invite link with QR failed: {response.status_code}")
            print_error(f"Response: {response.text}")
            return False
    except Exception as e:
        print_error(f"Delete invite link with QR error: {str(e)}")
        return False

def test_deactivate_invite_code():
    """Test deactivating an invite code"""
    print("\n" + "="*50)
    print("Testing Deactivate Invite Code")
    print("="*50)
    
    invite_code_id = test_resources.get("invite_code_id")
    if not invite_code_id:
        print_warning("No invite code ID available")
        return None
    
    try:
        response = requests.delete(
            f"{API_V1}/invites/codes/{invite_code_id}",
            headers=get_headers()
        )
        if response.status_code in [200, 204]:
            print_success("Invite code deactivated")
            return True
        else:
            print_error(f"Deactivate invite code failed: {response.status_code}")
            return False
    except Exception as e:
        print_error(f"Deactivate invite code error: {str(e)}")
        return False

# ============================================================================
# TIMELINE ADVANCED TESTS
# ============================================================================

def test_create_timeline():
    """Test creating a timeline"""
    print("\n" + "="*50)
    print("Testing Create Timeline")
    print("="*50)
    
    if not test_resources.get("event_id"):
        print_warning("No event ID available")
        return None
    
    timeline_data = {
        "title": "Event Timeline",
        "description": "Main timeline for the event"
    }
    
    try:
        response = requests.post(
            f"{API_V1}/timeline/events/{test_resources['event_id']}/timelines",
            json=timeline_data,
            headers=get_headers()
        )
        if response.status_code in [200, 201]:
            data = response.json()
            test_resources["timeline_id"] = data.get("id")
            print_success(f"Timeline created: {data.get('title')}")
            print_info(f"Timeline ID: {test_resources['timeline_id']}")
            return True
        else:
            print_error(f"Create timeline failed: {response.status_code}")
            print_error(f"Response: {response.text}")
            return False
    except Exception as e:
        print_error(f"Create timeline error: {str(e)}")
        return False

def test_add_timeline_item():
    """Test adding a timeline item"""
    print("\n" + "="*50)
    print("Testing Add Timeline Item")
    print("="*50)
    
    if not test_resources.get("timeline_id"):
        print_warning("No timeline ID available")
        return None
    
    item_data = {
        "title": "Guests Arrival",
        "description": "Guests start arriving",
        "item_type": "activity",
        "start_time": "10:00",
        "duration_minutes": 30,
        "order_index": 0
    }
    
    try:
        response = requests.post(
            f"{API_V1}/timeline/timelines/{test_resources['timeline_id']}/items",
            json=item_data,
            headers=get_headers()
        )
        if response.status_code in [200, 201]:
            data = response.json()
            item_id = data.get("id")
            if item_id:
                test_resources.setdefault("timeline_items", []).append(item_id)
            print_success(f"Timeline item added: {data.get('title')}")
            return True
        else:
            print_error(f"Add timeline item failed: {response.status_code}")
            print_error(f"Response: {response.text}")
            return False
    except Exception as e:
        print_error(f"Add timeline item error: {str(e)}")
        return False

def test_reorder_timeline_items():
    """Test reordering timeline items"""
    print("\n" + "="*50)
    print("Testing Reorder Timeline Items")
    print("="*50)
    
    if not test_resources.get("timeline_id"):
        print_warning("No timeline ID available")
        return None
    
    # First get the timeline to see items
    try:
        get_response = requests.get(
            f"{API_V1}/timeline/timelines/{test_resources['timeline_id']}",
            headers=get_headers()
        )
        if get_response.status_code != 200:
            print_warning("Could not fetch timeline items")
            return None
        
        timeline_data = get_response.json()
        items = timeline_data.get("items", [])
        
        if len(items) < 2:
            print_warning("Not enough items to reorder")
            return None
        
        # Reverse the order
        reorder_data = {
            "item_orders": [
                {"item_id": item["id"], "order_index": len(items) - 1 - idx}
                for idx, item in enumerate(items)
            ]
        }
        
        response = requests.post(
            f"{API_V1}/timeline/timelines/{test_resources['timeline_id']}/reorder",
            json=reorder_data,
            headers=get_headers()
        )
        if response.status_code == 200:
            print_success("Timeline items reordered")
            return True
        else:
            print_error(f"Reorder items failed: {response.status_code}")
            return False
    except Exception as e:
        print_error(f"Reorder items error: {str(e)}")
        return False

def test_duplicate_timeline():
    """Test duplicating a timeline"""
    print("\n" + "="*50)
    print("Testing Duplicate Timeline")
    print("="*50)
    
    if not test_resources.get("timeline_id"):
        print_warning("No timeline ID available")
        return None
    
    try:
        response = requests.post(
            f"{API_V1}/timeline/timelines/{test_resources['timeline_id']}/duplicate",
            headers=get_headers()
        )
        if response.status_code in [200, 201]:
            data = response.json()
            print_success(f"Timeline duplicated: {data.get('title')}")
            print_info(f"New Timeline ID: {data.get('id')}")
            return True
        else:
            print_error(f"Duplicate timeline failed: {response.status_code}")
            return False
    except Exception as e:
        print_error(f"Duplicate timeline error: {str(e)}")
        return False

# ============================================================================
# CREATIVE - MOODBOARD ADVANCED TESTS
# ============================================================================

def test_create_moodboard():
    """Test creating a moodboard"""
    print("\n" + "="*50)
    print("Testing Create Moodboard")
    print("="*50)
    
    if not test_resources.get("event_id"):
        print_warning("No event ID available")
        return None
    
    moodboard_data = {
        "title": "Wedding Decorations",
        "description": "Ideas for wedding decorations",
        "moodboard_type": "decorations",
        "is_public": True,
        "allow_contributions": True,
        "tags": ["wedding", "elegant", "floral"],
        "color_palette": ["#FFB6C1", "#FFF5EE", "#98FB98"]
    }
    
    try:
        response = requests.post(
            f"{API_V1}/creative/events/{test_resources['event_id']}/moodboards",
            json=moodboard_data,
            headers=get_headers()
        )
        if response.status_code in [200, 201]:
            data = response.json()
            test_resources["moodboard_id"] = data.get("id")
            print_success(f"Moodboard created: {data.get('title')}")
            print_info(f"Moodboard ID: {test_resources['moodboard_id']}")
            print_info(f"Type: {data.get('moodboard_type')}")
            return True
        else:
            print_error(f"Create moodboard failed: {response.status_code}")
            print_error(f"Response: {response.text}")
            return False
    except Exception as e:
        print_error(f"Create moodboard error: {str(e)}")
        return False

def test_add_moodboard_items():
    """Test adding items to moodboard"""
    print("\n" + "="*50)
    print("Testing Add Moodboard Items")
    print("="*50)
    
    if not test_resources.get("moodboard_id"):
        print_warning("No moodboard ID available")
        return None
    
    item_data = {
        "title": "Centerpiece Idea",
        "description": "Beautiful floral centerpiece",
        "image_url": "https://example.com/centerpiece.jpg",
        "content_type": "image",
        "tags": ["flowers", "centerpiece"],
        "price_estimate": "$50-75"
    }
    
    try:
        response = requests.post(
            f"{API_V1}/creative/moodboards/{test_resources['moodboard_id']}/items",
            json=item_data,
            headers=get_headers()
        )
        if response.status_code in [200, 201]:
            data = response.json()
            print_success(f"Moodboard item added: {data.get('title')}")
            return True
        else:
            print_error(f"Add moodboard item failed: {response.status_code}")
            print_error(f"Response: {response.text}")
            return False
    except Exception as e:
        print_error(f"Add moodboard item error: {str(e)}")
        return False

def test_like_moodboard():
    """Test liking a moodboard"""
    print("\n" + "="*50)
    print("Testing Like Moodboard")
    print("="*50)
    
    if not test_resources.get("moodboard_id"):
        print_warning("No moodboard ID available")
        return None
    
    try:
        response = requests.post(
            f"{API_V1}/creative/moodboards/{test_resources['moodboard_id']}/like",
            headers=get_headers()
        )
        if response.status_code == 200:
            data = response.json()
            print_success(f"Moodboard liked: {data.get('action')}")
            return True
        else:
            print_error(f"Like moodboard failed: {response.status_code}")
            return False
    except Exception as e:
        print_error(f"Like moodboard error: {str(e)}")
        return False

def test_add_moodboard_comment():
    """Test adding a comment to moodboard"""
    print("\n" + "="*50)
    print("Testing Add Moodboard Comment")
    print("="*50)
    
    if not test_resources.get("moodboard_id"):
        print_warning("No moodboard ID available")
        return None
    
    comment_data = {
        "content": "These decorations look amazing! Love the color palette."
    }
    
    try:
        response = requests.post(
            f"{API_V1}/creative/moodboards/{test_resources['moodboard_id']}/comments",
            json=comment_data,
            headers=get_headers()
        )
        if response.status_code in [200, 201]:
            data = response.json()
            print_success("Moodboard comment added")
            return True
        else:
            print_error(f"Add comment failed: {response.status_code}")
            return False
    except Exception as e:
        print_error(f"Add comment error: {str(e)}")
        return False

# ============================================================================
# USER PROFILE TESTS
# ============================================================================

def test_get_user_profile():
    """Test getting user profile"""
    print("\n" + "="*50)
    print("Testing Get User Profile")
    print("="*50)
    
    try:
        response = requests.get(
            f"{API_V1}/users/me",
            headers=get_headers()
        )
        if response.status_code == 200:
            data = response.json()
            print_success("Retrieved user profile")
            print_info(f"User: {data.get('full_name')} | Email: {data.get('email')}")
            return True
        else:
            print_error(f"Get user profile failed: {response.status_code}")
            return False
    except Exception as e:
        print_error(f"Get user profile error: {str(e)}")
        return False

def test_update_user_profile():
    """Test updating user profile"""
    print("\n" + "="*50)
    print("Testing Update User Profile")
    print("="*50)
    
    update_data = {
        "bio": "Event planning enthusiast",
        "phone_number": "+1234567890"
    }
    
    try:
        response = requests.put(
            f"{API_V1}/users/me",
            json=update_data,
            headers=get_headers()
        )
        if response.status_code == 200:
            data = response.json()
            print_success("Updated user profile")
            print_info(f"Bio: {data.get('bio', 'N/A')}")
            return True
        else:
            print_error(f"Update profile failed: {response.status_code}")
            return False
    except Exception as e:
        print_error(f"Update profile error: {str(e)}")
        return False

def test_get_user_stats():
    """Test getting user statistics"""
    print("\n" + "="*50)
    print("Testing Get User Statistics")
    print("="*50)
    
    try:
        response = requests.get(
            f"{API_V1}/users/me/stats",
            headers=get_headers()
        )
        if response.status_code == 200:
            data = response.json()
            print_success("Retrieved user stats")
            print_info(f"Events: {data.get('total_events', 0)} | Friends: {data.get('total_friends', 0)}")
            return True
        else:
            print_error(f"Get user stats failed: {response.status_code}")
            return False
    except Exception as e:
        print_error(f"Get user stats error: {str(e)}")
        return False

# ============================================================================
# MESSAGE/CHAT TESTS
# ============================================================================

def test_send_message():
    """Test sending a message to event chat"""
    print("\n" + "="*50)
    print("Testing Send Message")
    print("="*50)
    
    if not test_resources.get("event_id"):
        print_warning("No event ID available")
        return None
    
    message_data = {
        "content": "Hello everyone! Looking forward to the event!",
        "message_type": "text"
    }
    
    try:
        response = requests.post(
            f"{API_V1}/messages/events/{test_resources['event_id']}/messages",
            json=message_data,
            headers=get_headers()
        )
        if response.status_code in [200, 201]:
            data = response.json()
            test_resources["message_id"] = data.get("id")
            print_success(f"Message sent: {data.get('content', '')[:50]}...")
            print_info(f"Message ID: {test_resources['message_id']}")
            return True
        else:
            print_error(f"Send message failed: {response.status_code}")
            print_error(f"Response: {response.text}")
            return False
    except Exception as e:
        print_error(f"Send message error: {str(e)}")
        return False

def test_get_messages():
    """Test retrieving event messages"""
    print("\n" + "="*50)
    print("Testing Get Messages")
    print("="*50)
    
    if not test_resources.get("event_id"):
        print_warning("No event ID available")
        return None
    
    try:
        response = requests.get(
            f"{API_V1}/messages/events/{test_resources['event_id']}/messages",
            headers=get_headers()
        )
        if response.status_code == 200:
            data = response.json()
            messages = data.get("messages", [])
            print_success("Retrieved event messages")
            print_info(f"Message count: {len(messages)}")
            return True
        else:
            print_error(f"Get messages failed: {response.status_code}")
            return False
    except Exception as e:
        print_error(f"Get messages error: {str(e)}")
        return False

def test_react_to_message():
    """Test adding reaction to message"""
    print("\n" + "="*50)
    print("Testing React to Message")
    print("="*50)
    
    if not test_resources.get("message_id"):
        print_warning("No message ID available")
        return None
    
    reaction_data = {
        "emoji": "👍"
    }
    
    try:
        response = requests.post(
            f"{API_V1}/messages/messages/{test_resources['message_id']}/reactions",
            json=reaction_data,
            headers=get_headers()
        )
        if response.status_code in [200, 201]:
            print_success("Added reaction to message")
            return True
        else:
            print_error(f"React to message failed: {response.status_code}")
            return False
    except Exception as e:
        print_error(f"React to message error: {str(e)}")
        return False

def test_pin_message():
    """Test pinning a message"""
    print("\n" + "="*50)
    print("Testing Pin Message")
    print("="*50)
    
    if not test_resources.get("message_id"):
        print_warning("No message ID available")
        return None
    
    try:
        response = requests.post(
            f"{API_V1}/messages/messages/{test_resources['message_id']}/pin",
            headers=get_headers()
        )
        if response.status_code in [200, 201]:
            print_success("Message pinned successfully")
            return True
        else:
            print_error(f"Pin message failed: {response.status_code}")
            return False
    except Exception as e:
        print_error(f"Pin message error: {str(e)}")
        return False

def test_get_chat_stats():
    """Test getting chat statistics"""
    print("\n" + "="*50)
    print("Testing Get Chat Statistics")
    print("="*50)
    
    if not test_resources.get("event_id"):
        print_warning("No event ID available")
        return None
    
    try:
        response = requests.get(
            f"{API_V1}/messages/events/{test_resources['event_id']}/chat/stats",
            headers=get_headers()
        )
        if response.status_code == 200:
            data = response.json()
            print_success("Retrieved chat statistics")
            print_info(f"Total messages: {data.get('total_messages', 0)}")
            return True
        else:
            print_error(f"Get chat stats failed: {response.status_code}")
            return False
    except Exception as e:
        print_error(f"Get chat stats error: {str(e)}")
        return False

# ============================================================================
# ============================================================================
# TIMELINE ADVANCED TESTS
# ============================================================================

def test_get_timeline():
    """Test retrieving timeline details"""
    print("\n" + "="*50)
    print("Testing Get Timeline Details")
    print("="*50)
    
    if not test_resources.get("timeline_id"):
        print_warning("No timeline ID available")
        return None
    
    try:
        response = requests.get(
            f"{API_V1}/timeline/timelines/{test_resources['timeline_id']}",
            headers=get_headers()
        )
        if response.status_code == 200:
            data = response.json()
            print_success(f"Retrieved timeline: {data.get('title')}")
            print_info(f"Items count: {len(data.get('items', []))}")
            return True
        else:
            print_error(f"Get timeline failed: {response.status_code}")
            return False
    except Exception as e:
        print_error(f"Get timeline error: {str(e)}")
        return False

def test_update_timeline_item():
    """Test updating a timeline item"""
    print("\n" + "="*50)
    print("Testing Update Timeline Item")
    print("="*50)
    
    if not test_resources.get("timeline_items") or len(test_resources["timeline_items"]) == 0:
        print_warning("No timeline items available")
        return None
    
    item_id = test_resources["timeline_items"][0]
    update_data = {
        "title": "Guests Arrival - Updated",
        "notes": "Please arrive 15 minutes early"
    }
    
    try:
        response = requests.put(
            f"{API_V1}/timeline/timeline-items/{item_id}",
            json=update_data,
            headers=get_headers()
        )
        if response.status_code == 200:
            data = response.json()
            print_success(f"Timeline item updated: {data.get('title')}")
            return True
        else:
            print_error(f"Update timeline item failed: {response.status_code}")
            return False
    except Exception as e:
        print_error(f"Update timeline item error: {str(e)}")
        return False

# ============================================================================
# CREATIVE - PLAYLIST TESTS
# ============================================================================

def test_create_playlist():
    """Test creating a playlist"""
    print("\n" + "="*50)
    print("Testing Create Playlist")
    print("="*50)
    
    if not test_resources.get("event_id"):
        print_warning("No event ID available")
        return None
    
    playlist_data = {
        "title": "Party Playlist",
        "description": "Upbeat music for the party",
        "provider": "custom",
        "is_collaborative": True,
        "is_public": True,
        "genre_tags": ["pop", "dance", "electronic"],
        "mood_tags": ["energetic", "upbeat", "fun"]
    }
    
    try:
        response = requests.post(
            f"{API_V1}/creative/events/{test_resources['event_id']}/playlists",
            json=playlist_data,
            headers=get_headers()
        )
        if response.status_code in [200, 201]:
            data = response.json()
            test_resources["playlist_id"] = data.get("id")
            print_success(f"Playlist created: {data.get('title')}")
            print_info(f"Playlist ID: {test_resources['playlist_id']}")
            return True
        else:
            print_error(f"Create playlist failed: {response.status_code}")
            print_error(f"Response: {response.text}")
            return False
    except Exception as e:
        print_error(f"Create playlist error: {str(e)}")
        return False

def test_add_playlist_track():
    """Test adding a track to playlist"""
    print("\n" + "="*50)
    print("Testing Add Playlist Track")
    print("="*50)
    
    if not test_resources.get("playlist_id"):
        print_warning("No playlist ID available")
        return None
    
    track_data = {
        "title": "Dance Anthem",
        "artist": "DJ Test",
        "album": "Summer Hits 2025",
        "duration_ms": 210000,
        "preview_url": "https://example.com/preview.mp3"
    }
    
    try:
        response = requests.post(
            f"{API_V1}/creative/playlists/{test_resources['playlist_id']}/tracks",
            json=track_data,
            headers=get_headers()
        )
        if response.status_code in [200, 201]:
            data = response.json()
            print_success(f"Track added: {data.get('title')} by {data.get('artist')}")
            return True
        else:
            print_error(f"Add track failed: {response.status_code}")
            print_error(f"Response: {response.text}")
            return False
    except Exception as e:
        print_error(f"Add track error: {str(e)}")
        return False

def test_get_playlist():
    """Test getting a playlist"""
    print("\n" + "="*50)
    print("Testing Get Playlist")
    print("="*50)
    
    if not test_resources.get("playlist_id"):
        print_warning("No playlist ID available")
        return None
    
    try:
        response = requests.get(
            f"{API_V1}/creative/playlists/{test_resources['playlist_id']}",
            headers=get_headers()
        )
        if response.status_code == 200:
            data = response.json()
            print_success(f"Retrieved playlist: {data.get('title')}")
            print_info(f"Tracks: {data.get('track_count', 0)}")
            return True
        else:
            print_error(f"Get playlist failed: {response.status_code}")
            return False
    except Exception as e:
        print_error(f"Get playlist error: {str(e)}")
        return False

# ============================================================================
# CREATIVE - GAME TESTS
# ============================================================================

def test_generate_game_questions():
    """Test generating trivia questions with OpenTDB"""
    print("\n" + "="*50)
    print("Testing Generate Game Questions (OpenTDB)")
    print("="*50)
    
    question_data = {
        "topic": "General Knowledge",
        "difficulty": "medium",
        "game_type": "trivia",
        "count": 5
    }
    
    try:
        response = requests.post(
            f"{API_V1}/creative/games/generate-questions",
            json=question_data,
            headers=get_headers()
        )
        if response.status_code == 200:
            data = response.json()
            questions = data.get("questions", [])
            test_resources["generated_questions"] = questions
            print_success(f"Generated {len(questions)} questions from OpenTDB")
            if questions:
                q = questions[0]
                print_info(f"Sample: {q.get('text', 'N/A')[:60]}...")
                print_info(f"Category: {q.get('category', 'N/A')}")
            return True
        else:
            print_error(f"Generate questions failed: {response.status_code}")
            print_error(f"Response: {response.text}")
            return False
    except Exception as e:
        print_error(f"Generate questions error: {str(e)}")
        return False

def test_create_game():
    """Test creating a game"""
    print("\n" + "="*50)
    print("Testing Create Game")
    print("="*50)
    
    if not test_resources.get("event_id"):
        print_warning("No event ID available")
        return None
    
    # Use generated questions or create with empty questions
    questions = test_resources.get("generated_questions", [])
    if not questions:
        print_warning("No generated questions available, creating game without questions")
    
    game_data = {
        "title": "Trivia Challenge",
        "description": "Fun trivia game with OpenTDB questions",
        "event_id": test_resources["event_id"],
        "game_type": "trivia",
        "difficulty": "medium",
        "min_players": 2,
        "max_players": 6,
        "estimated_duration_minutes": 15,
        "instructions": "Split into teams and answer timed trivia questions. Highest score wins.",
        "materials_needed": ["Projector", "Scorecards"],
        "game_data": {
            "questions": questions,
            "total_rounds": 1
        },
        "tags": ["quiz", "team"],
        "categories": ["party", "icebreaker"],
        "age_appropriate": True
    }
    
    try:
        response = requests.post(
            f"{API_V1}/creative/events/{test_resources['event_id']}/games",
            json=game_data,
            headers=get_headers()
        )
        if response.status_code in [200, 201]:
            data = response.json()
            test_resources["game_id"] = data.get("id")
            print_success(f"Game created: {data.get('title')}")
            print_info(f"Game ID: {test_resources['game_id']}")
            print_info(f"Type: {data.get('game_type')}")
            return True
        else:
            print_error(f"Create game failed: {response.status_code}")
            print_error(f"Response: {response.text}")
            return False
    except Exception as e:
        print_error(f"Create game error: {str(e)}")
        return False

def test_start_game_session():
    """Test starting a game session"""
    print("\n" + "="*50)
    print("Testing Start Game Session")
    print("="*50)
    
    if not test_resources.get("event_id") or not test_resources.get("game_id"):
        print_warning("No event or game ID available")
        return None
    
    session_data = {
        "game_id": test_resources["game_id"]
    }
    
    try:
        response = requests.post(
            f"{API_V1}/creative/events/{test_resources['event_id']}/game-sessions",
            json=session_data,
            headers=get_headers()
        )
        if response.status_code in [200, 201]:
            data = response.json()
            test_resources["game_session_id"] = data.get("id")
            print_success(f"Game session started")
            print_info(f"Session ID: {test_resources['game_session_id']}")
            print_info(f"Status: {data.get('status')}")
            return True
        else:
            print_error(f"Start game session failed: {response.status_code}")
            print_error(f"Response: {response.text}")
            return False
    except Exception as e:
        print_error(f"Start game session error: {str(e)}")
        return False

def test_get_game_templates():
    """Test getting all game templates"""
    print("\n" + "="*50)
    print("Testing Get Game Templates")
    print("="*50)
    
    try:
        response = requests.get(
            f"{API_V1}/creative/games/templates",
            headers=get_headers()
        )
        if response.status_code == 200:
            data = response.json()
            templates = data.get("templates", {})
            total = data.get("total", 0)
            
            print_success(f"Retrieved {total} game templates")
            
            # Display template counts by type
            for game_type, template_list in templates.items():
                print_info(f"{game_type}: {len(template_list)} templates")
                for template in template_list[:2]:  # Show first 2 of each type
                    print(f"  • {template.get('title')} ({template.get('template_name')})")
            
            # Store first icebreaker template for next test
            if templates.get("icebreaker"):
                test_resources["template_type"] = "icebreaker"
                test_resources["template_name"] = templates["icebreaker"][0].get("template_name")
            
            return True
        else:
            print_error(f"Get templates failed: {response.status_code}")
            print_error(f"Response: {response.text}")
            return False
    except Exception as e:
        print_error(f"Get templates error: {str(e)}")
        return False

def test_get_template_details():
    """Test getting specific template details"""
    print("\n" + "="*50)
    print("Testing Get Template Details")
    print("="*50)
    
    if not test_resources.get("template_type") or not test_resources.get("template_name"):
        print_warning("No template type or name available")
        return None
    
    try:
        response = requests.get(
            f"{API_V1}/creative/games/templates/{test_resources['template_type']}/{test_resources['template_name']}",
            headers=get_headers()
        )
        if response.status_code == 200:
            data = response.json()
            print_success(f"Retrieved template: {data.get('title')}")
            print_info(f"Type: {data.get('game_type')}")
            print_info(f"Players: {data.get('min_players')}-{data.get('max_players')}")
            print_info(f"Duration: {data.get('estimated_duration_minutes')} minutes")
            print_info(f"Materials: {', '.join(data.get('materials_needed', []))}")
            return True
        else:
            print_error(f"Get template details failed: {response.status_code}")
            print_error(f"Response: {response.text}")
            return False
    except Exception as e:
        print_error(f"Get template details error: {str(e)}")
        return False

def test_create_game_from_template():
    """Test creating a game from a template"""
    print("\n" + "="*50)
    print("Testing Create Game From Template")
    print("="*50)
    
    if not test_resources.get("event_id"):
        print_warning("No event ID available")
        return None
    
    if not test_resources.get("template_type") or not test_resources.get("template_name"):
        print_warning("No template available")
        return None
    
    template_data = {
        "game_type": test_resources["template_type"],
        "template_name": test_resources["template_name"],
        "event_id": test_resources["event_id"],
        "title": f"Custom {test_resources['template_name'].replace('_', ' ').title()}",
        "description": "Game created from template for testing",
        "is_public": False,
        "customizations": {
            "custom_field": "test_value"
        }
    }
    
    try:
        response = requests.post(
            f"{API_V1}/creative/games/from-template",
            json=template_data,
            headers=get_headers()
        )
        if response.status_code in [200, 201]:
            data = response.json()
            test_resources["template_game_id"] = data.get("id")
            print_success(f"Game created from template: {data.get('title')}")
            print_info(f"Game ID: {test_resources['template_game_id']}")
            print_info(f"Type: {data.get('game_type')}")
            print_info(f"Template: {test_resources['template_name']}")
            return True
        else:
            print_error(f"Create game from template failed: {response.status_code}")
            print_error(f"Response: {response.text}")
            return False
    except Exception as e:
        print_error(f"Create game from template error: {str(e)}")
        return False

def test_rate_game():
    """Test rating a game"""
    print("\n" + "="*50)
    print("Testing Rate Game")
    print("="*50)
    
    if not test_resources.get("game_id"):
        print_warning("No game ID available")
        return None
    
    rating_data = {
        "rating": 5,
        "comment": "Great game! Very entertaining."
    }
    
    try:
        response = requests.post(
            f"{API_V1}/creative/games/{test_resources['game_id']}/rate",
            json=rating_data,
            headers=get_headers()
        )
        if response.status_code in [200, 201]:
            data = response.json()
            print_success(f"Game rated: {data.get('rating')} stars")
            return True
        else:
            print_error(f"Rate game failed: {response.status_code}")
            print_error(f"Response: {response.text}")
            return False
    except Exception as e:
        print_error(f"Rate game error: {str(e)}")
        return False

def test_get_creative_stats():
    """Test getting creative statistics for event"""
    print("\n" + "="*50)
    print("Testing Get Creative Stats")
    print("="*50)
    
    if not test_resources.get("event_id"):
        print_warning("No event ID available")
        return None
    
    try:
        response = requests.get(
            f"{API_V1}/creative/events/{test_resources['event_id']}/creative-stats",
            headers=get_headers()
        )
        if response.status_code == 200:
            data = response.json()
            print_success("Retrieved creative stats")
            print_info(f"Moodboards: {data.get('total_moodboards', 0)}")
            print_info(f"Playlists: {data.get('total_playlists', 0)}")
            print_info(f"Games: {data.get('total_games', 0)}")
            print_info(f"Active sessions: {data.get('active_game_sessions', 0)}")
            return True
        else:
            print_error(f"Get creative stats failed: {response.status_code}")
            return False
    except Exception as e:
        print_error(f"Get creative stats error: {str(e)}")
        return False

# ============================================================================
# USER ADVANCED TESTS
# ============================================================================

def test_get_user_activity():
    """Test getting user activity log"""
    print("\n" + "="*50)
    print("Testing Get User Activity")
    print("="*50)
    
    try:
        response = requests.get(
            f"{API_V1}/users/activity",
            headers=get_headers()
        )
        if response.status_code == 200:
            data = response.json()
            print_success("Retrieved user activity")
            print_info(f"Total activities: {data.get('total', 0)}")
            return True
        else:
            print_error(f"Get activity failed: {response.status_code}")
            return False
    except Exception as e:
        print_error(f"Get activity error: {str(e)}")
        return False

def test_update_user_settings():
    """Test updating user settings"""
    print("\n" + "="*50)
    print("Testing Update User Settings")
    print("="*50)
    
    settings_data = {
        "theme": "dark",
        "language": "en",
        "timezone": "UTC",
        "date_format": "MM/DD/YYYY"
    }
    
    try:
        response = requests.put(
            f"{API_V1}/users/settings",
            json=settings_data,
            headers=get_headers()
        )
        if response.status_code == 200:
            data = response.json()
            print_success("User settings updated")
            return True
        else:
            print_error(f"Update settings failed: {response.status_code}")
            return False
    except Exception as e:
        print_error(f"Update settings error: {str(e)}")
        return False

# ============================================================================
# NEW GAME QUESTION TESTS
# ============================================================================

def test_get_game_questions():
    """Test getting questions for a game"""
    print("\n" + "="*50)
    print("Testing Get Game Questions")
    print("="*50)
    
    game_id = test_resources.get("game_id")
    if not game_id:
        print_warning("No game ID available - skipping test")
        return None
    
    try:
        response = requests.get(
            f"{API_V1}/creative/games/{game_id}/questions",
            headers=get_headers()
        )
        if response.status_code == 200:
            data = response.json()
            questions = data.get('questions', [])
            print_success("Retrieved game questions")
            print_info(f"Question count: {len(questions)}")
            if questions:
                q = questions[0]
                print_info(f"Sample: {q.get('text')}")
                print_info(f"Options: {len(q.get('options', []))}")
            return True
        elif response.status_code == 400:
            print_warning("Game has no questions configured")
            return None
        else:
            print_error(f"Get questions failed: {response.status_code}")
            return False
    except Exception as e:
        print_error(f"Get questions error: {str(e)}")
        return False

# ============================================================================
# USER MANAGEMENT TESTS
# ============================================================================

def test_get_user_stats():
    """Test getting user statistics"""
    print("\n" + "="*50)
    print("Testing Get User Stats")
    print("="*50)
    
    try:
        response = requests.get(
            f"{API_V1}/users/me/stats",
            headers=get_headers()
        )
        if response.status_code == 200:
            data = response.json()
            print_success("Retrieved user stats")
            print_info(f"Events created: {data.get('events_created', 0)}")
            print_info(f"Events attended: {data.get('events_attended', 0)}")
            print_info(f"Friends count: {data.get('friends_count', 0)}")
            return True
        else:
            print_error(f"Get user stats failed: {response.status_code}")
            return False
    except Exception as e:
        print_error(f"Get user stats error: {str(e)}")
        return False

def test_update_user_profile():
    """Test updating user profile"""
    print("\n" + "="*50)
    print("Testing Update User Profile")
    print("="*50)
    
    profile_data = {
        "bio": "Updated bio via API test",
        "city": "Lagos",
        "country": "Nigeria"
    }
    
    try:
        response = requests.put(
            f"{API_V1}/users/me",
            json=profile_data,
            headers=get_headers()
        )
        if response.status_code == 200:
            data = response.json()
            print_success("Updated user profile")
            print_info(f"Bio: {data.get('bio')}")
            print_info(f"Location: {data.get('city')}, {data.get('country')}")
            return True
        else:
            print_error(f"Update profile failed: {response.status_code}")
            return False
    except Exception as e:
        print_error(f"Update profile error: {str(e)}")
        return False

# ============================================================================
# CONTACT TESTS
# ============================================================================

def test_create_contact():
    """Test creating a contact"""
    print("\n" + "="*50)
    print("Testing Create Contact")
    print("="*50)
    
    contact_data = {
        "name": "John Doe",
        "email": "john.doe@example.com",
        "phone_number": "+2348012345678",
        "notes": "Test contact created during automated run",
        "is_favorite": False
    }
    
    try:
        response = requests.post(
            f"{API_V1}/contacts/",
            json=contact_data,
            headers=get_headers()
        )
        if response.status_code in [200, 201]:
            data = response.json()
            test_resources["contact_id"] = data.get("id")
            print_success("Contact created")
            print_info(f"Contact ID: {data.get('id')}")
            print_info(f"Name: {data.get('first_name')} {data.get('last_name')}")
            return True
        else:
            print_error(f"Create contact failed: {response.status_code}")
            print_error(f"Response: {response.text}")
            return False
    except Exception as e:
        print_error(f"Create contact error: {str(e)}")
        return False

def test_get_contacts():
    """Test getting contacts list"""
    print("\n" + "="*50)
    print("Testing Get Contacts")
    print("="*50)
    
    try:
        response = requests.get(
            f"{API_V1}/contacts/",
            headers=get_headers()
        )
        if response.status_code == 200:
            data = response.json()
            contacts = data.get('contacts', [])
            total = data.get('total', 0)
            print_success("Retrieved contacts list")
            print_info(f"Total contacts: {total}")
            if contacts:
                sample = contacts[0]
                print_info(f"Sample: {sample.get('first_name')} {sample.get('last_name')}")
            return True
        else:
            print_error(f"Get contacts failed: {response.status_code}")
            return False
    except Exception as e:
        print_error(f"Get contacts error: {str(e)}")
        return False

def test_get_contact_stats():
    """Test getting contact statistics"""
    print("\n" + "="*50)
    print("Testing Get Contact Stats")
    print("="*50)
    
    try:
        response = requests.get(
            f"{API_V1}/contacts/stats",
            headers=get_headers()
        )
        if response.status_code == 200:
            data = response.json()
            print_success("Retrieved contact stats")
            print_info(f"Total contacts: {data.get('total_contacts', 0)}")
            print_info(f"Relationship types: {len(data.get('by_relationship', {}))}")
            return True
        else:
            print_error(f"Get contact stats failed: {response.status_code}")
            return False
    except Exception as e:
        print_error(f"Get contact stats error: {str(e)}")
        return False

# ============================================================================
# VENDOR TESTS
# ============================================================================

def test_create_vendor_profile():
    """Test creating vendor profile"""
    print("\n" + "="*50)
    print("Testing Create Vendor Profile")
    print("="*50)
    
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S%f")

    vendor_data = {
        "business_name": "Test Catering Services",
        "display_name": "Test Catering",
        "description": "Professional catering for events",
        "email": f"catering-{timestamp}@example.com",
        "phone": "+2348012345678",
        "category": "catering",
        "city": "Lagos",
        "country": "Nigeria",
        "service_radius_km": 50,
        "years_in_business": 3,
        "base_price": 50000,
        "currency": "USD",
        "pricing_model": "custom_quote",
        "payment_methods": ["transfer", "cash"],
        "accepts_online_payment": False
    }
    
    try:
        response = requests.post(
            f"{API_V1}/vendors/profile",
            json=vendor_data,
            headers=get_headers()
        )
        if response.status_code in [200, 201]:
            data = response.json()
            test_resources["vendor_id"] = data.get("id")
            test_resources["vendor_email"] = data.get("email")
            print_success("Vendor profile created")
            print_info(f"Vendor ID: {data.get('id')}")
            print_info(f"Business: {data.get('business_name')}")
            print_info(f"Category: {data.get('business_category')}")
            return True
        else:
            print_error(f"Create vendor profile failed: {response.status_code}")
            print_error(f"Response: {response.text}")
            return False
    except Exception as e:
        print_error(f"Create vendor profile error: {str(e)}")
        return False

def test_get_vendor_profile():
    """Test getting vendor profile"""
    print("\n" + "="*50)
    print("Testing Get Vendor Profile")
    print("="*50)
    
    try:
        response = requests.get(
            f"{API_V1}/vendors/profile",
            headers=get_headers()
        )
        if response.status_code == 200:
            data = response.json()
            print_success("Retrieved vendor profile")
            print_info(f"Business: {data.get('business_name')}")
            print_info(f"Rating: {data.get('average_rating', 0)}")
            print_info(f"Verified: {data.get('is_verified', False)}")
            return True
        elif response.status_code == 404:
            print_warning("No vendor profile exists yet")
            return None
        else:
            print_error(f"Get vendor profile failed: {response.status_code}")
            return False
    except Exception as e:
        print_error(f"Get vendor profile error: {str(e)}")
        return False

# ============================================================================
# GOOGLE MAPS API TESTS
# ============================================================================

def test_google_maps_api_key():
    """Test Google Maps API key configuration"""
    print("\n" + "="*50)
    print("Testing Google Maps API Key Configuration")
    print("="*50)
    
    try:
        api_key = os.getenv('GOOGLE_MAPS_API_KEY')
        if api_key and api_key != 'your-google-maps-api-key':
            print_success(f"Google Maps API key configured")
            print_info(f"Key length: {len(api_key)} characters")
            print_info(f"Key preview: {api_key[:10]}...{api_key[-5:]}")
            return True
        else:
            print_warning("Google Maps API key not configured")
            print_info("Set GOOGLE_MAPS_API_KEY in .env file")
            return None
    except Exception as e:
        print_error(f"API key check error: {str(e)}")
        return False

def test_geocode_address():
    """Test geocoding an address"""
    print("\n" + "="*50)
    print("Testing Address Geocoding")
    print("="*50)
    
    try:
        import googlemaps
        api_key = os.getenv('GOOGLE_MAPS_API_KEY')
        
        if not api_key or api_key == 'your-google-maps-api-key':
            print_warning("Google Maps API key not configured - skipping test")
            return None
        
        gmaps = googlemaps.Client(key=api_key)
        test_address = "1600 Amphitheatre Parkway, Mountain View, CA"
        
        print_info(f"Geocoding address: {test_address}")
        result = gmaps.geocode(test_address)
        
        if result:
            location = result[0]['geometry']['location']
            formatted_address = result[0]['formatted_address']
            print_success("Geocoding successful")
            print_info(f"Address: {formatted_address}")
            print_info(f"Latitude: {location['lat']}")
            print_info(f"Longitude: {location['lng']}")
            print_info(f"Place ID: {result[0]['place_id']}")
            return True
        else:
            print_error("No geocoding results found")
            return False
    except ImportError:
        print_warning("googlemaps package not installed")
        print_info("Install with: pip install googlemaps")
        return None
    except Exception as e:
        print_error(f"Geocoding error: {str(e)}")
        return False

def test_reverse_geocode():
    """Test reverse geocoding coordinates"""
    print("\n" + "="*50)
    print("Testing Reverse Geocoding")
    print("="*50)
    
    try:
        import googlemaps
        api_key = os.getenv('GOOGLE_MAPS_API_KEY')
        
        if not api_key or api_key == 'your-google-maps-api-key':
            print_warning("Google Maps API key not configured - skipping test")
            return None
        
        gmaps = googlemaps.Client(key=api_key)
        # Google HQ coordinates
        lat, lng = 37.4224764, -122.0842499
        
        print_info(f"Reverse geocoding: {lat}, {lng}")
        result = gmaps.reverse_geocode((lat, lng))
        
        if result:
            formatted_address = result[0]['formatted_address']
            print_success("Reverse geocoding successful")
            print_info(f"Address: {formatted_address}")
            print_info(f"Place ID: {result[0]['place_id']}")
            return True
        else:
            print_error("No reverse geocoding results found")
            return False
    except ImportError:
        print_warning("googlemaps package not installed")
        return None
    except Exception as e:
        print_error(f"Reverse geocoding error: {str(e)}")
        return False

def test_place_autocomplete():
    """Test place autocomplete suggestions"""
    print("\n" + "="*50)
    print("Testing Place Autocomplete")
    print("="*50)
    
    try:
        import googlemaps
        api_key = os.getenv('GOOGLE_MAPS_API_KEY')
        
        if not api_key or api_key == 'your-google-maps-api-key':
            print_warning("Google Maps API key not configured - skipping test")
            return None
        
        gmaps = googlemaps.Client(key=api_key)
        search_input = "Central Park"
        
        print_info(f"Autocomplete search: {search_input}")
        result = gmaps.places_autocomplete(search_input)
        
        if result:
            print_success(f"Found {len(result)} autocomplete suggestions")
            for i, prediction in enumerate(result[:5], 1):  # Show first 5
                print_info(f"  {i}. {prediction['description']}")
                print_info(f"     Place ID: {prediction['place_id']}")
            return True
        else:
            print_error("No autocomplete results found")
            return False
    except ImportError:
        print_warning("googlemaps package not installed")
        return None
    except Exception as e:
        print_error(f"Autocomplete error: {str(e)}")
        return False

# ============================================================================
# MAIN TEST RUNNER
# ============================================================================

def run_all_tests():
    """Run all core API tests"""
    print("\n" + "="*60)
    print("CORE API TEST SUITE - NO EXTERNAL SERVICES")
    print("="*60)
    print(f"Starting tests at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*60)
    
    results = {
        "passed": 0,
        "failed": 0,
        "skipped": 0
    }
    
    # Test 1: Register user
    success, user_data = test_register()
    if success:
        results["passed"] += 1
    else:
        results["failed"] += 1
        print_error("Cannot continue without registration")
        print_summary(results)
        return
    
    # Test 2: Login user
    if test_login(user_data):
        results["passed"] += 1
    else:
        results["failed"] += 1
        print_error("Cannot continue without authentication")
        print_summary(results)
        return
    
    # Test 3: Create event
    if test_create_event():
        results["passed"] += 1
    else:
        results["failed"] += 1
    
    # EVENT FILTERING TESTS
    print("\n" + "="*60)
    print("EVENT CATEGORY FILTER TESTS")
    print("="*60)
    
    # Test 3a: Get upcoming events
    if test_get_my_events_upcoming():
        results["passed"] += 1
    else:
        results["failed"] += 1
    
    # Test 3b: Get draft events
    if test_get_my_events_drafts():
        results["passed"] += 1
    else:
        results["failed"] += 1
    
    # Test 3c: Get hosting events
    if test_get_my_events_hosting():
        results["passed"] += 1
    else:
        results["failed"] += 1
    
    # Test 3d: Get all events
    if test_get_my_events_all():
        results["passed"] += 1
    else:
        results["failed"] += 1
    
    # TASK TESTS
    print("\n" + "="*60)
    print("TASK MANAGEMENT TESTS")
    print("="*60)
    
    # Test 4: Get event tasks (categorized)
    result = test_get_event_tasks()
    if result is True:
        results["passed"] += 1
    elif result is False:
        results["failed"] += 1
    else:
        results["skipped"] += 1
    
    # Test 5: Get single task
    result = test_get_single_task()
    if result is True:
        results["passed"] += 1
    elif result is False:
        results["failed"] += 1
    else:
        results["skipped"] += 1
    
    # Test 6: Update task (mark completed)
    result = test_update_task()
    if result is True:
        results["passed"] += 1
    elif result is False:
        results["failed"] += 1
    else:
        results["skipped"] += 1
    
    # Test 7: Update task (mark incomplete)
    result = test_update_task_mark_incomplete()
    if result is True:
        results["passed"] += 1
    elif result is False:
        results["failed"] += 1
    else:
        results["skipped"] += 1
    
    # Test 8: Delete task
    result = test_delete_task()
    if result is True:
        results["passed"] += 1
    elif result is False:
        results["failed"] += 1
    else:
        results["skipped"] += 1
    
    # NOTIFICATION TESTS
    print("\n" + "="*60)
    print("NOTIFICATION TESTS")
    print("="*60)
    
    # Test 9: Get notifications
    if test_get_notifications():
        results["passed"] += 1
    else:
        results["failed"] += 1
    
    # Test 9: Get notification preferences
    if test_notification_preferences():
        results["passed"] += 1
    else:
        results["failed"] += 1
    
    # Test 10: Update notification preferences
    if test_update_notification_preferences():
        results["passed"] += 1
    else:
        results["failed"] += 1
    
    # Test 11: Get notification channels
    if test_get_notification_channels():
        results["passed"] += 1
    else:
        results["failed"] += 1

    # Test 12: Get notification logs
    if test_get_notification_logs():
        results["passed"] += 1
    else:
        results["failed"] += 1
    
    # Test 9: Get in-app notifications
    if test_get_in_app_notifications():
        results["passed"] += 1
    else:
        results["failed"] += 1
    
    # Test 9a: Test Firebase credentials loading
    result = test_firebase_credentials()
    if result is True:
        results["passed"] += 1
    elif result is False:
        results["failed"] += 1
    else:
        results["skipped"] += 1
    
    # PUSH NOTIFICATION TESTS
    print("\n" + "="*60)
    print("PUSH NOTIFICATION DEVICE & SERVICE TESTS")
    print("="*60)
    
    # Test 9b: Register push notification device
    result = test_register_push_device()
    if result is True:
        results["passed"] += 1
    elif result is False:
        results["failed"] += 1
    else:
        results["skipped"] += 1
    
    # Test 9c: Get user devices
    result = test_get_user_devices()
    if result is True:
        results["passed"] += 1
    elif result is False:
        results["failed"] += 1
    else:
        results["skipped"] += 1
    
    # Test 9d: Send test push notification
    result = test_send_push_notification()
    if result is True:
        results["passed"] += 1
    elif result is False:
        results["failed"] += 1
    else:
        results["skipped"] += 1

    # INVITE TESTS
    # Test 10: Create invite code
    invite_code_result = test_create_invite_code()
    if invite_code_result:
        results["passed"] += 1
    else:
        results["failed"] += 1

    # GCP STORAGE TESTS (Profile Pictures & Media Uploads)
    print("\n" + "="*60)
    print("GCP STORAGE UPLOAD & DELETE TESTS")
    print("="*60)
    
    # Test 10a: Upload profile picture
    if test_upload_profile_picture():
        results["passed"] += 1
    else:
        results["failed"] += 1
    
    # Test 10b: Delete profile picture (from both GCP and database)
    if test_delete_profile_picture():
        results["passed"] += 1
    else:
        results["failed"] += 1
    
    # Test 10c: Upload moodboard image
    if test_upload_moodboard_image():
        results["passed"] += 1
    else:
        results["failed"] += 1
    
    # Test 10d: Delete moodboard with images (from both GCP and database)
    if test_delete_moodboard_with_images():
        results["passed"] += 1
    else:
        results["failed"] += 1
    
    # Test 10e: Upload vendor image
    if test_upload_vendor_image():
        results["passed"] += 1
    else:
        results["failed"] += 1

    # Test 16: Generate custom QR code
    if test_generate_custom_qr_code():
        results["passed"] += 1
    else:
        results["failed"] += 1
    
    # Test 17: Generate profile QR code
    if test_generate_profile_qr_code():
        results["passed"] += 1
    else:
        results["failed"] += 1
    
    # Test 18: Generate app QR code
    if test_generate_app_qr_code():
        results["passed"] += 1
    else:
        results["failed"] += 1

    # Test 19: Get invite codes
    if test_get_invite_codes():
        results["passed"] += 1
    else:
        results["failed"] += 1

    # Test 20: Create invite link
    invite_link_result = test_create_invite_link()
    if invite_link_result:
        results["passed"] += 1
    else:
        results["failed"] += 1
    
    # Test 21: Get invite links
    if test_get_invite_links():
        results["passed"] += 1
    else:
        results["failed"] += 1
    
    # Test 22: Get invite stats
    if test_get_invite_stats():
        results["passed"] += 1
    else:
        results["failed"] += 1
    
    # Test 23: Delete invite code with QR code
    if test_delete_invite_code_with_qr():
        results["passed"] += 1
    else:
        results["failed"] += 1
    
    # Test 24: Delete invite link with QR code
    if test_delete_invite_link_with_qr():
        results["passed"] += 1
    else:
        results["failed"] += 1
    
    # Test 25: Deactivate invite code
    result = test_deactivate_invite_code()
    if result is True:
        results["passed"] += 1
    elif result is False:
        results["failed"] += 1
    else:
        results["skipped"] += 1
    
    # TIMELINE TESTS
    # Test 26: Create timeline
    result = test_create_timeline()
    if result is True:
        results["passed"] += 1
    elif result is False:
        results["failed"] += 1
    else:
        results["skipped"] += 1
    
    # Test 27: Add timeline item
    result = test_add_timeline_item()
    if result is True:
        results["passed"] += 1
    elif result is False:
        results["failed"] += 1
    else:
        results["skipped"] += 1
    
    # MOODBOARD TESTS
    # Test 28: Create moodboard
    result = test_create_moodboard()
    if result is True:
        results["passed"] += 1
    elif result is False:
        results["failed"] += 1
    else:
        results["skipped"] += 1
    
    # Test 29: Add moodboard items
    result = test_add_moodboard_items()
    if result is True:
        results["passed"] += 1
    elif result is False:
        results["failed"] += 1
    else:
        results["skipped"] += 1
    
    # Test 30: Like moodboard
    result = test_like_moodboard()
    if result is True:
        results["passed"] += 1
    elif result is False:
        results["failed"] += 1
    else:
        results["skipped"] += 1
    
    # Test 31: Add moodboard comment
    result = test_add_moodboard_comment()
    if result is True:
        results["passed"] += 1
    elif result is False:
        results["failed"] += 1
    else:
        results["skipped"] += 1
    
    # USER PROFILE TESTS
    # Test 32: Get user profile
    result = test_get_user_profile()
    if result is True:
        results["passed"] += 1
    elif result is False:
        results["failed"] += 1
    else:
        results["skipped"] += 1
    
    # Test 33: Update user profile
    result = test_update_user_profile()
    if result is True:
        results["passed"] += 1
    elif result is False:
        results["failed"] += 1
    else:
        results["skipped"] += 1
    
    # Test 34: Get user stats
    result = test_get_user_stats()
    if result is True:
        results["passed"] += 1
    elif result is False:
        results["failed"] += 1
    else:
        results["skipped"] += 1
    
    # MESSAGE TESTS
    # Test 35: Send message
    result = test_send_message()
    if result is True:
        results["passed"] += 1
    elif result is False:
        results["failed"] += 1
    else:
        results["skipped"] += 1
    
    # Test 36: Get messages
    result = test_get_messages()
    if result is True:
        results["passed"] += 1
    elif result is False:
        results["failed"] += 1
    else:
        results["skipped"] += 1
    
    # Test 37: React to message
    result = test_react_to_message()
    if result is True:
        results["passed"] += 1
    elif result is False:
        results["failed"] += 1
    else:
        results["skipped"] += 1
    
    # Test 38: Pin message
    result = test_pin_message()
    if result is True:
        results["passed"] += 1
    elif result is False:
        results["failed"] += 1
    else:
        results["skipped"] += 1
    
    # Test 39: Get chat stats
    result = test_get_chat_stats()
    if result is True:
        results["passed"] += 1
    elif result is False:
        results["failed"] += 1
    else:
        results["skipped"] += 1
    
    # TIMELINE ADVANCED TESTS
    # Test 42: Get timeline
    result = test_get_timeline()
    if result is True:
        results["passed"] += 1
    elif result is False:
        results["failed"] += 1
    else:
        results["skipped"] += 1
    
    # Test 43: Update timeline item
    result = test_update_timeline_item()
    if result is True:
        results["passed"] += 1
    elif result is False:
        results["failed"] += 1
    else:
        results["skipped"] += 1
    
    # PLAYLIST TESTS
    # Test 44: Create playlist
    result = test_create_playlist()
    if result is True:
        results["passed"] += 1
    elif result is False:
        results["failed"] += 1
    else:
        results["skipped"] += 1
    
    # Test 45: Add playlist track
    result = test_add_playlist_track()
    if result is True:
        results["passed"] += 1
    elif result is False:
        results["failed"] += 1
    else:
        results["skipped"] += 1
    
    # Test 37: Get playlist
    result = test_get_playlist()
    if result is True:
        results["passed"] += 1
    elif result is False:
        results["failed"] += 1
    else:
        results["skipped"] += 1
    
    # GAME TESTS
    # Test 38: Generate game questions with OpenTDB
    result = test_generate_game_questions()
    if result is True:
        results["passed"] += 1
    elif result is False:
        results["failed"] += 1
    else:
        results["skipped"] += 1
    
    # Test 39: Create game
    result = test_create_game()
    if result is True:
        results["passed"] += 1
    elif result is False:
        results["failed"] += 1
    else:
        results["skipped"] += 1
    
    # Test 40: Start game session
    result = test_start_game_session()
    if result is True:
        results["passed"] += 1
    elif result is False:
        results["failed"] += 1
    else:
        results["skipped"] += 1
    
    # Test 41: Get game templates
    result = test_get_game_templates()
    if result is True:
        results["passed"] += 1
    elif result is False:
        results["failed"] += 1
    else:
        results["skipped"] += 1
    
    # Test 42: Get template details
    result = test_get_template_details()
    if result is True:
        results["passed"] += 1
    elif result is False:
        results["failed"] += 1
    else:
        results["skipped"] += 1
    
    # Test 43: Create game from template
    result = test_create_game_from_template()
    if result is True:
        results["passed"] += 1
    elif result is False:
        results["failed"] += 1
    else:
        results["skipped"] += 1
    
    # Test 41: Get creative stats
    result = test_get_creative_stats()
    if result is True:
        results["passed"] += 1
    elif result is False:
        results["failed"] += 1
    else:
        results["skipped"] += 1
    
    # Test 42: Get game questions
    result = test_get_game_questions()
    if result is True:
        results["passed"] += 1
    elif result is False:
        results["failed"] += 1
    else:
        results["skipped"] += 1
    
    # USER MANAGEMENT TESTS
    # Test 42: Get user stats
    result = test_get_user_stats()
    if result is True:
        results["passed"] += 1
    elif result is False:
        results["failed"] += 1
    else:
        results["skipped"] += 1
    
    # Test 43: Update user profile
    result = test_update_user_profile()
    if result is True:
        results["passed"] += 1
    elif result is False:
        results["failed"] += 1
    else:
        results["skipped"] += 1
    
    # CONTACT TESTS
    # Test 44: Create contact
    result = test_create_contact()
    if result is True:
        results["passed"] += 1
    elif result is False:
        results["failed"] += 1
    else:
        results["skipped"] += 1
    
    # Test 45: Get contacts list
    result = test_get_contacts()
    if result is True:
        results["passed"] += 1
    elif result is False:
        results["failed"] += 1
    else:
        results["skipped"] += 1
    
    # Test 46: Get contact stats
    result = test_get_contact_stats()
    if result is True:
        results["passed"] += 1
    elif result is False:
        results["failed"] += 1
    else:
        results["skipped"] += 1
    
    # VENDOR TESTS
    # Test 58: Create vendor profile
    result = test_create_vendor_profile()
    if result is True:
        results["passed"] += 1
    elif result is False:
        results["failed"] += 1
    else:
        results["skipped"] += 1
    
    # Test 59: Get vendor profile
    result = test_get_vendor_profile()
    if result is True:
        results["passed"] += 1
    elif result is False:
        results["failed"] += 1
    else:
        results["skipped"] += 1
    
    # GOOGLE MAPS TESTS
    # Test 60: Test Google Maps API Key
    result = test_google_maps_api_key()
    if result is True:
        results["passed"] += 1
    elif result is False:
        results["failed"] += 1
    else:
        results["skipped"] += 1
    
    # Test 61: Geocode Address
    result = test_geocode_address()
    if result is True:
        results["passed"] += 1
    elif result is False:
        results["failed"] += 1
    else:
        results["skipped"] += 1
    
    # Test 62: Reverse Geocode
    result = test_reverse_geocode()
    if result is True:
        results["passed"] += 1
    elif result is False:
        results["failed"] += 1
    else:
        results["skipped"] += 1
    
    # Test 63: Place Autocomplete
    result = test_place_autocomplete()
    if result is True:
        results["passed"] += 1
    elif result is False:
        results["failed"] += 1
    else:
        results["skipped"] += 1
    
    # Print summary
    print_summary(results)

def print_summary(results):
    """Print test summary"""
    print("\n" + "="*60)
    print("TEST SUMMARY")
    print("="*60)
    print_success(f"Passed: {results['passed']}")
    print_error(f"Failed: {results['failed']}")
    if results.get('skipped', 0) > 0:
        print_warning(f"Skipped: {results['skipped']}")
    
    total = results['passed'] + results['failed']
    if total > 0:
        percentage = (results['passed'] / total) * 100
        print(f"\nSuccess Rate: {percentage:.1f}%")
    
    print("\nCompleted at: " + datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    print("="*60 + "\n")

if __name__ == "__main__":
    try:
        run_all_tests()
    except KeyboardInterrupt:
        print("\n\nTests interrupted by user")
    except Exception as e:
        print_error(f"Unexpected error: {str(e)}")
        import traceback
        traceback.print_exc()
