"""
Database setup using SQLAlchemy.

We create:
- an Engine bound to the DATABASE_URL from config
- a SessionLocal factory for request/collector sessions
- a Base class to declare ORM models
"""

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

from app.config import settings

# Engine: the core connection to the DB (SQLite by default)
engine = create_engine(
    settings.database_url,
    future=True,
    echo=False,  # set True if you want to see SQL in the logs
)

# Session factory: each "unit of work" gets its own session
SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
    future=True,
)

# Base class for all ORM models
Base = declarative_base()
