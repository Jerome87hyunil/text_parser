"""
Custom exceptions for the HWP API.
"""
from typing import Optional, Dict, Any


class HWPAPIException(Exception):
    """Base exception for HWP API."""
    
    def __init__(
        self,
        message: str,
        status_code: int = 500,
        details: Optional[Dict[str, Any]] = None
    ):
        self.message = message
        self.status_code = status_code
        self.details = details or {}
        super().__init__(self.message)


class FileValidationError(HWPAPIException):
    """Raised when file validation fails."""
    
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(message, status_code=400, details=details)


class ParsingError(HWPAPIException):
    """Raised when parsing fails."""
    
    def __init__(self, message: str, parser: str = "unknown", details: Optional[Dict[str, Any]] = None):
        details = details or {}
        details["parser"] = parser
        super().__init__(message, status_code=500, details=details)


class FileSizeError(HWPAPIException):
    """Raised when file size exceeds limits."""
    
    def __init__(self, size: int, max_size: int):
        message = f"File size {size} bytes exceeds maximum {max_size} bytes"
        details = {"file_size": size, "max_size": max_size}
        super().__init__(message, status_code=413, details=details)


class RateLimitError(HWPAPIException):
    """Raised when rate limit is exceeded."""
    
    def __init__(self, retry_after: int):
        message = f"Rate limit exceeded. Try again in {retry_after} seconds"
        details = {"retry_after": retry_after}
        super().__init__(message, status_code=429, details=details)


class AuthenticationError(HWPAPIException):
    """Raised when authentication fails."""
    
    def __init__(self, message: str = "Authentication failed"):
        super().__init__(message, status_code=401)


class AuthorizationError(HWPAPIException):
    """Raised when authorization fails."""
    
    def __init__(self, message: str = "Insufficient permissions"):
        super().__init__(message, status_code=403)


class ProcessingTimeoutError(HWPAPIException):
    """Raised when processing times out."""
    
    def __init__(self, timeout: int):
        message = f"Processing timed out after {timeout} seconds"
        details = {"timeout": timeout}
        super().__init__(message, status_code=504, details=details)


class FileTooLargeError(HWPAPIException):
    """Raised when file is too large to process."""
    
    def __init__(self, message: str, size: Optional[int] = None, max_size: Optional[int] = None):
        details = {}
        if size:
            details["file_size"] = size
        if max_size:
            details["max_size"] = max_size
        super().__init__(message, status_code=413, details=details)


class ProcessingError(HWPAPIException):
    """Raised when general processing error occurs."""
    
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(message, status_code=500, details=details)


class ExtractionError(HWPAPIException):
    """Raised when content extraction fails."""
    
    def __init__(self, message: str, extractor: str = "unknown", details: Optional[Dict[str, Any]] = None):
        details = details or {}
        details["extractor"] = extractor
        super().__init__(message, status_code=500, details=details)