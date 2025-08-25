"""
Database models for PostgreSQL integration
"""
from sqlalchemy import Column, Integer, String, DateTime, Text, Float, Boolean, ForeignKey, JSON, Index
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.db.base import Base, DatabaseBase
from datetime import datetime
import uuid


class User(Base, DatabaseBase):
    """User model for authentication and tracking"""
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    uuid = Column(String(36), unique=True, default=lambda: str(uuid.uuid4()))
    username = Column(String(100), unique=True, index=True, nullable=False)
    email = Column(String(255), unique=True, index=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    is_active = Column(Boolean, default=True)
    is_superuser = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    extraction_jobs = relationship("ExtractionJob", back_populates="user")
    api_keys = relationship("APIKey", back_populates="user")
    
    __table_args__ = (
        Index('idx_user_email', 'email'),
        Index('idx_user_username', 'username'),
    )


class APIKey(Base, DatabaseBase):
    """API Key model for token-based authentication"""
    __tablename__ = "api_keys"
    
    id = Column(Integer, primary_key=True, index=True)
    key = Column(String(64), unique=True, index=True, nullable=False)
    name = Column(String(100))
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    is_active = Column(Boolean, default=True)
    last_used = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    expires_at = Column(DateTime(timezone=True))
    
    # Relationships
    user = relationship("User", back_populates="api_keys")
    
    __table_args__ = (
        Index('idx_api_key', 'key'),
        Index('idx_api_key_user', 'user_id'),
    )


class ExtractionJob(Base, DatabaseBase):
    """Extraction job tracking model"""
    __tablename__ = "extraction_jobs"
    
    id = Column(Integer, primary_key=True, index=True)
    job_id = Column(String(36), unique=True, default=lambda: str(uuid.uuid4()), index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    
    # File information
    filename = Column(String(255), nullable=False)
    file_type = Column(String(10), nullable=False)  # hwp, hwpx, pdf
    file_size = Column(Integer)  # bytes
    file_hash = Column(String(64))  # SHA256 hash
    
    # Processing information
    status = Column(String(20), default="pending")  # pending, processing, completed, failed
    extraction_type = Column(String(20))  # json, text, markdown
    options = Column(JSON)  # Additional extraction options
    
    # Results
    result = Column(JSON)  # Extraction result (for small results)
    result_path = Column(String(255))  # Path to result file (for large results)
    error_message = Column(Text)
    
    # Metrics
    processing_time = Column(Float)  # seconds
    memory_used = Column(Integer)  # bytes
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    started_at = Column(DateTime(timezone=True))
    completed_at = Column(DateTime(timezone=True))
    
    # Relationships
    user = relationship("User", back_populates="extraction_jobs")
    
    __table_args__ = (
        Index('idx_job_id', 'job_id'),
        Index('idx_job_user', 'user_id'),
        Index('idx_job_status', 'status'),
        Index('idx_job_created', 'created_at'),
        Index('idx_job_file_hash', 'file_hash'),
    )


class CacheEntry(Base, DatabaseBase):
    """Cache entry tracking for Redis cache management"""
    __tablename__ = "cache_entries"
    
    id = Column(Integer, primary_key=True, index=True)
    cache_key = Column(String(255), unique=True, index=True, nullable=False)
    file_hash = Column(String(64), index=True)
    extraction_type = Column(String(20))
    size = Column(Integer)  # bytes
    hit_count = Column(Integer, default=0)
    last_accessed = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    expires_at = Column(DateTime(timezone=True))
    
    __table_args__ = (
        Index('idx_cache_key', 'cache_key'),
        Index('idx_cache_hash', 'file_hash'),
        Index('idx_cache_expires', 'expires_at'),
    )


class SystemMetric(Base, DatabaseBase):
    """System metrics for monitoring"""
    __tablename__ = "system_metrics"
    
    id = Column(Integer, primary_key=True, index=True)
    metric_type = Column(String(50), nullable=False)  # cpu, memory, disk, api_calls
    metric_name = Column(String(100), nullable=False)
    value = Column(Float, nullable=False)
    unit = Column(String(20))
    metric_data = Column(JSON)  # Changed from 'metadata' to 'metric_data' to avoid SQLAlchemy reserved word
    timestamp = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    
    __table_args__ = (
        Index('idx_metric_type', 'metric_type'),
        Index('idx_metric_timestamp', 'timestamp'),
        Index('idx_metric_type_time', 'metric_type', 'timestamp'),
    )


class AuditLog(Base, DatabaseBase):
    """Audit log for security and compliance"""
    __tablename__ = "audit_logs"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    action = Column(String(100), nullable=False)  # login, logout, extract, delete, etc.
    resource = Column(String(255))  # Resource being accessed
    ip_address = Column(String(45))  # IPv4 or IPv6
    user_agent = Column(Text)
    request_data = Column(JSON)
    response_status = Column(Integer)
    error_message = Column(Text)
    timestamp = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    
    __table_args__ = (
        Index('idx_audit_user', 'user_id'),
        Index('idx_audit_action', 'action'),
        Index('idx_audit_timestamp', 'timestamp'),
        Index('idx_audit_user_time', 'user_id', 'timestamp'),
    )