"""
API endpoint tests.
"""
import pytest
from fastapi.testclient import TestClient
import os
import tempfile
from pathlib import Path


def test_root_endpoint(client: TestClient):
    """Test root endpoint."""
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert "project" in data
    assert "version" in data
    assert "status" in data
    assert data["status"] == "healthy"


def test_health_check(client: TestClient):
    """Test health check endpoint."""
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "healthy"}


def test_upload_invalid_file_type(client: TestClient):
    """Test uploading invalid file type."""
    # Create a temporary text file
    with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as tmp:
        tmp.write(b"This is not an HWP file")
        tmp_path = tmp.name
    
    try:
        with open(tmp_path, "rb") as f:
            response = client.post(
                "/api/v1/convert/hwp-to-pdf",
                files={"file": ("test.txt", f, "text/plain")}
            )
        
        assert response.status_code == 400
        assert "Invalid file type" in response.json()["detail"]
    finally:
        os.unlink(tmp_path)


def test_upload_oversized_file(client: TestClient):
    """Test uploading oversized file."""
    # Create a file larger than allowed
    large_content = b"x" * (11 * 1024 * 1024)  # 11MB
    
    with tempfile.NamedTemporaryFile(suffix=".hwp", delete=False) as tmp:
        tmp.write(large_content)
        tmp_path = tmp.name
    
    try:
        with open(tmp_path, "rb") as f:
            response = client.post(
                "/api/v1/convert/hwp-to-pdf",
                files={"file": ("large.hwp", f, "application/octet-stream")}
            )
        
        assert response.status_code == 400
        assert "File too large" in response.json()["detail"]
    finally:
        os.unlink(tmp_path)


def test_upload_mock_hwp_file(client: TestClient):
    """Test uploading a mock HWP file."""
    # Create a mock HWP file with OLE signature
    ole_signature = b'\xD0\xCF\x11\xE0\xA1\xB1\x1A\xE1'
    mock_content = ole_signature + b'x' * 1000
    
    with tempfile.NamedTemporaryFile(suffix=".hwp", delete=False) as tmp:
        tmp.write(mock_content)
        tmp_path = tmp.name
    
    try:
        with open(tmp_path, "rb") as f:
            response = client.post(
                "/api/v1/convert/hwp-to-pdf",
                files={"file": ("test.hwp", f, "application/octet-stream")}
            )
        
        # Should process the file (even if conversion fails, it should return a PDF)
        assert response.status_code == 200
        assert response.headers["content-type"] == "application/pdf"
        
        # Check that we got some PDF content
        content = response.content
        assert len(content) > 0
        assert content.startswith(b'%PDF')  # PDF signature
        
    finally:
        os.unlink(tmp_path)