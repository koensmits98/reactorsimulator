from sqlalchemy import create_engine

from alembic import context
from app.db.models import Base
from app.db.session import DATABASE_URL

target_metadata = Base.metadata

if context.config.config_file_name:
    from logging.config import fileConfig

    fileConfig(context.config.config_file_name)

engine = create_engine(DATABASE_URL)
with engine.connect() as connection:
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()
