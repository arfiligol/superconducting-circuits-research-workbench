"""Unit of Work pattern implementation for SQLite."""

from types import TracebackType

from sqlmodel import Session

from core.shared.persistence.database import get_session, init_db
from core.shared.persistence.repositories import (
    AuditLogRepository,
    CircuitRepository,
    DataRecordRepository,
    DatasetRepository,
    DerivedParameterRepository,
    ParameterDesignationRepository,
    ResultBundleRepository,
    TagRepository,
    TaskRepository,
    UserRepository,
)


class SqliteUnitOfWork:
    """Unit of Work for SQLite database operations."""

    def __init__(self, session: Session | None = None):
        self._session = session or get_session()
        self._owns_session = session is None

    @property
    def datasets(self) -> DatasetRepository:
        """Access DatasetRecord repository."""
        return DatasetRepository(self._session)

    @property
    def data_records(self) -> DataRecordRepository:
        """Access DataRecord repository."""
        return DataRecordRepository(self._session)

    @property
    def tags(self) -> TagRepository:
        """Access Tag repository."""
        return TagRepository(self._session)

    @property
    def derived_params(self) -> DerivedParameterRepository:
        """Access DerivedParameter repository."""
        return DerivedParameterRepository(self._session)

    @property
    def designations(self) -> ParameterDesignationRepository:
        """Access ParameterDesignation repository."""
        return ParameterDesignationRepository(self._session)

    @property
    def result_bundles(self) -> ResultBundleRepository:
        """Access ResultBundleRecord repository."""
        return ResultBundleRepository(self._session)

    @property
    def circuits(self) -> CircuitRepository:
        """Access CircuitRecord repository."""
        return CircuitRepository(self._session)

    @property
    def tasks(self) -> TaskRepository:
        """Access TaskRecord repository."""
        return TaskRepository(self._session)

    @property
    def users(self) -> UserRepository:
        """Access UserRecord repository."""
        return UserRepository(self._session)

    @property
    def audit_logs(self) -> AuditLogRepository:
        """Access AuditLogRecord repository."""
        return AuditLogRepository(self._session)

    def __enter__(self) -> "SqliteUnitOfWork":
        """Enter context manager."""
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        """Exit context manager."""
        if exc_type is not None:
            self.rollback()
        if self._owns_session:
            self._session.close()

    def commit(self) -> None:
        """Commit the current transaction."""
        self._session.commit()

    def flush(self) -> None:
        """Flush pending changes without committing."""
        self._session.flush()

    def rollback(self) -> None:
        """Rollback the current transaction."""
        self._session.rollback()


def get_unit_of_work() -> SqliteUnitOfWork:
    """
    Get a new Unit of Work instance.

    Usage:
        with get_unit_of_work() as uow:
            dataset = uow.datasets.get_by_name("my_dataset")
            uow.datasets.add(new_dataset)
            uow.commit()
    """
    init_db()  # Ensure tables exist
    return SqliteUnitOfWork()
