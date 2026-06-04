"""Repository contract tests for page-orchestration critical APIs."""

from core.shared.persistence.models import DesignRecord
from core.shared.persistence.repositories import (
    AnalysisRunPersistenceContract,
    AuditLogPersistenceContract,
    DataRecordCharacterizationContract,
    ResultBundleCharacterizationContract,
    ResultBundleDatasetSummaryContract,
    ResultBundleRepository,
    ResultBundleSnapshotContract,
    TaskPersistenceContract,
    TraceBatchCharacterizationContract,
    TraceBatchDesignSummaryContract,
    TraceBatchRepository,
    TraceBatchSnapshotContract,
    TraceCharacterizationContract,
    TraceRepository,
    UserPersistenceContract,
)
from core.shared.persistence.unit_of_work import SqliteUnitOfWork
from sqlmodel import Session, SQLModel, create_engine


def _memory_session() -> Session:
    engine = create_engine("sqlite://")
    SQLModel.metadata.create_all(engine)
    return Session(engine)


def test_trace_repository_satisfies_canonical_characterization_contract() -> None:
    with _memory_session() as session:
        design = DesignRecord(name="Contract Design", source_meta={}, parameters={})
        session.add(design)
        session.commit()
        session.refresh(design)
        assert design.id is not None

        repo = TraceRepository(session)

        assert isinstance(repo, TraceCharacterizationContract)
        assert isinstance(repo, DataRecordCharacterizationContract)
        assert repo.count_by_design(design.id) == 0
        assert repo.list_distinct_index_for_profile(design.id) == []

        rows, total = repo.list_index_page_by_design(design.id)
        assert rows == []
        assert total == 0


def test_trace_batch_repository_satisfies_characterization_contracts() -> None:
    with _memory_session() as session:
        repo = TraceBatchRepository(session)
        assert isinstance(repo, TraceBatchCharacterizationContract)
        assert isinstance(repo, ResultBundleCharacterizationContract)
        assert isinstance(repo.analysis_runs, AnalysisRunPersistenceContract)
        assert repo.count_traces(1) == 0

        rows, total = repo.list_trace_index_page(1)
        assert rows == []
        assert total == 0


def test_trace_batch_repository_satisfies_design_summary_contracts() -> None:
    with _memory_session() as session:
        design = DesignRecord(name="Summary Contract Design", source_meta={}, parameters={})
        session.add(design)
        session.commit()
        session.refresh(design)
        assert design.id is not None

        repo = TraceBatchRepository(session)
        assert isinstance(repo, TraceBatchDesignSummaryContract)
        assert isinstance(repo, ResultBundleDatasetSummaryContract)
        assert repo.count_by_design(design.id) == 0
        assert repo.list_analysis_run_summaries_by_design(design.id) == []


def test_trace_batch_repository_satisfies_snapshot_contracts() -> None:
    with _memory_session() as session:
        repo = TraceBatchRepository(session)
        assert isinstance(repo, TraceBatchSnapshotContract)
        assert isinstance(repo, ResultBundleSnapshotContract)
        assert repo.get_trace_batch_snapshot(1) is None
        assert repo.get_snapshot(1) is None


def test_legacy_aliases_still_expose_canonical_repositories() -> None:
    with _memory_session():
        assert TraceRepository is not None
        assert TraceBatchRepository is not None
        assert ResultBundleRepository is TraceBatchRepository


def test_unit_of_work_exposes_task_auth_and_audit_contracts() -> None:
    with _memory_session() as session:
        uow = SqliteUnitOfWork(session)

        assert isinstance(uow.tasks, TaskPersistenceContract)
        assert isinstance(uow.users, UserPersistenceContract)
        assert isinstance(uow.audit_logs, AuditLogPersistenceContract)

        assert uow.tasks.get_task(1) is None
        assert uow.users.get_by_id(1) is None
        assert uow.audit_logs.list_logs() == []
        assert uow.designations.list_all() == []
