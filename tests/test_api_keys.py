"""
Test cases for API key management and authentication
"""
import pytest
from datetime import datetime, timedelta
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.main import app
from app.models.database import User, APIKey
from app.core.security import get_password_hash, generate_api_key
from app.db.base import get_db

client = TestClient(app)


@pytest.fixture
def test_user(db: Session):
    """Create a test user"""
    user = User(
        username="testuser",
        email="test@example.com",
        hashed_password=get_password_hash("testpass123"),
        is_active=True,
        is_superuser=False
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@pytest.fixture
def auth_token():
    """Get authentication token for test user"""
    response = client.post(
        "/api/v1/auth/token",
        data={
            "username": "testuser",
            "password": "testpass123"
        }
    )
    assert response.status_code == 200
    return response.json()["access_token"]


@pytest.fixture
def test_api_key(db: Session, test_user: User):
    """Create a test API key"""
    api_key = APIKey(
        key=generate_api_key(),
        name="Test API Key",
        user_id=test_user.id,
        is_active=True,
        expires_at=datetime.utcnow() + timedelta(days=30)
    )
    db.add(api_key)
    db.commit()
    db.refresh(api_key)
    return api_key


class TestAPIKeyManagement:
    """Test API key management endpoints"""
    
    def test_create_api_key(self, auth_token: str):
        """Test creating a new API key"""
        response = client.post(
            "/api/v1/api-keys/create",
            headers={"Authorization": f"Bearer {auth_token}"},
            json={
                "name": "My API Key",
                "expires_in_days": 30
            }
        )
        
        assert response.status_code == 201
        data = response.json()
        assert "key" in data
        assert data["name"] == "My API Key"
        assert data["is_active"] is True
        assert data["expires_at"] is not None
        
        # Store the key for later tests
        return data["key"]
    
    def test_create_api_key_without_expiry(self, auth_token: str):
        """Test creating API key without expiry date"""
        response = client.post(
            "/api/v1/api-keys/create",
            headers={"Authorization": f"Bearer {auth_token}"},
            json={
                "name": "Permanent Key"
            }
        )
        
        assert response.status_code == 201
        data = response.json()
        assert data["expires_at"] is None
    
    def test_list_api_keys(self, auth_token: str, test_api_key: APIKey):
        """Test listing user's API keys"""
        response = client.get(
            "/api/v1/api-keys/list",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) > 0
        
        # Check that key preview is shown, not full key
        for key in data:
            assert "key_preview" in key
            assert len(key["key_preview"]) < 20  # Should be truncated
    
    def test_deactivate_api_key(self, auth_token: str, test_api_key: APIKey):
        """Test deactivating an API key"""
        response = client.patch(
            f"/api/v1/api-keys/{test_api_key.id}/deactivate",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        
        assert response.status_code == 200
        assert response.json()["message"] == "API key deactivated successfully"
    
    def test_activate_api_key(self, auth_token: str, test_api_key: APIKey, db: Session):
        """Test activating a deactivated API key"""
        # First deactivate it
        test_api_key.is_active = False
        db.commit()
        
        # Then activate it
        response = client.patch(
            f"/api/v1/api-keys/{test_api_key.id}/activate",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        
        assert response.status_code == 200
        assert response.json()["message"] == "API key activated successfully"
    
    def test_delete_api_key(self, auth_token: str, test_api_key: APIKey):
        """Test deleting an API key"""
        response = client.delete(
            f"/api/v1/api-keys/{test_api_key.id}",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        
        assert response.status_code == 204
    
    def test_cannot_activate_expired_key(self, auth_token: str, test_api_key: APIKey, db: Session):
        """Test that expired keys cannot be activated"""
        # Set key as expired
        test_api_key.expires_at = datetime.utcnow() - timedelta(days=1)
        test_api_key.is_active = False
        db.commit()
        
        response = client.patch(
            f"/api/v1/api-keys/{test_api_key.id}/activate",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        
        assert response.status_code == 400
        assert "expired" in response.json()["detail"].lower()


class TestAPIKeyAuthentication:
    """Test API key authentication on protected endpoints"""
    
    def test_protected_endpoint_with_valid_api_key(self, test_api_key: APIKey):
        """Test accessing protected endpoint with valid API key"""
        # Create a test file
        test_file = ("test.hwp", b"test content", "application/octet-stream")
        
        response = client.post(
            "/api/v1/extract/protected/hwp-to-json",
            headers={"X-API-Key": test_api_key.key},
            files={"file": test_file},
            data={"extract_tables": "true"}
        )
        
        # May fail due to invalid file content, but should authenticate
        assert response.status_code in [200, 500]  # 500 if file parsing fails
    
    def test_protected_endpoint_with_bearer_token(self, test_api_key: APIKey):
        """Test accessing protected endpoint with Bearer token format"""
        test_file = ("test.hwp", b"test content", "application/octet-stream")
        
        response = client.post(
            "/api/v1/extract/protected/hwp-to-json",
            headers={"Authorization": f"Bearer {test_api_key.key}"},
            files={"file": test_file},
            data={"extract_tables": "true"}
        )
        
        # May fail due to invalid file content, but should authenticate
        assert response.status_code in [200, 500]  # 500 if file parsing fails
    
    def test_protected_endpoint_without_api_key(self):
        """Test accessing protected endpoint without API key"""
        test_file = ("test.hwp", b"test content", "application/octet-stream")
        
        response = client.post(
            "/api/v1/extract/protected/hwp-to-json",
            files={"file": test_file},
            data={"extract_tables": "true"}
        )
        
        assert response.status_code == 401
        assert "API key required" in response.json()["detail"]
    
    def test_protected_endpoint_with_invalid_api_key(self):
        """Test accessing protected endpoint with invalid API key"""
        test_file = ("test.hwp", b"test content", "application/octet-stream")
        
        response = client.post(
            "/api/v1/extract/protected/hwp-to-json",
            headers={"X-API-Key": "invalid-api-key"},
            files={"file": test_file},
            data={"extract_tables": "true"}
        )
        
        assert response.status_code == 401
        assert "Invalid or expired API key" in response.json()["detail"]
    
    def test_protected_endpoint_with_inactive_api_key(self, test_api_key: APIKey, db: Session):
        """Test accessing protected endpoint with inactive API key"""
        # Deactivate the key
        test_api_key.is_active = False
        db.commit()
        
        test_file = ("test.hwp", b"test content", "application/octet-stream")
        
        response = client.post(
            "/api/v1/extract/protected/hwp-to-json",
            headers={"X-API-Key": test_api_key.key},
            files={"file": test_file},
            data={"extract_tables": "true"}
        )
        
        assert response.status_code == 401
        assert "Invalid or expired API key" in response.json()["detail"]
    
    def test_protected_endpoint_with_expired_api_key(self, test_api_key: APIKey, db: Session):
        """Test accessing protected endpoint with expired API key"""
        # Set key as expired
        test_api_key.expires_at = datetime.utcnow() - timedelta(days=1)
        db.commit()
        
        test_file = ("test.hwp", b"test content", "application/octet-stream")
        
        response = client.post(
            "/api/v1/extract/protected/hwp-to-json",
            headers={"X-API-Key": test_api_key.key},
            files={"file": test_file},
            data={"extract_tables": "true"}
        )
        
        assert response.status_code == 401
        assert "Invalid or expired API key" in response.json()["detail"]
    
    def test_api_key_last_used_updated(self, test_api_key: APIKey, db: Session):
        """Test that API key's last_used timestamp is updated"""
        initial_last_used = test_api_key.last_used
        
        test_file = ("test.hwp", b"test content", "application/octet-stream")
        
        response = client.post(
            "/api/v1/extract/protected/hwp-to-json",
            headers={"X-API-Key": test_api_key.key},
            files={"file": test_file},
            data={"extract_tables": "true"}
        )
        
        # Refresh the API key from database
        db.refresh(test_api_key)
        
        # Check that last_used was updated
        assert test_api_key.last_used is not None
        if initial_last_used:
            assert test_api_key.last_used > initial_last_used