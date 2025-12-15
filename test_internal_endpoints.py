"""
Internal Endpoints Testing Script
Tests endpoints not covered by existing scripts, without external service dependencies.
Adheres to existing test patterns (requests, auth, summaries, isolation).
"""
import requests
import json
from datetime import datetime

# Base URL
BASE_URL = "http://localhost:8000"
API_V1 = f"{BASE_URL}/api/v1"

# Colors for terminal output (consistent with existing files)
class Colors:
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    END = '\033[0m'

def print_success(message):
    print(f"{Colors.GREEN}✓ {message}{Colors.END}")

def print_error(message):
    print(f"{Colors.RED}✗ {message}{Colors.END}")

def print_info(message):
    print(f"{Colors.BLUE}ℹ {message}{Colors.END}")

def print_warning(message):
    print(f"{Colors.YELLOW}⚠ {message}{Colors.END}")

# Global tokens and resources
auth_tokens = {
    "access_token": None,
    "refresh_token": None,
    "user_id": None
}

test_resources = {
    "secondary_user_id": None,
    "tertiary_user_id": None,
    "device_id": None,
    "profile_created": False,
    # store credentials for secondary/tertiary to perform actions
    "secondary_email": None,
    "secondary_password": None,
    "tertiary_email": None,
    "tertiary_password": None
}

def get_headers():
    return {
        "Authorization": f"Bearer {auth_tokens['access_token']}",
        "Content-Type": "application/json"
    }

# ==========================================================================
# AUTH SETUP
# ==========================================================================

def test_register_primary_user():
    print("\n" + "="*50)
    print("Registering Primary Test User")
    print("="*50)

    timestamp = datetime.now().strftime("%Y%m%d%H%M%S%f")
    user_data = {
        "email": f"internal-tests-{timestamp}@example.com",
        "full_name": "Internal Tester",
        "username": f"internaltester{timestamp[:8]}",
        "password": "InternalTest123!",
        "confirm_password": "InternalTest123!",
        "timezone": "UTC",
        "country": "Nigeria"
    }

    try:
        response = requests.post(f"{API_V1}/auth/register", json=user_data)
        if response.status_code in [200, 201]:
            data = response.json()
            auth_tokens["user_id"] = data.get("id")
            print_success("Primary user registration successful")
            return True, user_data
        else:
            print_error(f"Registration failed: {response.status_code}")
            print_error(f"Response: {response.text}")
            return False, None
    except Exception as e:
        print_error(f"Registration error: {str(e)}")
        return False, None

def test_login_primary(user_data):
    print("\n" + "="*50)
    print("Logging In Primary Test User")
    print("="*50)

    login_data = {"email": user_data["email"], "password": user_data["password"]}
    try:
        response = requests.post(f"{API_V1}/auth/login", json=login_data)
        if response.status_code == 200:
            data = response.json()
            auth_tokens["access_token"] = data.get("access_token")
            auth_tokens["refresh_token"] = data.get("refresh_token")
            print_success("Primary user login successful")
            return True
        else:
            print_error(f"Login failed: {response.status_code}")
            print_error(f"Response: {response.text}")
            return False
    except Exception as e:
        print_error(f"Login error: {str(e)}")
        return False

def register_additional_user(label_key):
    """Register a secondary/tertiary user to drive friend tests."""
    ts = datetime.now().strftime("%Y%m%d%H%M%S%f")
    user_data = {
        "email": f"internal-{label_key}-{ts}@example.com",
        "full_name": f"Internal {label_key.title()}",
        "username": f"internal{label_key}{ts[:8]}",
        "password": "InternalTest123!",
        "confirm_password": "InternalTest123!",
        "timezone": "UTC",
        "country": "Nigeria"
    }
    try:
        response = requests.post(f"{API_V1}/auth/register", json=user_data)
        if response.status_code in [200, 201]:
            data = response.json()
            uid = data.get("id")
            test_resources[f"{label_key}_user_id"] = uid
            # store credentials for later logins
            test_resources[f"{label_key}_email"] = user_data["email"]
            test_resources[f"{label_key}_password"] = user_data["password"]
            print_success(f"{label_key.title()} user registered: {uid}")
            return True, user_data
        else:
            print_error(f"{label_key.title()} registration failed: {response.status_code}")
            print_error(f"Response: {response.text}")
            return False, None
    except Exception as e:
        print_error(f"{label_key.title()} registration error: {str(e)}")
        return False, None

def login_user_get_token(email, password):
    """Login helper to obtain a bearer token for a given user."""
    try:
        resp = requests.post(f"{API_V1}/auth/login", json={"email": email, "password": password})
        if resp.status_code == 200:
            return True, resp.json().get("access_token")
        else:
            print_error(f"Login failed for {email}: {resp.status_code}")
            print_error(f"Response: {resp.text}")
            return False, None
    except Exception as e:
        print_error(f"Login error for {email}: {str(e)}")
        return False, None

# ==========================================================================
# USERS: DETAILED PROFILE ENDPOINTS (/users/me/profile)
# ==========================================================================

def test_get_profile_details_not_found():
    print("\n" + "="*50)
    print("Testing Get Detailed Profile (Expect 404)")
    print("="*50)
    try:
        response = requests.get(f"{API_V1}/users/me/profile", headers=get_headers())
        if response.status_code == 404:
            print_success("Profile not found as expected")
            return True
        else:
            print_error(f"Unexpected status: {response.status_code}")
            print_error(f"Response: {response.text}")
            return False
    except Exception as e:
        print_error(f"Get profile details error: {str(e)}")
        return False

def test_create_profile_details():
    print("\n" + "="*50)
    print("Testing Create Detailed Profile")
    print("="*50)
    payload = {
        "occupation": "Planner",
        "company": "CoPlanner Inc",
        "website": "https://example.com",
        "instagram_handle": "@planner",
        "planning_style": "Minimalist",
        "budget_range": "Medium"
    }
    try:
        response = requests.post(
            f"{API_V1}/users/me/profile",
            json=payload,
            headers=get_headers()
        )
        if response.status_code in [200, 201]:
            data = response.json()
            test_resources["profile_created"] = True
            print_success("Detailed profile created")
            print_info(f"Profile ID: {data.get('id')} | User ID: {data.get('user_id')}")
            return True
        else:
            print_error(f"Create profile failed: {response.status_code}")
            print_error(f"Response: {response.text}")
            return False
    except Exception as e:
        print_error(f"Create profile error: {str(e)}")
        return False

def test_get_profile_details_success():
    print("\n" + "="*50)
    print("Testing Get Detailed Profile (Success)")
    print("="*50)
    try:
        response = requests.get(f"{API_V1}/users/me/profile", headers=get_headers())
        if response.status_code == 200:
            data = response.json()
            print_success("Detailed profile retrieved")
            print_info(f"Occupation: {data.get('occupation', 'N/A')} | Company: {data.get('company', 'N/A')}")
            return True
        else:
            print_error(f"Get detailed profile failed: {response.status_code}")
            print_error(f"Response: {response.text}")
            return False
    except Exception as e:
        print_error(f"Get detailed profile error: {str(e)}")
        return False

def test_update_profile_details_success():
    print("\n" + "="*50)
    print("Testing Update Detailed Profile")
    print("="*50)
    payload = {
        "planning_style": "Elegant",
        "budget_range": "High"
    }
    try:
        response = requests.put(
            f"{API_V1}/users/me/profile",
            json=payload,
            headers=get_headers()
        )
        if response.status_code == 200:
            data = response.json()
            print_success("Detailed profile updated")
            print_info(f"Planning Style: {data.get('planning_style', 'N/A')}")
            return True
        else:
            print_error(f"Update detailed profile failed: {response.status_code}")
            print_error(f"Response: {response.text}")
            return False
    except Exception as e:
        print_error(f"Update detailed profile error: {str(e)}")
        return False

def test_create_profile_duplicate_conflict():
    print("\n" + "="*50)
    print("Testing Create Detailed Profile Duplicate (Expect 409)")
    print("="*50)
    try:
        response = requests.post(
            f"{API_V1}/users/me/profile",
            json={"occupation": "Duplicate"},
            headers=get_headers()
        )
        if response.status_code == 409:
            print_success("Duplicate profile creation blocked as expected")
            return True
        else:
            print_error(f"Unexpected status: {response.status_code}")
            print_error(f"Response: {response.text}")
            return False
    except Exception as e:
        print_error(f"Duplicate create error: {str(e)}")
        return False

# ==========================================================================
# USERS: PASSWORD UPDATE (/users/me/password)
# ==========================================================================

def test_update_password_mismatch_error():
    print("\n" + "="*50)
    print("Testing Update Password Mismatch (Expect 400)")
    print("="*50)
    payload = {
        "current_password": "InternalTest123!",
        "new_password": "NewPass123!",
        "confirm_new_password": "NewPass123!!"
    }
    try:
        response = requests.put(
            f"{API_V1}/users/me/password",
            json=payload,
            headers=get_headers()
        )
        if response.status_code == 400:
            print_success("Password mismatch correctly handled")
            return True
        else:
            print_error(f"Unexpected status: {response.status_code}")
            print_error(f"Response: {response.text}")
            return False
    except Exception as e:
        print_error(f"Update password error: {str(e)}")
        return False

def test_update_password_success(primary_user_data):
    print("\n" + "="*50)
    print("Testing Update Password Success")
    print("="*50)
    payload = {
        "current_password": "InternalTest123!",
        "new_password": "InternalTest456!",
        "confirm_new_password": "InternalTest456!"
    }
    try:
        response = requests.put(
            f"{API_V1}/users/me/password",
            json=payload,
            headers=get_headers()
        )
        if response.status_code == 200:
            print_success("Password updated successfully")
            # Verify login with new password
            login_data = {"email": primary_user_data["email"], "password": "InternalTest456!"}
            login_resp = requests.post(f"{API_V1}/auth/login", json=login_data)
            if login_resp.status_code == 200:
                print_success("Re-login with new password succeeded")
                return True
            else:
                print_error(f"Re-login failed: {login_resp.status_code}")
                print_error(f"Response: {login_resp.text}")
                return False
        else:
            print_error(f"Update password failed: {response.status_code}")
            print_error(f"Response: {response.text}")
            return False
    except Exception as e:
        print_error(f"Update password success error: {str(e)}")
        return False

# ==========================================================================
# USERS: FRIEND MANAGEMENT (/users/me/friends)
# ==========================================================================

def test_add_friend_success():
    print("\n" + "="*50)
    print("Testing Add Friend")
    print("="*50)
    if not test_resources["secondary_user_id"]:
        print_warning("No secondary user available for friend test")
        return False
    payload = {"friend_id": test_resources["secondary_user_id"]}
    try:
        response = requests.post(
            f"{API_V1}/users/me/friends",
            json=payload,
            headers=get_headers()
        )
        if response.status_code in [200, 201]:
            print_success("Friend added successfully")
            return True
        else:
            print_error(f"Add friend failed: {response.status_code}")
            print_error(f"Response: {response.text}")
            return False
    except Exception as e:
        print_error(f"Add friend error: {str(e)}")
        return False

def test_get_friends_list():
    print("\n" + "="*50)
    print("Testing Get Friends List")
    print("="*50)
    try:
        response = requests.get(f"{API_V1}/users/me/friends", headers=get_headers())
        if response.status_code == 200:
            data = response.json()
            friends = data.get("friends", [])
            print_success("Retrieved friends list")
            print_info(f"Total friends: {data.get('total', 0)}")
            return True
        else:
            print_error(f"Get friends failed: {response.status_code}")
            print_error(f"Response: {response.text}")
            return False
    except Exception as e:
        print_error(f"Get friends error: {str(e)}")
        return False

def test_remove_friend_success():
    print("\n" + "="*50)
    print("Testing Remove Friend")
    print("="*50)
    friend_id = test_resources["secondary_user_id"]
    if not friend_id:
        print_warning("No friend to remove")
        return False
    try:
        response = requests.delete(
            f"{API_V1}/users/me/friends/{friend_id}",
            headers=get_headers()
        )
        if response.status_code == 200:
            print_success("Friend removed successfully")
            return True
        else:
            print_error(f"Remove friend failed: {response.status_code}")
            print_error(f"Response: {response.text}")
            return False
    except Exception as e:
        print_error(f"Remove friend error: {str(e)}")
        return False

def test_remove_friend_not_friends_error():
    print("\n" + "="*50)
    print("Testing Remove Non-Friend (Expect 400)")
    print("="*50)
    friend_id = test_resources["secondary_user_id"]
    if not friend_id:
        print_warning("No friend ID available")
        return False
    try:
        response = requests.delete(
            f"{API_V1}/users/me/friends/{friend_id}",
            headers=get_headers()
        )
        if response.status_code == 400:
            print_success("Not-friends validation handled correctly")
            return True
        else:
            print_error(f"Unexpected status: {response.status_code}")
            print_error(f"Response: {response.text}")
            return False
    except Exception as e:
        print_error(f"Remove non-friend error: {str(e)}")
        return False

# ==========================================================================
def test_get_friend_suggestions():
    print("\n" + "="*50)
    print("Testing Friend Suggestions")
    print("="*50)
    # Fetch suggestions for primary and validate basic shape
    try:
        response = requests.get(
            f"{API_V1}/users/me/friends/suggestions",
            params={"limit": 10},
            headers=get_headers()
        )
        if response.status_code == 200:
            try:
                suggestions = response.json()
            except Exception:
                print_error("Suggestions response is not valid JSON")
                print_info(response.text)
                return False
            if isinstance(suggestions, list):
                print_success(f"Friend suggestions returned list (count: {len(suggestions)})")
                return True
            print_error("Suggestions response is not a list")
            print_info(json.dumps(suggestions, indent=2))
            return False
        print_error(f"Get suggestions failed: {response.status_code}")
        print_error(f"Response: {response.text}")
        return False
    except Exception as e:
        print_error(f"Get friend suggestions error: {str(e)}")
        return False

# ==========================================================================
def test_register_device():
    print("\n" + "="*50)
    print("Testing Register Device")
    print("="*50)
    payload = {
        "device_token": f"token-{datetime.now().timestamp()}",
        "device_id": f"device-{datetime.now().strftime('%Y%m%d%H%M%S')}",
        "platform": "android",
        "device_name": "Internal Test Phone",
        "app_version": "1.0.0",
        "os_version": "14"
    }
    try:
        response = requests.post(
            f"{API_V1}/devices/register",
            json=payload,
            headers=get_headers()
        )
        if response.status_code == 200:
            data = response.json()
            test_resources["device_id"] = data.get("device_id")
            print_success("Device registered successfully")
            print_info(f"Device ID: {test_resources['device_id']}")
            return True
        else:
            print_error(f"Register device failed: {response.status_code}")
            print_error(f"Response: {response.text}")
            return False
    except Exception as e:
        print_error(f"Register device error: {str(e)}")
        return False

def test_update_device():
    print("\n" + "="*50)
    print("Testing Update Device")
    print("="*50)
    device_id = test_resources["device_id"]
    if not device_id:
        print_warning("No device_id available for update")
        return False
    payload = {
        "device_name": "Internal Test Phone Updated",
        "is_active": True
    }
    try:
        response = requests.put(
            f"{API_V1}/devices/{device_id}",
            json=payload,
            headers=get_headers()
        )
        if response.status_code == 200:
            print_success("Device updated successfully")
            return True
        else:
            print_error(f"Update device failed: {response.status_code}")
            print_error(f"Response: {response.text}")
            return False
    except Exception as e:
        print_error(f"Update device error: {str(e)}")
        return False

def test_update_device_token():
    print("\n" + "="*50)
    print("Testing Update Device Token")
    print("="*50)
    device_id = test_resources["device_id"]
    if not device_id:
        print_warning("No device_id available for token update")
        return False
    params = {
        "device_id": device_id,
        "new_token": f"token-refresh-{datetime.now().timestamp()}"
    }
    try:
        response = requests.post(
            f"{API_V1}/devices/update-token",
            params=params,
            headers=get_headers()
        )
        if response.status_code == 200:
            print_success("Device token updated successfully")
            return True
        else:
            print_error(f"Update token failed: {response.status_code}")
            print_error(f"Response: {response.text}")
            return False
    except Exception as e:
        print_error(f"Update device token error: {str(e)}")
        return False

def test_delete_device():
    print("\n" + "="*50)
    print("Testing Delete Device")
    print("="*50)
    device_id = test_resources["device_id"]
    if not device_id:
        print_warning("No device_id available for deletion")
        return False
    try:
        response = requests.delete(
            f"{API_V1}/devices/{device_id}",
            headers=get_headers()
        )
        if response.status_code == 200:
            print_success("Device deleted successfully")
            return True
        else:
            print_error(f"Delete device failed: {response.status_code}")
            print_error(f"Response: {response.text}")
            return False
    except Exception as e:
        print_error(f"Delete device error: {str(e)}")
        return False
def test_get_user_devices():
    print("\n" + "="*50)
    print("Testing Get User Devices")
    print("="*50)
    try:
        response = requests.get(f"{API_V1}/devices/", headers=get_headers())
        if response.status_code == 200:
            data = response.json()
            print_success("Retrieved user devices")
            print_info(f"Total devices: {data.get('total', 0)}")
            return True
        else:
            print_error(f"Get user devices failed: {response.status_code}")
            print_error(f"Response: {response.text}")
            return False
    except Exception as e:
        print_error(f"Get devices error: {str(e)}")

# ==========================================================================
# RUNNER
# ==========================================================================

def run_all_tests():
    results = {}
    # Setup primary
    ok, primary_data = test_register_primary_user()
    results["register_primary"] = ok
    if not ok:
        print_error("Aborting: primary user registration failed")
        print_summary(results)
        return
    ok = test_login_primary(primary_data)
    results["login_primary"] = ok
    if not ok:
        print_error("Aborting: primary user login failed")
        print_summary(results)
        return

    # Secondary user for friends
    ok, secondary_data = register_additional_user("secondary")
    results["register_secondary"] = ok

    # Users: Detailed profile
    results["get_profile_404"] = test_get_profile_details_not_found()
    results["create_profile"] = test_create_profile_details()
    results["get_profile"] = test_get_profile_details_success()
    results["update_profile"] = test_update_profile_details_success()
    results["duplicate_profile_conflict"] = test_create_profile_duplicate_conflict()

    # Users: Password update
    results["password_mismatch"] = test_update_password_mismatch_error()
    results["password_update_success"] = test_update_password_success(primary_data)

    # Users: Friends
    results["add_friend"] = test_add_friend_success()
    # Build friend-of-friend network and test suggestions before removals
    results["friend_suggestions"] = test_get_friend_suggestions()
    results["list_friends"] = test_get_friends_list()
    results["remove_friend"] = test_remove_friend_success()
    results["remove_friend_not_friends"] = test_remove_friend_not_friends_error()

    # Devices
    results["register_device"] = test_register_device()
    results["update_device"] = test_update_device()
    results["update_token"] = test_update_device_token()
    results["get_devices"] = test_get_user_devices()
    results["delete_device"] = test_delete_device()

    print_summary(results)

def print_summary(results):
    print("\n" + "="*60)
    print("Internal Endpoints Test Summary")
    print("="*60)
    passed = sum(1 for v in results.values() if v)
    total = len(results)
    for name, ok in results.items():
        status = "PASS" if ok else "FAIL"
        color = Colors.GREEN if ok else Colors.RED
        print(f"{color}{name}: {status}{Colors.END}")
    print_info(f"Passed {passed}/{total} tests")
    print("="*60)

if __name__ == "__main__":
    try:
        run_all_tests()
    except KeyboardInterrupt:
        print("\n\nTests interrupted by user")
    except Exception as e:
        print_error(f"Unexpected error: {str(e)}")