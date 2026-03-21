"""Tests for record-scope availability evaluator."""

from legacy.legacy_nicegui_archived.features.characterization.query.analysis_registry import ANALYSIS_REGISTRY
from legacy.legacy_nicegui_archived.services.analysis_scope_evaluator import get_available_analyses


def test_get_available_analyses_filters_per_dataset_and_matches_requires() -> None:
    records = [
        {"data_type": "y_parameters", "parameter": "Y11", "representation": "imaginary"},
        {"data_type": "s_parameters", "parameter": "S21", "representation": "real"},
    ]

    available = get_available_analyses(ANALYSIS_REGISTRY, records)
    available_ids = {analysis["id"] for analysis in available}

    assert "admittance_extraction" in available_ids
    assert "s21_resonance_fit" in available_ids
    assert "parameter_comparison" not in available_ids  # cross-dataset only
