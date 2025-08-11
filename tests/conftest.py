"""
Pytest configuration and fixtures.
"""
import pytest
import asyncio
from typing import Generator
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def client() -> Generator[TestClient, None, None]:
    """Create a test client for the FastAPI app."""
    with TestClient(app) as c:
        yield c


@pytest.fixture
def sample_hwp_content():
    """Sample HWP parsed content for testing."""
    return {
        "metadata": {
            "title": "Test Document",
            "author": "Test Author",
            "subject": "Test Subject",
            "created": "2024-01-01",
            "modified": "2024-01-02"
        },
        "paragraphs": [
            {"text": "This is the first paragraph."},
            {"text": "This is the second paragraph with Korean text: 안녕하세요"},
            {"text": "This is the third paragraph."}
        ],
        "tables": [
            {
                "index": 0,
                "rows": [
                    ["Header 1", "Header 2"],
                    ["Cell 1", "Cell 2"],
                    ["Cell 3", "Cell 4"]
                ]
            }
        ],
        "text": "This is the first paragraph.\n\nThis is the second paragraph with Korean text: 안녕하세요\n\nThis is the third paragraph."
    }