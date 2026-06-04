from __future__ import annotations

import os
from typing import Generator, Optional

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session

from app.models.db_models import Base

# DATABASE_URL can be overridden via env var for easy migration to Postgres later
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./data/plum_adjudication.db")

# For SQLite, need check_same_thread
connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}

engine = create_engine(DATABASE_URL, connect_args=connect_args, echo=False)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db() -> Generator[Session, None, None]:
    db: Session = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def create_tables(engine_override: Optional = None) -> None:
    """Create database tables using models' metadata.

    Args:
        engine_override: Optional SQLAlchemy engine to use instead of module-level engine.
    """
    eng = engine_override or engine
    # Ensure directory exists for SQLite databases
    try:
        db_url = os.getenv("DATABASE_URL", DATABASE_URL)
        if db_url.startswith("sqlite"):
            # strip sqlite prefix and ensure parent directory exists
            path = db_url.replace("sqlite://", "")
            # remove leading slashes
            path = path.lstrip('/')
            dirpath = os.path.dirname(path) or "."
            os.makedirs(dirpath, exist_ok=True)
    except Exception:
        # best-effort; don't block table creation if dir check fails
        pass

    Base.metadata.create_all(bind=eng)


if __name__ == "__main__":
    # quick helper for local dev: create DB and tables
    os.makedirs(os.path.dirname(DATABASE_URL.replace("sqlite:///", "")), exist_ok=True)
    create_tables()
    print("Tables created at", DATABASE_URL)
