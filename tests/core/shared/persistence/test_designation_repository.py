"""Tests for designation and derived-parameter repository helpers."""

from core.shared.persistence.models import (
    DerivedParameter,
    DesignRecord,
    DeviceType,
    ParameterDesignation,
)
from core.shared.persistence.unit_of_work import SqliteUnitOfWork
from sqlmodel import Session, SQLModel, create_engine


def _memory_session() -> Session:
    engine = create_engine("sqlite://")
    SQLModel.metadata.create_all(engine)
    return Session(engine)


def test_designation_repository_unique_lookup_and_exclusion() -> None:
    with _memory_session() as session:
        uow = SqliteUnitOfWork(session)
        design = uow.datasets.add(DesignRecord(name="D1", source_meta={}, parameters={}))
        uow.flush()
        assert design.id is not None

        first = uow.designations.add(
            ParameterDesignation(
                dataset_id=design.id,
                designated_name="f_q",
                source_analysis_type="fit",
                source_parameter_name="mode_1_ghz",
            )
        )
        second = uow.designations.add(
            ParameterDesignation(
                dataset_id=design.id,
                designated_name="f_q",
                source_analysis_type="fit",
                source_parameter_name="mode_2_ghz",
            )
        )
        uow.commit()
        assert first.id is not None
        assert second.id is not None
        assert first.design_id == design.id
        assert second.design_id == design.id

        found = uow.designations.find_unique_by_design(
            design_id=design.id,
            designated_name="f_q",
            source_analysis_type="fit",
            source_parameter_name="mode_1_ghz",
        )
        assert found is not None
        assert found.id == first.id

        excluded = uow.designations.find_unique_by_design(
            design_id=design.id,
            designated_name="f_q",
            source_analysis_type="fit",
            source_parameter_name="mode_2_ghz",
            exclude_id=second.id,
        )
        assert excluded is None

        legacy_found = uow.designations.find_unique(
            dataset_id=design.id,
            designated_name="f_q",
            source_analysis_type="fit",
            source_parameter_name="mode_1_ghz",
        )
        assert legacy_found is not None
        assert legacy_found.id == first.id


def test_derived_parameter_repository_exact_and_prefix_lookups() -> None:
    with _memory_session() as session:
        uow = SqliteUnitOfWork(session)
        design = uow.datasets.add(DesignRecord(name="D2", source_meta={}, parameters={}))
        uow.flush()
        assert design.id is not None

        mode_base = uow.derived_params.add(
            DerivedParameter(
                dataset_id=design.id,
                device_type=DeviceType.RESONATOR,
                name="mode_1_ghz",
                value=5.01,
                method="fit",
                unit="GHz",
                extra={},
            )
        )
        mode_bias = uow.derived_params.add(
            DerivedParameter(
                dataset_id=design.id,
                device_type=DeviceType.RESONATOR,
                name="mode_1_ghz_b0",
                value=5.02,
                method="fit",
                unit="GHz",
                extra={},
            )
        )
        mode_prefix_first = uow.derived_params.add(
            DerivedParameter(
                dataset_id=design.id,
                device_type=DeviceType.RESONATOR,
                name="mode_2_ghz_b1",
                value=5.11,
                method="fit",
                unit="GHz",
                extra={},
            )
        )
        uow.derived_params.add(
            DerivedParameter(
                dataset_id=design.id,
                device_type=DeviceType.RESONATOR,
                name="mode_2_ghz_b2",
                value=5.12,
                method="fit",
                unit="GHz",
                extra={},
            )
        )
        uow.commit()
        assert mode_base.id is not None
        assert mode_bias.id is not None
        assert mode_prefix_first.id is not None
        assert mode_base.design_id == design.id
        assert mode_bias.design_id == design.id
        assert mode_prefix_first.design_id == design.id

        by_name = uow.derived_params.get_by_design_and_name(design.id, "mode_1_ghz")
        assert by_name is not None
        assert by_name.id == mode_base.id

        by_exact = uow.derived_params.get_by_design_method_and_name(
            design.id,
            "fit",
            "mode_1_ghz_b0",
        )
        assert by_exact is not None
        assert by_exact.id == mode_bias.id

        by_prefix = uow.derived_params.get_first_by_design_method_name_prefix(
            design.id,
            "fit",
            "mode_2_ghz",
        )
        assert by_prefix is not None
        assert by_prefix.id == mode_prefix_first.id

        legacy_by_name = uow.derived_params.get_by_dataset_and_name(design.id, "mode_1_ghz")
        assert legacy_by_name is not None
        assert legacy_by_name.id == mode_base.id
