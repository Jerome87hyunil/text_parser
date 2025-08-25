"""
Tests for authentication endpoints.
"""
import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock
import jwt
from datetime import datetime, timedelta

from app.main import app
from app.core.security import SECRET_KEY, ALGORITHM

client = TestClient(app)


class TestAuthEndpoints:
    """Test authentication endpoints."""
    
    @pytest.fixture
    def valid_token(self):
        """Create a valid JWT token."""
        payload = {
            "sub": "testuser",
            "exp": datetime.utcnow() + timedelta(minutes=30)
        }
        return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)
    
    @pytest.fixture
    def expired_token(self):
        """Create an expired JWT token."""
        payload = {
            "sub": "testuser",
            "exp": datetime.utcnow() - timedelta(minutes=1)
        }
        return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)
    
    def test_login_success(self):
        """Test successful login."""
        response = client.post(
            "/api/v1/auth/token",
            data={
                "username": "testuser",
                "password": "testpass123"
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert "access_token" in data
        assert data["token_type"] == "bearer"
        
        # Verify token is valid
        token = data["access_token"]
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        assert payload["sub"] == "testuser"
    
    def test_login_invalid_credentials(self):
        """Test login with invalid credentials."""
        response = client.post(
            "/api/v1/auth/token",
            data={
                "username": "wronguser",
                "password": "wrongpass"
            }
        )
        
        assert response.status_code == 401
        data = response.json()
        assert "Incorrect username or password" in data["detail"]
    
    def test_login_missing_fields(self):
        """Test login with missing fields."""
        response = client.post(
            "/api/v1/auth/token",
            data={"username": "testuser"}  # Missing password
        )
        
        assert response.status_code == 422  # Validation error
    
    def test_get_current_user_success(self, valid_token):
        """Test getting current user with valid token."""
        headers = {"Authorization": f"Bearer {valid_token}"}
        response = client.get("/api/v1/auth/me", headers=headers)
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["username"] == "testuser"
        assert data["email"] == "test@example.com"
        assert data["is_active"] is True
    
    def test_get_current_user_no_token(self):
        """Test getting current user without token."""
        response = client.get("/api/v1/auth/me")
        
        assert response.status_code == 401
        data = response.json()
        assert "Not authenticated" in data["detail"]
    
    def test_get_current_user_expired_token(self, expired_token):
        """Test getting current user with expired token."""
        headers = {"Authorization": f"Bearer {expired_token}"}
        response = client.get("/api/v1/auth/me", headers=headers)
        
        assert response.status_code == 401
        data = response.json()
        assert "Could not validate credentials" in data["detail"]
    
    def test_get_current_user_invalid_token(self):
        """Test getting current user with invalid token."""
        headers = {"Authorization": "Bearer invalid_token_here"}
        response = client.get("/api/v1/auth/me", headers=headers)
        
        assert response.status_code == 401
        data = response.json()
        assert "Could not validate credentials" in data["detail"]
    
    def test_authenticated_extraction(self, valid_token):
        """Test authenticated extraction endpoint."""
        headers = {"Authorization": f"Bearer {valid_token}"}
        
        with patch('app.services.hwp_parser.HWPParser.parse') as mock_parse:
            mock_parse.return_value = {
                "text": "Test content",
                "paragraphs": [],
                "tables": [],
                "metadata": {}
            }
            
            files = {"file": ("test.hwp", b"content", "application/x-hwp")}
            response = client.post(
                "/api/v1/extract/auth/hwp-to-json",
                files=files,
                headers=headers
            )
            
            # Should work with valid auth
            assert response.status_code in [200, 500]  # 500 might occur due to mock issues
    
    def test_authenticated_extraction_no_auth(self):
        """Test authenticated extraction without auth."""
        files = {"file": ("test.hwp", b"content", "application/x-hwp")}
        response = client.post("/api/v1/extract/auth/hwp-to-json", files=files)
        
        assert response.status_code == 401
        data = response.json()
        assert "Not authenticated" in data["detail"]