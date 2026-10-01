from pathlib import Path

import pytest
from alembic.config import Config
from fastapi.testclient import TestClient

from alembic import command
from app.main import app


@pytest.fixture(scope="session", autouse=True)
def migrated_database():
    """Build the schema with the real Alembic migration, from an empty database.

    Needs a PostgreSQL server reachable through DATABASE_URL (a service container in CI).
    """
    config = Config(str(Path(__file__).parent.parent / "alembic.ini"))
    config.set_main_option("script_location", str(Path(__file__).parent.parent / "alembic"))
    command.downgrade(config, "base")
    command.upgrade(config, "head")


@pytest.fixture
def client():
    return TestClient(app)
