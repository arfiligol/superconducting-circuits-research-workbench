from __future__ import annotations

from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool
from src.app.infrastructure.persistence.database import build_sqlite_database_url
from src.app.infrastructure.persistence.models import RewriteMetadataBase
from src.app.settings import AppSettings

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = RewriteMetadataBase.metadata


def run_migrations_offline() -> None:
    url = _resolve_database_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    configuration = config.get_section(config.config_ini_section, {})
    configuration["sqlalchemy.url"] = _resolve_database_url()
    connectable = engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)

        with context.begin_transaction():
            context.run_migrations()


def _resolve_database_url() -> str:
    configured_url = config.get_main_option("sqlalchemy.url")
    if configured_url and not configured_url.endswith("./data/database.db"):
        return configured_url
    settings = AppSettings()
    return build_sqlite_database_url(settings.database_path)


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
