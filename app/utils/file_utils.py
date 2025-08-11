"""
File utility functions.
"""
import os
import hashlib
import magic
from pathlib import Path
from typing import Optional
import structlog

logger = structlog.get_logger()


def get_file_hash(file_path: str) -> str:
    """
    Calculate SHA256 hash of a file.
    
    Args:
        file_path: Path to file
        
    Returns:
        SHA256 hash as hex string
    """
    sha256_hash = hashlib.sha256()
    with open(file_path, "rb") as f:
        for byte_block in iter(lambda: f.read(4096), b""):
            sha256_hash.update(byte_block)
    return sha256_hash.hexdigest()


def get_file_type(file_path: str) -> Optional[str]:
    """
    Get MIME type of a file using python-magic.
    
    Args:
        file_path: Path to file
        
    Returns:
        MIME type string or None
    """
    try:
        return magic.from_file(file_path, mime=True)
    except Exception as e:
        logger.warning(f"Failed to get file type: {e}")
        return None


def validate_hwp_file(file_path: str) -> bool:
    """
    Validate if file is a valid HWP file.
    
    Args:
        file_path: Path to file
        
    Returns:
        True if valid HWP file, False otherwise
    """
    # Check extension
    ext = Path(file_path).suffix.lower()
    if ext not in ['.hwp', '.hwpx']:
        return False
    
    # Check MIME type
    mime_type = get_file_type(file_path)
    if mime_type:
        # HWP files are often detected as application/x-ole-storage
        # or application/vnd.hancom.hwp
        valid_types = [
            'application/x-ole-storage',
            'application/vnd.hancom.hwp',
            'application/haansofthwp',
            'application/x-hwp',
            'application/octet-stream'  # Sometimes misidentified
        ]
        if mime_type not in valid_types:
            logger.warning(f"Unexpected MIME type for HWP: {mime_type}")
    
    # Check file signature (HWP files start with specific bytes)
    try:
        with open(file_path, 'rb') as f:
            header = f.read(8)
            # HWP v5 files start with "HWP Document File"
            # or have OLE signature D0CF11E0A1B11AE1
            ole_signature = b'\xD0\xCF\x11\xE0\xA1\xB1\x1A\xE1'
            if header.startswith(ole_signature):
                return True
            # Some HWP files might have different signatures
            if header.startswith(b'HWP'):
                return True
    except Exception as e:
        logger.error(f"Failed to read file header: {e}")
        return False
    
    return True


def cleanup_file(file_path: str):
    """
    Safely remove a file if it exists.
    
    Args:
        file_path: Path to file to remove
    """
    try:
        if os.path.exists(file_path):
            os.remove(file_path)
            logger.debug(f"Cleaned up file: {file_path}")
    except Exception as e:
        logger.warning(f"Failed to cleanup file {file_path}: {e}")


def ensure_directory(directory: str):
    """
    Ensure directory exists, create if not.
    
    Args:
        directory: Path to directory
    """
    Path(directory).mkdir(parents=True, exist_ok=True)