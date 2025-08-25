"""
Enhanced file validation utilities
"""
import os
import hashlib
import structlog
from typing import Optional, Tuple, Dict, Any
from pathlib import Path
import zipfile
import tempfile
import asyncio

# Try to import magic, but make it optional
try:
    import magic
    MAGIC_AVAILABLE = True
except ImportError:
    logger = structlog.get_logger()
    logger.warning("python-magic not available, MIME type validation will be limited")
    MAGIC_AVAILABLE = False

from app.utils.virus_scanner import virus_scanner

logger = structlog.get_logger()

# Define allowed MIME types and extensions
ALLOWED_EXTENSIONS = {
    '.hwp': ['application/x-hwp', 'application/haansofthwp', 'application/vnd.hancom.hwp'],
    '.hwpx': ['application/vnd.hancom.hwpx', 'application/zip'],
    '.pdf': ['application/pdf']
}

# Maximum file sizes by type (in bytes)
MAX_FILE_SIZES = {
    '.hwp': 50 * 1024 * 1024,   # 50MB for HWP
    '.hwpx': 100 * 1024 * 1024,  # 100MB for HWPX (can contain images)
    '.pdf': 100 * 1024 * 1024    # 100MB for PDF
}

# Dangerous patterns to check in files
DANGEROUS_PATTERNS = [
    b'<script',
    b'javascript:',
    b'vbscript:',
    b'onload=',
    b'onerror=',
    b'onclick=',
    b'<iframe',
    b'<object',
    b'<embed',
    b'cmd.exe',
    b'powershell',
    b'/bin/sh',
    b'/bin/bash'
]


class FileValidator:
    """Enhanced file validation with security checks"""
    
    def __init__(self):
        self.allowed_extensions = set(ALLOWED_EXTENSIONS.keys())
        self.max_file_size = max(MAX_FILE_SIZES.values())
        if MAGIC_AVAILABLE:
            self.mime = magic.Magic(mime=True)
            self.file_magic = magic.Magic()
        else:
            self.mime = None
            self.file_magic = None
    
    def calculate_file_hash(self, file_path: str) -> str:
        """Calculate SHA256 hash of file"""
        sha256_hash = hashlib.sha256()
        with open(file_path, "rb") as f:
            for byte_block in iter(lambda: f.read(4096), b""):
                sha256_hash.update(byte_block)
        return sha256_hash.hexdigest()
    
    def validate_extension(self, filename: str) -> Tuple[bool, Optional[str]]:
        """Validate file extension"""
        if not filename:
            return False, "No filename provided"
        
        file_ext = Path(filename).suffix.lower()
        if file_ext not in ALLOWED_EXTENSIONS:
            return False, f"File extension '{file_ext}' not allowed. Allowed: {list(ALLOWED_EXTENSIONS.keys())}"
        
        return True, None
    
    def validate_mime_type(self, file_path: str, expected_ext: str) -> Tuple[bool, Optional[str]]:
        """Validate MIME type matches expected extension"""
        if not MAGIC_AVAILABLE or not self.mime:
            # Fallback to extension-based validation
            logger.warning("MIME type validation skipped (python-magic not available)")
            return True, None
            
        try:
            mime_type = self.mime.from_file(file_path)
            allowed_mimes = ALLOWED_EXTENSIONS.get(expected_ext, [])
            
            if mime_type not in allowed_mimes:
                # Special case for HWPX which is essentially a ZIP
                if expected_ext == '.hwpx' and mime_type == 'application/zip':
                    # Further validate it's actually HWPX
                    if self.is_valid_hwpx(file_path):
                        return True, None
                
                return False, f"MIME type '{mime_type}' not allowed for {expected_ext}. Expected: {allowed_mimes}"
            
            return True, None
        except Exception as e:
            logger.error("Failed to check MIME type", error=str(e))
            return False, f"Failed to determine file type: {str(e)}"
    
    def is_valid_hwpx(self, file_path: str) -> bool:
        """Check if ZIP file is actually HWPX"""
        try:
            with zipfile.ZipFile(file_path, 'r') as zip_file:
                # HWPX should contain specific structure
                namelist = zip_file.namelist()
                required_files = ['version.xml', 'Contents/content.hpf']
                return any(name in namelist for name in required_files)
        except:
            return False
    
    def validate_file_size(self, file_path: str, file_ext: str) -> Tuple[bool, Optional[str]]:
        """Validate file size"""
        file_size = os.path.getsize(file_path)
        max_size = MAX_FILE_SIZES.get(file_ext, 10 * 1024 * 1024)  # Default 10MB
        
        if file_size > max_size:
            return False, f"File too large: {file_size} bytes. Maximum: {max_size} bytes"
        
        if file_size == 0:
            return False, "File is empty"
        
        return True, None
    
    def scan_for_threats(self, file_path: str) -> Tuple[bool, Optional[str]]:
        """Scan file for dangerous patterns"""
        try:
            with open(file_path, 'rb') as f:
                # Read file in chunks to avoid memory issues
                while True:
                    chunk = f.read(1024 * 1024)  # 1MB chunks
                    if not chunk:
                        break
                    
                    for pattern in DANGEROUS_PATTERNS:
                        if pattern in chunk:
                            logger.warning("Dangerous pattern detected", 
                                         pattern=pattern.decode('utf-8', errors='ignore'))
                            return False, f"Potentially dangerous content detected"
            
            return True, None
        except Exception as e:
            logger.error("Failed to scan file", error=str(e))
            return False, f"Failed to scan file: {str(e)}"
    
    def validate_file_structure(self, file_path: str, file_ext: str) -> Tuple[bool, Optional[str]]:
        """Validate internal file structure"""
        try:
            if file_ext == '.hwp':
                # Check if it's a valid OLE file
                import olefile
                if not olefile.isOleFile(file_path):
                    return False, "Invalid HWP file structure"
            
            elif file_ext == '.hwpx':
                # Check if it's a valid ZIP with HWPX structure
                if not zipfile.is_zipfile(file_path):
                    return False, "Invalid HWPX file structure"
                if not self.is_valid_hwpx(file_path):
                    return False, "ZIP file is not a valid HWPX"
            
            elif file_ext == '.pdf':
                # Basic PDF validation
                with open(file_path, 'rb') as f:
                    header = f.read(5)
                    if header != b'%PDF-':
                        return False, "Invalid PDF file structure"
            
            return True, None
        except Exception as e:
            logger.error("Failed to validate file structure", error=str(e))
            return False, f"Invalid file structure: {str(e)}"
    
    async def validate_file_async(self, file_path: str, filename: str, enable_virus_scan: bool = True) -> Dict[str, Any]:
        """
        Comprehensive async file validation with virus scanning
        
        Returns:
            Dict with validation results and file metadata
        """
        result = {
            "valid": False,
            "errors": [],
            "warnings": [],
            "metadata": {},
            "virus_scan": None
        }
        
        # Check extension
        valid, error = self.validate_extension(filename)
        if not valid:
            result["errors"].append(error)
            return result
        
        file_ext = Path(filename).suffix.lower()
        
        # Check file size
        valid, error = self.validate_file_size(file_path, file_ext)
        if not valid:
            result["errors"].append(error)
            return result
        
        # Check MIME type
        valid, error = self.validate_mime_type(file_path, file_ext)
        if not valid:
            result["errors"].append(error)
            return result
        
        # Check file structure
        valid, error = self.validate_file_structure(file_path, file_ext)
        if not valid:
            result["errors"].append(error)
            return result
        
        # Scan for threats
        valid, error = self.scan_for_threats(file_path)
        if not valid:
            result["warnings"].append(error)
            # Don't return here, just add warning
        
        # Virus scan (async)
        if enable_virus_scan:
            try:
                scan_result = await virus_scanner.scan_file_async(file_path)
                result["virus_scan"] = scan_result
                
                if scan_result["status"] == "infected":
                    result["errors"].append(f"Virus detected: {scan_result['threats']}")
                    return result
                elif scan_result["status"] == "suspicious":
                    result["warnings"].append(f"Suspicious content: {scan_result['threats']}")
            except Exception as e:
                logger.error("Virus scan failed", error=str(e))
                result["warnings"].append(f"Virus scan failed: {str(e)}")
        
        # Calculate file hash
        file_hash = self.calculate_file_hash(file_path)
        
        # Get file info
        file_size = os.path.getsize(file_path)
        file_type = self.file_magic.from_file(file_path) if self.file_magic else "Unknown"
        
        result["valid"] = len(result["errors"]) == 0
        result["metadata"] = {
            "filename": filename,
            "extension": file_ext,
            "size": file_size,
            "hash": file_hash,
            "type": file_type,
            "mime": self.mime.from_file(file_path) if self.mime else "Unknown"
        }
        
        logger.info("File validation completed", 
                   filename=filename,
                   valid=result["valid"],
                   errors=result["errors"],
                   warnings=result["warnings"],
                   virus_scan_status=result["virus_scan"]["status"] if result["virus_scan"] else "skipped")
        
        return result
    
    def validate_file(self, file_path: str, filename: str) -> Dict[str, Any]:
        """
        Synchronous wrapper for backward compatibility - simplified for development
        """
        # For development, perform basic validation without async
        result = {
            "valid": True,
            "filename": filename,
            "file_path": file_path,
            "errors": [],
            "warnings": []
        }
        
        # Check file exists
        import os
        if not os.path.exists(file_path):
            result["valid"] = False
            result["errors"].append("File does not exist")
            return result
        
        # Check extension
        ext = os.path.splitext(filename)[1].lower()
        if ext not in self.allowed_extensions:
            result["valid"] = False
            result["errors"].append(f"File type {ext} not allowed")
        
        # Check size
        file_size = os.path.getsize(file_path)
        result["file_size"] = file_size
        if file_size > self.max_file_size:
            result["valid"] = False
            result["errors"].append(f"File size {file_size} exceeds maximum {self.max_file_size}")
        
        return result


# Singleton instance
file_validator = FileValidator()