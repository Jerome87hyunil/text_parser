"""
Database session management
"""
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import NullPool
from app.core.config import settings
from typing import Generator
import structlog

logger = structlog.get_logger()

# Create database engine
if settings.DATABASE_URL:
    engine = create_engine(
        settings.DATABASE_URL,
        pool_pre_ping=True,  # Verify connections before using
        pool_size=10,  # Connection pool size
        max_overflow=20,  # Maximum overflow connections
        pool_recycle=3600,  # Recycle connections after 1 hour
        echo=settings.DEBUG,  # Log SQL queries in debug mode
    )
else:
    # Use SQLite for development/testing
    engine = create_engine(
        "sqlite:///./hwp_api.db",
        connect_args={"check_same_thread": False},
        poolclass=NullPool,
    )
    logger.warning("Using SQLite database. Configure DATABASE_URL for production.")

# Create session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def get_db() -> Generator[Session, None, None]:
    """
    Get database session
    
    Yields:
        Database session
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()