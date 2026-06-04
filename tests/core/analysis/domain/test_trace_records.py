"""Tests for canonical trace-record naming helpers."""

from superconducting_circuits_analysis.domain.trace_records import (
    normalize_trace_record,
    trace_record_dataset_id,
    trace_record_design_id,
)


def test_trace_record_design_id_prefers_canonical_design_scope() -> None:
    record = {
        "id": 7,
        "design_id": 42,
        "dataset_id": 99,
        "family": "y",
        "parameter": "Y11",
        "representation": "imag",
        "axes": [],
        "values": [],
    }

    normalized = normalize_trace_record(record)

    assert trace_record_design_id(record) == 42
    assert trace_record_dataset_id(record) == 99
    assert normalized.design_id == 42
    assert normalized.dataset_id == 99


def test_trace_record_design_id_requires_explicit_design_scope() -> None:
    record = {
        "id": 8,
        "dataset_id": 17,
        "data_type": "y_parameters",
        "parameter": "Y21",
        "representation": "imaginary",
        "axes": [],
        "values": [],
    }

    normalized = normalize_trace_record(record)

    assert trace_record_design_id(record) is None
    assert trace_record_dataset_id(record) == 17
    assert normalized.design_id is None
    assert normalized.dataset_id == 17
