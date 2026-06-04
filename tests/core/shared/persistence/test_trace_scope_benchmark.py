"""Large-dataset baseline tests for trace-scope paging queries."""

from __future__ import annotations

from datetime import UTC, datetime
from time import perf_counter

from core.shared.persistence.models import DesignRecord, TraceRecord
from core.shared.persistence.repositories.data_record_repository import TraceRepository
from core.shared.persistence.repositories.query_objects import TraceIndexPageQuery
from sqlmodel import Session, SQLModel, create_engine


def _memory_session() -> Session:
    engine = create_engine("sqlite://")
    SQLModel.metadata.create_all(engine)
    return Session(engine)


def _seed_large_design(session: Session, *, total: int) -> DesignRecord:
    design = DesignRecord(name=f"LargeDesign_{total}", source_meta={}, parameters={})
    session.add(design)
    session.flush()
    assert design.id is not None

    rows = [
        TraceRecord(
            dataset_id=design.id,
            design_id=design.id,
            data_type="y_parameters",
            parameter=f"Y11 [om=(0,), im=({index % 5},)]" if index % 3 == 0 else "Y11",
            representation="imaginary",
            axes=[{"name": "frequency", "unit": "GHz", "values": [5.0, 6.0]}],
            values=[0.01, 0.02],
            created_at=datetime.now(UTC),
        )
        for index in range(total)
    ]
    session.add_all(rows)
    session.commit()
    return design


def test_large_trace_scope_query_returns_paged_rows_under_baseline_time() -> None:
    """JTWPA-scale trace metadata queries should stay on paged path."""
    with _memory_session() as session:
        design = _seed_large_design(session, total=10_000)
        assert design.id is not None

        repo = TraceRepository(session)
        query = TraceIndexPageQuery(
            search="Y11",
            mode_filter="base",
            sort_by="id",
            descending=False,
            limit=20,
            offset=100,
        )

        started = perf_counter()
        rows, total = repo.list_index_page_by_design(design.id, query=query)
        elapsed = perf_counter() - started

        # Zero-mode suffixes are canonical base-mode traces and remain visible here.
        assert total == 7_333
        assert len(rows) == 20
        assert all("family" in row for row in rows)
        assert elapsed < 1.5
