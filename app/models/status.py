"""
Status response models for various endpoints.
"""
from pydantic import BaseModel, Field
from typing import Optional, Any, Dict
from datetime import datetime


class TaskStatus(BaseModel):
    """Task status response model."""
    task_id: str = Field(..., description="Task ID")
    status: str = Field(..., description="Task status")
    created_at: Optional[datetime] = Field(None, description="Task creation time")
    updated_at: Optional[datetime] = Field(None, description="Last update time")
    progress: Optional[int] = Field(None, description="Progress percentage")
    message: Optional[str] = Field(None, description="Status message")


class TaskResult(BaseModel):
    """Task result response model."""
    task_id: str = Field(..., description="Task ID")
    status: str = Field(..., description="Task status")
    result: Optional[Any] = Field(None, description="Task result")
    error: Optional[str] = Field(None, description="Error message if failed")
    created_at: Optional[datetime] = Field(None, description="Task creation time")
    completed_at: Optional[datetime] = Field(None, description="Task completion time")


class CacheStats(BaseModel):
    """Cache statistics response model."""
    enabled: bool = Field(..., description="Whether cache is enabled")
    backend: str = Field(..., description="Cache backend type")
    items_count: int = Field(..., description="Number of cached items")
    memory_usage: Optional[str] = Field(None, description="Memory usage")
    hit_rate: Optional[float] = Field(None, description="Cache hit rate")
    miss_rate: Optional[float] = Field(None, description="Cache miss rate")
    ttl: int = Field(..., description="Default TTL in seconds")


class SecurityStatus(BaseModel):
    """Security status response model."""
    virus_scanning_enabled: bool = Field(..., description="Whether virus scanning is enabled")
    rate_limiting_enabled: bool = Field(..., description="Whether rate limiting is enabled")
    authentication_enabled: bool = Field(..., description="Whether authentication is enabled")
    encryption_enabled: bool = Field(..., description="Whether encryption is enabled")
    security_level: str = Field(..., description="Current security level")
    last_security_check: Optional[datetime] = Field(None, description="Last security check time")
    threats_detected: int = Field(0, description="Number of threats detected")


class VirusScanStats(BaseModel):
    """Virus scan statistics response model."""
    total_scans: int = Field(..., description="Total number of scans performed")
    threats_detected: int = Field(..., description="Total threats detected")
    files_cleaned: int = Field(..., description="Files cleaned")
    files_quarantined: int = Field(..., description="Files quarantined")
    last_scan: Optional[datetime] = Field(None, description="Last scan time")
    scan_engine: str = Field(..., description="Scan engine being used")
    engine_version: Optional[str] = Field(None, description="Engine version")