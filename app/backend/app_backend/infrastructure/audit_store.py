from __future__ import annotations

from pathlib import Path

from sqlalchemy import JSON, String, create_engine, delete, desc, select
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, sessionmaker

from app_backend.domain.audit import AuditListQuery, AuditRecord

DEFAULT_AUDIT_DATABASE_PATH = "data/audit-log.db"


class AuditStoreBase(DeclarativeBase):
    pass


class AuditLogRecordModel(AuditStoreBase):
    __tablename__ = "audit_log_records"

    audit_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    occurred_at: Mapped[str] = mapped_column(String(32), nullable=False)
    actor_user_id: Mapped[str] = mapped_column(String(64), nullable=False)
    actor_display_name: Mapped[str | None] = mapped_column(String(128))
    session_id: Mapped[str] = mapped_column(String(128), nullable=False)
    correlation_id: Mapped[str] = mapped_column(String(128), nullable=False)
    workspace_id: Mapped[str] = mapped_column(String(64), nullable=False)
    action_kind: Mapped[str] = mapped_column(String(128), nullable=False)
    resource_kind: Mapped[str] = mapped_column(String(64), nullable=False)
    resource_id: Mapped[str] = mapped_column(String(128), nullable=False)
    outcome: Mapped[str] = mapped_column(String(16), nullable=False)
    payload_json: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False, default=dict)
    debug_ref: Mapped[str] = mapped_column(String(128), nullable=False)


def resolve_audit_database_path(configured_path: str = DEFAULT_AUDIT_DATABASE_PATH) -> Path:
    database_path = Path(configured_path).expanduser()
    if not database_path.is_absolute():
        database_path = (_repo_root() / database_path).resolve()
    database_path.parent.mkdir(parents=True, exist_ok=True)
    return database_path


def build_audit_database_url(database_path: Path) -> str:
    return f"sqlite:///{database_path}"


def create_audit_engine(configured_path: str = DEFAULT_AUDIT_DATABASE_PATH) -> Engine:
    return create_engine(build_audit_database_url(resolve_audit_database_path(configured_path)))


def create_audit_session_factory(
    configured_path: str = DEFAULT_AUDIT_DATABASE_PATH,
) -> sessionmaker[Session]:
    return sessionmaker(bind=create_audit_engine(configured_path), expire_on_commit=False)


def bootstrap_audit_store(configured_path: str = DEFAULT_AUDIT_DATABASE_PATH) -> None:
    engine = create_audit_engine(configured_path)
    AuditStoreBase.metadata.create_all(engine)


class SqliteAuditLogRepository:
    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self._session_factory = session_factory

    def append(self, record: AuditRecord) -> AuditRecord:
        with self._session_factory() as session, session.begin():
            session.add(_to_model(record))
        return record

    def clear(self) -> None:
        with self._session_factory() as session, session.begin():
            session.execute(delete(AuditLogRecordModel))

    def list_records(self) -> tuple[AuditRecord, ...]:
        return tuple(self.query_records(AuditListQuery(limit=10_000)))

    def list_records_for_resource(
        self,
        *,
        resource_kind: str,
        resource_id: str,
    ) -> tuple[AuditRecord, ...]:
        return tuple(
            record
            for record in self.list_records()
            if record.resource_kind == resource_kind and record.resource_id == resource_id
        )

    def get_record(self, audit_id: str) -> AuditRecord | None:
        with self._session_factory() as session:
            record = session.get(AuditLogRecordModel, audit_id)
            return None if record is None else _to_record(record)

    def query_records(self, query: AuditListQuery) -> tuple[AuditRecord, ...]:
        with self._session_factory() as session:
            rows = session.scalars(
                select(AuditLogRecordModel).order_by(
                    desc(AuditLogRecordModel.occurred_at), desc(AuditLogRecordModel.audit_id)
                )
            ).all()

        records = [_to_record(row) for row in rows if _matches_query(_to_record(row), query)]
        if query.after is not None:
            after_index = _find_record_index(records, query.after)
            if after_index is None:
                return ()
            records = records[after_index + 1 :]
        if query.before is not None:
            before_index = _find_record_index(records, query.before)
            if before_index is None:
                return ()
            records = records[:before_index]
        return tuple(records)


def _matches_query(record: AuditRecord, query: AuditListQuery) -> bool:
    if query.workspace_id is not None and record.workspace_id != query.workspace_id:
        return False
    if query.actor_user_id is not None and record.actor_user_id != query.actor_user_id:
        return False
    if query.action_kind is not None and record.action_kind != query.action_kind:
        return False
    if query.resource_kind is not None and record.resource_kind != query.resource_kind:
        return False
    return query.outcome is None or record.outcome == query.outcome


def _find_record_index(records: list[AuditRecord], audit_id: str) -> int | None:
    for index, record in enumerate(records):
        if record.audit_id == audit_id:
            return index
    return None


def _to_model(record: AuditRecord) -> AuditLogRecordModel:
    return AuditLogRecordModel(
        audit_id=record.audit_id,
        occurred_at=record.occurred_at,
        actor_user_id=record.actor_user_id,
        actor_display_name=record.actor_display_name,
        session_id=record.session_id,
        correlation_id=record.correlation_id,
        workspace_id=record.workspace_id,
        action_kind=record.action_kind,
        resource_kind=record.resource_kind,
        resource_id=record.resource_id,
        outcome=record.outcome,
        payload_json=record.payload,
        debug_ref=record.debug_ref,
    )


def _to_record(model: AuditLogRecordModel) -> AuditRecord:
    return AuditRecord(
        audit_id=model.audit_id,
        occurred_at=model.occurred_at,
        actor_user_id=model.actor_user_id,
        actor_display_name=model.actor_display_name,
        session_id=model.session_id,
        correlation_id=model.correlation_id,
        workspace_id=model.workspace_id,
        action_kind=model.action_kind,
        resource_kind=model.resource_kind,
        resource_id=model.resource_id,
        outcome=model.outcome,  # type: ignore[arg-type]
        payload=model.payload_json,
        debug_ref=model.debug_ref,
    )


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[4]
