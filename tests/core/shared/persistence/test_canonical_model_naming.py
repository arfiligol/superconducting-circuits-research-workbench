"""Tests for canonical dataset/design persistence naming."""

from datetime import UTC

from core.shared.persistence.models import (
    DerivedParameter,
    DeviceType,
    ParameterDesignation,
    PersistedScopeIds,
    TraceBatchRecord,
    TraceRecord,
    ensure_scope_ids,
    require_explicit_scope_ids,
    resolve_scope_ids_for_compatibility_write,
    resolve_scope_ids_for_write,
)


def test_design_scoped_records_keep_dataset_and_design_scope_distinct() -> None:
    trace = TraceRecord(
        dataset_id=11,
        design_id=101,
        data_type="y_parameters",
        parameter="Y11",
        representation="imaginary",
        axes=[],
        values=[],
        store_ref={},
    )
    batch = TraceBatchRecord(
        dataset_id=12,
        design_id=102,
        bundle_type="circuit_simulation",
        role="cache",
        status="completed",
        source_meta={},
        config_snapshot={},
        result_payload={},
    )
    derived = DerivedParameter(
        dataset_id=13,
        design_id=103,
        device_type=DeviceType.RESONATOR,
        name="mode_1_ghz",
        value=5.0,
        unit="GHz",
        method="fit",
        extra={},
    )
    designation = ParameterDesignation(
        dataset_id=14,
        design_id=104,
        designated_name="f_q",
        source_analysis_type="fit",
        source_parameter_name="mode_1_ghz",
    )

    assert trace.dataset_id == 11
    assert trace.design_id == 101
    assert trace.created_at.tzinfo == UTC
    assert batch.dataset_id == 12
    assert batch.design_id == 102
    assert batch.created_at.tzinfo == UTC
    assert derived.dataset_id == 13
    assert derived.design_id == 103
    assert derived.created_at.tzinfo == UTC
    assert designation.dataset_id == 14
    assert designation.design_id == 104
    assert designation.created_at.tzinfo == UTC


def test_canonical_scope_write_requires_explicit_dataset_and_design_ids() -> None:
    trace = TraceRecord(
        dataset_id=21,
        data_type="y_parameters",
        parameter="Y11",
        representation="imaginary",
        axes=[],
        values=[],
        store_ref={},
    )

    try:
        require_explicit_scope_ids(trace)
    except ValueError as exc:
        assert str(exc) == "Explicit design_id is required for canonical persistence writes."
    else:
        raise AssertionError("Expected canonical write validation to reject missing design_id.")


def test_design_scoped_records_apply_explicit_legacy_scope_shim_when_design_id_missing() -> None:
    trace = TraceRecord(
        dataset_id=21,
        data_type="y_parameters",
        parameter="Y11",
        representation="imaginary",
        axes=[],
        values=[],
        store_ref={},
    )

    scope_ids = ensure_scope_ids(trace)

    assert trace.dataset_id == 21
    assert trace.design_id == 21
    assert scope_ids.dataset_id == 21
    assert scope_ids.design_id == 21
    assert scope_ids.used_legacy_design_fallback is True

    explicit_compat_scope_ids = resolve_scope_ids_for_compatibility_write(trace)
    assert explicit_compat_scope_ids == PersistedScopeIds(
        dataset_id=21,
        design_id=21,
        used_legacy_design_fallback=False,
    )


def test_scope_write_helpers_keep_strict_and_compatibility_paths_distinct() -> None:
    canonical_trace = TraceRecord(
        dataset_id=31,
        design_id=41,
        data_type="y_parameters",
        parameter="Y11",
        representation="imaginary",
        axes=[],
        values=[],
        store_ref={},
    )
    legacy_trace = TraceRecord(
        dataset_id=32,
        data_type="y_parameters",
        parameter="Y21",
        representation="real",
        axes=[],
        values=[],
        store_ref={},
    )

    canonical_scope_ids = resolve_scope_ids_for_write(canonical_trace)
    legacy_scope_ids = resolve_scope_ids_for_compatibility_write(legacy_trace)

    assert canonical_scope_ids == PersistedScopeIds(
        dataset_id=31,
        design_id=41,
        used_legacy_design_fallback=False,
    )
    assert legacy_scope_ids == PersistedScopeIds(
        dataset_id=32,
        design_id=32,
        used_legacy_design_fallback=True,
    )

    strict_legacy_trace = TraceRecord(
        dataset_id=33,
        data_type="y_parameters",
        parameter="Y31",
        representation="real",
        axes=[],
        values=[],
        store_ref={},
    )
    try:
        resolve_scope_ids_for_write(strict_legacy_trace)
    except ValueError as exc:
        assert str(exc) == "Explicit design_id is required for canonical persistence writes."
    else:
        raise AssertionError("Expected strict write helper to reject compatibility fallback.")


def test_require_explicit_scope_ids_does_not_mutate_missing_design_scope() -> None:
    trace = TraceRecord(
        dataset_id=51,
        data_type="y_parameters",
        parameter="Y11",
        representation="imaginary",
        axes=[],
        values=[],
        store_ref={},
    )

    try:
        require_explicit_scope_ids(trace)
    except ValueError as exc:
        assert str(exc) == "Explicit design_id is required for canonical persistence writes."
    else:
        raise AssertionError("Expected explicit scope validation to reject missing design_id.")

    assert trace.dataset_id == 51
    assert trace.design_id is None
