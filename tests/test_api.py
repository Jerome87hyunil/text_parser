"""
API endpoint tests.
"""
import pytest
from fastapi.testclient import TestClient
import os
import tempfile
from pathlib import Path


def test_root_endpoint(client: TestClient):
    """Test root endpoint returns API info."""
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert "project" in data
    assert "version" in data
    assert "status" in data
    assert data["status"] == "healthy"
    assert "docs" in data
    assert data["docs"] == "/docs"


def test_health_check(client: TestClient):
    """Test health check endpoint."""
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "healthy"}


def test_extract_json_invalid_file_type(client: TestClient):
    """Test extract endpoint with invalid file type."""
    # Create a temporary text file
    with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as tmp:
        tmp.write(b"This is not an HWP file")
        tmp_path = tmp.name
    
    try:
        with open(tmp_path, "rb") as f:
            response = client.post(
                "/api/v1/extract/hwp-to-json",
                files={"file": ("test.txt", f, "text/plain")}
            )
        
        assert response.status_code == 400
        assert "File must be HWP, HWPX, or PDF format" in response.json()["detail"]
    finally:
        os.unlink(tmp_path)


def test_extract_json_oversized_file(client: TestClient):
    """Test uploading oversized file."""
    # Create a file larger than allowed (11MB)
    large_content = b"x" * (11 * 1024 * 1024)
    
    with tempfile.NamedTemporaryFile(suffix=".hwp", delete=False) as tmp:
        tmp.write(large_content)
        tmp_path = tmp.name
    
    try:
        with open(tmp_path, "rb") as f:
            response = client.post(
                "/api/v1/extract/hwp-to-json",
                files={"file": ("large.hwp", f, "application/octet-stream")}
            )
        
        assert response.status_code == 413
        assert "File too large" in response.json()["detail"]
    finally:
        os.unlink(tmp_path)


def test_extract_json_missing_file(client: TestClient):
    """Test extract endpoint with missing file."""
    response = client.post("/api/v1/extract/hwp-to-json")
    assert response.status_code == 422  # Unprocessable Entity


def test_extract_text_missing_file(client: TestClient):
    """Test text extraction with missing file."""
    response = client.post("/api/v1/extract/hwp-to-text")
    assert response.status_code == 422  # Unprocessable Entity


def test_extract_markdown_missing_file(client: TestClient):
    """Test markdown extraction with missing file."""
    response = client.post("/api/v1/extract/hwp-to-markdown")
    assert response.status_code == 422  # Unprocessable Entity


def test_swagger_ui_available(client: TestClient):
    """Test that Swagger UI is available."""
    response = client.get("/docs")
    assert response.status_code == 200
    assert "swagger-ui" in response.text.lower()


def test_redoc_available(client: TestClient):
    """Test that ReDoc is available."""
    response = client.get("/redoc")
    assert response.status_code == 200
    assert "redoc" in response.text.lower()


def test_openapi_schema_available(client: TestClient):
    """Test that OpenAPI schema is available."""
    response = client.get("/openapi.json")
    assert response.status_code == 200
    schema = response.json()
    assert "openapi" in schema
    assert "info" in schema
    assert "paths" in schema