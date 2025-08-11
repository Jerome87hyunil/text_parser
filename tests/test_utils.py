"""
Utility function tests.
"""
import pytest
import tempfile
import os
from pathlib import Path

from app.utils.file_utils import (
    get_file_hash,
    get_file_type,
    validate_hwp_file,
    cleanup_file,
    ensure_directory
)


def test_get_file_hash():
    """Test file hash calculation."""
    # Create a temporary file with known content
    content = b"Hello, World!"
    with tempfile.NamedTemporaryFile(delete=False) as tmp:
        tmp.write(content)
        tmp_path = tmp.name
    
    try:
        hash_value = get_file_hash(tmp_path)
        assert len(hash_value) == 64  # SHA256 produces 64 hex characters
        assert hash_value == "dffd6021bb2bd5b0af676290809ec3a53191dd81c7f70a4b28688a362182986f"
    finally:
        os.unlink(tmp_path)


def test_validate_hwp_file_valid():
    """Test HWP file validation with valid file."""
    # Create a mock HWP file with OLE signature
    ole_signature = b'\xD0\xCF\x11\xE0\xA1\xB1\x1A\xE1'
    
    with tempfile.NamedTemporaryFile(suffix=".hwp", delete=False) as tmp:
        tmp.write(ole_signature + b'x' * 100)
        tmp_path = tmp.name
    
    try:
        assert validate_hwp_file(tmp_path) is True
    finally:
        os.unlink(tmp_path)


def test_validate_hwp_file_invalid_extension():
    """Test HWP file validation with invalid extension."""
    with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as tmp:
        tmp.write(b"Not an HWP file")
        tmp_path = tmp.name
    
    try:
        assert validate_hwp_file(tmp_path) is False
    finally:
        os.unlink(tmp_path)


def test_validate_hwp_file_invalid_signature():
    """Test HWP file validation with invalid signature."""
    with tempfile.NamedTemporaryFile(suffix=".hwp", delete=False) as tmp:
        tmp.write(b"Invalid HWP content")
        tmp_path = tmp.name
    
    try:
        assert validate_hwp_file(tmp_path) is False
    finally:
        os.unlink(tmp_path)


def test_cleanup_file():
    """Test file cleanup."""
    # Create a temporary file
    with tempfile.NamedTemporaryFile(delete=False) as tmp:
        tmp.write(b"Test content")
        tmp_path = tmp.name
    
    assert os.path.exists(tmp_path)
    
    # Clean up the file
    cleanup_file(tmp_path)
    assert not os.path.exists(tmp_path)
    
    # Should not raise error for non-existent file
    cleanup_file("/non/existent/file.txt")


def test_ensure_directory():
    """Test directory creation."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Test creating nested directories
        test_dir = os.path.join(tmpdir, "a", "b", "c")
        ensure_directory(test_dir)
        assert os.path.exists(test_dir)
        assert os.path.isdir(test_dir)
        
        # Should not raise error if directory already exists
        ensure_directory(test_dir)