"""
Custom exceptions for HWP API.
"""


class HWPAPIException(Exception):
    """Base exception for HWP API."""
    pass


class FileValidationError(HWPAPIException):
    """Raised when file validation fails."""
    pass


class ConversionError(HWPAPIException):
    """Raised when conversion fails."""
    pass


class DependencyError(HWPAPIException):
    """Raised when required dependencies are missing."""
    pass


class TimeoutError(HWPAPIException):
    """Raised when operation times out."""
    pass