from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

DEFAULT_DATABASE_PATH = "data/database.db"
_LEGACY_REWRITE_METADATA_BASELINE_REVISION = "20260321_0005"


def resolve_metadata_database_path(configured_path: str = DEFAULT_DATABASE_PATH) -> Path:
    database_path = Path(configured_path).expanduser()
    if not database_path.is_absolute():
        database_path = (_repo_root() / database_path).resolve()
    database_path.parent.mkdir(parents=True, exist_ok=True)
    return database_path


def build_sqlite_database_url(database_path: Path) -> str:
    return f"sqlite:///{database_path}"


def create_metadata_engine(configured_path: str = DEFAULT_DATABASE_PATH) -> Engine:
    return create_engine(build_sqlite_database_url(resolve_metadata_database_path(configured_path)))


def create_metadata_session_factory(
    configured_path: str = DEFAULT_DATABASE_PATH,
) -> sessionmaker[Session]:
    return sessionmaker(
        bind=create_metadata_engine(configured_path),
        expire_on_commit=False,
    )


def bootstrap_metadata_schema(configured_path: str = DEFAULT_DATABASE_PATH) -> None:
    database_path = resolve_metadata_database_path(configured_path)
    alembic_config = _build_alembic_config(database_path)

    engine = create_engine(build_sqlite_database_url(database_path))
    inspector = inspect(engine)
    table_names = set(inspector.get_table_names())
    if "alembic_version" not in table_names and _has_legacy_rewrite_tables(table_names):
        command.stamp(alembic_config, _LEGACY_REWRITE_METADATA_BASELINE_REVISION)
    command.upgrade(alembic_config, "head")


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[5]


def _backend_root() -> Path:
    return Path(__file__).resolve().parents[4]


def _build_alembic_config(database_path: Path) -> Config:
    backend_root = _backend_root()
    config = Config(str(backend_root / "alembic.ini"))
    config.set_main_option("script_location", str(backend_root / "alembic"))
    config.set_main_option("sqlalchemy.url", build_sqlite_database_url(database_path))
    return config


def _has_legacy_rewrite_tables(table_names: set[str]) -> bool:
    return any(name.startswith("rewrite_") for name in table_names)
