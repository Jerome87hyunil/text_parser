"""
Database base configuration
"""
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import Session

Base = declarative_base()

class DatabaseBase:
    """Base class for database models"""
    __abstract__ = True
    
    @classmethod
    def create(cls, db: Session, **kwargs):
        """Create a new record"""
        instance = cls(**kwargs)
        db.add(instance)
        db.commit()
        db.refresh(instance)
        return instance
    
    def update(self, db: Session, **kwargs):
        """Update record"""
        for key, value in kwargs.items():
            setattr(self, key, value)
        db.commit()
        db.refresh(self)
        return self
    
    def delete(self, db: Session):
        """Delete record"""
        db.delete(self)
        db.commit()
        return True