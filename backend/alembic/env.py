from logging.config import fileConfig
from pathlib import Path
import sys

from alembic import context
from sqlalchemy import engine_from_config, pool
from sqlmodel import SQLModel

# Ensure migrations can import both backend and root-domain packages
# when invoked from backend/ without manual absolute PYTHONPATH.
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from piios_backend.models import entities  # noqa: F401
from piios.decision_contracts.infrastructure import sqlmodel_entities as decision_sqlmodel_entities  # noqa: F401
from piios.thesis_health.infrastructure import sqlmodel_entities as thesis_health_sqlmodel_entities  # noqa: F401

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = SQLModel.metadata


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(url=url, target_metadata=target_metadata, literal_binds=True)

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
