import os
from collections.abc import Iterator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

DATABASE_URL = os.environ.get(
    "DATABASE_URL", "postgresql+psycopg://reactor:reactor@localhost:5432/reactor"
)

# A small pool: the server has 512 MB of RAM and Postgres allows only ~20 connections.
engine = create_engine(DATABASE_URL, pool_size=3, max_overflow=2, pool_pre_ping=True)
SessionLocal = sessionmaker(engine, expire_on_commit=False)


def get_db() -> Iterator[Session]:
    """FastAPI dependency: one database session per request, always closed afterwards."""
    with SessionLocal() as session:
        yield session
