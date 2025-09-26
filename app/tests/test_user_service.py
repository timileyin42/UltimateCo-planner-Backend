import pytest
from sqlalchemy.orm import Session
from app.services.user_service import UserService
from app.services.auth_service import AuthService
from app.schemas.user import UserRegister, UserUpdate, UserPasswordUpdate
from app.core.errors import NotFoundError, ValidationError, ConflictError
from app.tests.conftest import UserFactory

class TestUserService:
    """Test cases for UserService."""
    
    def test_get_user_by_id(self, user_service: UserService, test_user):
        """Test getting user by ID."""
        user = user_service.get_user_by_id(test_user.id)
        assert user is not None
        assert user.id == test_user.id
        assert user.email == test_user.email
    
    def test_get_user_by_id_not_found(self, user_service: UserService):
        """Test getting non-existent user by ID."""
        user = user_service.get_user_by_id(99999)
        assert user is None
    
    def test_get_user_by_email(self, user_service: UserService, test_user):
        """Test getting user by email."""
        user = user_service.get_user_by_email(test_user.email)
        assert user is not None
        assert user.email == test_user.email
    
    def test_get_user_by_email_not_found(self, user_service: UserService):
        """Test getting non-existent user by email."""
        user = user_service.get_user_by_email("nonexistent@example.com")
        assert user is None
    
    def test_create_user(self, user_service: UserService):
        """Test creating a new user."""
        user_data = UserRegister(
            email="newuser@example.com",
            password="password123",
            confirm_password="password123",
            full_name="New User",
            username="newuser"
        )
        
        user = user_service.create_user(user_data)
        
        assert user.email == "newuser@example.com"
        assert user.full_name == "New User"
        assert user.username == "newuser"
        assert user.is_active is True
        assert user.is_verified is False
    
    def test_create_user_duplicate_email(self, user_service: UserService, test_user):
        """Test creating user with duplicate email."""
        user_data = UserRegister(
            email=test_user.email,  # Duplicate email
            password="password123",
            confirm_password="password123",
            full_name="Another User"
        )
        
        with pytest.raises(ConflictError, match="already exists"):
            user_service.create_user(user_data)
    
    def test_create_user_duplicate_username(self, user_service: UserService, test_user):
        """Test creating user with duplicate username."""
        user_data = UserRegister(
            email="different@example.com",
            password="password123",
            confirm_password="password123",
            full_name="Another User",
            username=test_user.username  # Duplicate username
        )
        
        with pytest.raises(ConflictError, match="already taken"):
            user_service.create_user(user_data)
    
    def test_create_user_password_mismatch(self, user_service: UserService):
        """Test creating user with mismatched passwords."""
        user_data = UserRegister(
            email="newuser@example.com",
            password="password123",
            confirm_password="different123",  # Different password
            full_name="New User"
        )
        
        with pytest.raises(ValidationError, match="do not match"):
            user_service.create_user(user_data)
    
    def test_update_user(self, user_service: UserService, test_user):
        """Test updating user information."""
        update_data = UserUpdate(
            full_name="Updated Name",
            bio="Updated bio",
            city="Updated City"
        )
        
        updated_user = user_service.update_user(test_user.id, update_data)
        
        assert updated_user.full_name == "Updated Name"
        assert updated_user.bio == "Updated bio"
        assert updated_user.city == "Updated City"
        assert updated_user.email == test_user.email  # Unchanged
    
    def test_update_user_not_found(self, user_service: UserService):
        """Test updating non-existent user."""
        update_data = UserUpdate(full_name="Updated Name")
        
        with pytest.raises(NotFoundError, match="not found"):
            user_service.update_user(99999, update_data)
    
    def test_update_user_duplicate_username(self, user_service: UserService, auth_service: AuthService, test_user):
        """Test updating user with duplicate username."""
        # Create another user
        other_user = UserFactory.create_user(auth_service, username="otherusername")
        
        # Try to update test_user with other_user's username
        update_data = UserUpdate(username=other_user.username)
        
        with pytest.raises(ConflictError, match="already taken"):
            user_service.update_user(test_user.id, update_data)
    
    def test_update_user_password(self, user_service: UserService, test_user):
        """Test updating user password."""
        password_data = UserPasswordUpdate(
            current_password="testpassword123",
            new_password="newpassword123",
            confirm_new_password="newpassword123"
        )
        
        success = user_service.update_user_password(test_user.id, password_data)
        assert success is True
        
        # Verify old password no longer works
        from app.core.security import verify_password
        updated_user = user_service.get_user_by_id(test_user.id)
        assert not verify_password("testpassword123", updated_user.hashed_password)
        assert verify_password("newpassword123", updated_user.hashed_password)
    
    def test_update_user_password_wrong_current(self, user_service: UserService, test_user):
        """Test updating password with wrong current password."""
        password_data = UserPasswordUpdate(
            current_password="wrongpassword",
            new_password="newpassword123",
            confirm_new_password="newpassword123"
        )
        
        with pytest.raises(ValidationError, match="incorrect"):
            user_service.update_user_password(test_user.id, password_data)
    
    def test_update_user_password_mismatch(self, user_service: UserService, test_user):
        """Test updating password with mismatched new passwords."""
        password_data = UserPasswordUpdate(
            current_password="testpassword123",
            new_password="newpassword123",
            confirm_new_password="different123"
        )
        
        with pytest.raises(ValidationError, match="do not match"):
            user_service.update_user_password(test_user.id, password_data)
    
    def test_deactivate_user(self, user_service: UserService, test_user):
        """Test deactivating user account."""
        deactivated_user = user_service.deactivate_user(test_user.id)
        
        assert deactivated_user.is_active is False
    
    def test_activate_user(self, user_service: UserService, test_user):
        """Test activating user account."""
        # First deactivate
        user_service.deactivate_user(test_user.id)
        
        # Then activate
        activated_user = user_service.activate_user(test_user.id)
        
        assert activated_user.is_active is True
    
    def test_search_users(self, user_service: UserService, auth_service: AuthService):
        """Test searching users."""
        # Create multiple users
        user1 = UserFactory.create_user(auth_service, email="john.doe@example.com", username="johndoe")
        user2 = UserFactory.create_user(auth_service, email="jane.smith@example.com", username="janesmith")
        user3 = UserFactory.create_user(auth_service, email="bob.wilson@example.com", username="bobwilson")
        
        # Search by name
        results = user_service.search_users("john", skip=0, limit=10)
        assert len(results) >= 1
        assert any(user.id == user1.id for user in results)
        
        # Search by email
        results = user_service.search_users("jane.smith", skip=0, limit=10)
        assert len(results) >= 1
        assert any(user.id == user2.id for user in results)
    
    def test_get_user_stats(self, user_service: UserService, test_user):
        """Test getting user statistics."""
        stats = user_service.get_user_stats(test_user.id)
        
        assert "total_events_created" in stats
        assert "total_events_attended" in stats
        assert "total_tasks_completed" in stats
        assert "total_friends" in stats
        assert "member_since" in stats
        
        # New user should have zero stats
        assert stats["total_events_created"] == 0
        assert stats["total_events_attended"] == 0
        assert stats["total_tasks_completed"] == 0
        assert stats["total_friends"] == 0
    
    def test_add_friend(self, user_service: UserService, auth_service: AuthService, test_user):
        """Test adding a friend."""
        friend = UserFactory.create_user(auth_service)
        
        success = user_service.add_friend(test_user.id, friend.id)
        assert success is True
        
        # Verify friendship
        updated_user = user_service.get_user_by_id(test_user.id)
        assert updated_user.is_friend_with(friend.id)
    
    def test_add_friend_self(self, user_service: UserService, test_user):
        """Test adding self as friend (should fail)."""
        with pytest.raises(ValidationError, match="yourself"):
            user_service.add_friend(test_user.id, test_user.id)
    
    def test_add_friend_already_friends(self, user_service: UserService, auth_service: AuthService, test_user):
        """Test adding already existing friend."""
        friend = UserFactory.create_user(auth_service)
        
        # Add friend first time
        user_service.add_friend(test_user.id, friend.id)
        
        # Try to add again
        with pytest.raises(ConflictError, match="already friends"):
            user_service.add_friend(test_user.id, friend.id)
    
    def test_remove_friend(self, user_service: UserService, auth_service: AuthService, test_user):
        """Test removing a friend."""
        friend = UserFactory.create_user(auth_service)
        
        # Add friend first
        user_service.add_friend(test_user.id, friend.id)
        
        # Remove friend
        success = user_service.remove_friend(test_user.id, friend.id)
        assert success is True
        
        # Verify friendship removed
        updated_user = user_service.get_user_by_id(test_user.id)
        assert not updated_user.is_friend_with(friend.id)
    
    def test_remove_friend_not_friends(self, user_service: UserService, auth_service: AuthService, test_user):
        """Test removing non-friend."""
        other_user = UserFactory.create_user(auth_service)
        
        with pytest.raises(ValidationError, match="not friends"):
            user_service.remove_friend(test_user.id, other_user.id)
    
    def test_get_mutual_friends(self, user_service: UserService, auth_service: AuthService, test_user):
        """Test getting mutual friends."""
        friend1 = UserFactory.create_user(auth_service)
        friend2 = UserFactory.create_user(auth_service)
        mutual_friend = UserFactory.create_user(auth_service)
        
        # Create friendships
        user_service.add_friend(test_user.id, mutual_friend.id)
        user_service.add_friend(friend1.id, mutual_friend.id)
        user_service.add_friend(test_user.id, friend2.id)  # Not mutual
        
        # Get mutual friends
        mutual_friends = user_service.get_mutual_friends(test_user.id, friend1.id)
        
        assert len(mutual_friends) == 1
        assert mutual_friends[0].id == mutual_friend.id
    
    def test_suggest_friends(self, user_service: UserService, auth_service: AuthService, test_user):
        """Test friend suggestions."""
        # Create a network of users
        friend = UserFactory.create_user(auth_service)
        potential_friend = UserFactory.create_user(auth_service)
        
        # Create connections: test_user -> friend -> potential_friend
        user_service.add_friend(test_user.id, friend.id)
        user_service.add_friend(friend.id, potential_friend.id)
        
        # Get suggestions
        suggestions = user_service.suggest_friends(test_user.id, limit=10)
        
        # potential_friend should be suggested
        suggested_ids = [user.id for user in suggestions]
        assert potential_friend.id in suggested_ids