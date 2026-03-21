"""Tests for capability gating in analysis registry."""

from legacy.legacy_nicegui_archived.features.characterization.query.analysis_registry import (
    ANALYSIS_REGISTRY,
    AnalysisDescriptor,
    get_analysis_descriptor,
    list_cross_dataset_analyses,
    list_dataset_analyses,
)
from legacy.legacy_nicegui_archived.features.characterization.query.capability import evaluate_analysis_capability_gating


def _analysis_by_id(analysis_id: str) -> AnalysisDescriptor:
    return next(analysis for analysis in ANALYSIS_REGISTRY if analysis["id"] == analysis_id)


def test_dataset_analysis_listing_excludes_cross_dataset_entries() -> None:
    dataset_analyses = list_dataset_analyses()
    assert dataset_analyses
    assert all(analysis["scope"] == "per_dataset" for analysis in dataset_analyses)
    assert all(analysis["id"] != "parameter_comparison" for analysis in dataset_analyses)


def test_cross_dataset_analysis_listing_only_returns_cross_dataset_entries() -> None:
    cross_dataset_analyses = list_cross_dataset_analyses()
    assert cross_dataset_analyses
    assert all(analysis["scope"] == "cross_dataset" for analysis in cross_dataset_analyses)
    assert any(analysis["id"] == "parameter_comparison" for analysis in cross_dataset_analyses)


def test_get_analysis_descriptor_returns_none_for_unknown_id() -> None:
    assert get_analysis_descriptor("missing-analysis-id") is None


def test_get_analysis_descriptor_returns_expected_entry() -> None:
    descriptor = get_analysis_descriptor("squid_fitting")
    assert descriptor is not None
    assert descriptor["label"] == "SQUID Fitting"


def test_squid_fitting_recommended_for_squid_profile() -> None:
    decision = evaluate_analysis_capability_gating(
        _analysis_by_id("squid_fitting"),
        dataset_profile={
            "device_type": "squid",
            "capabilities": [
                "y_parameter_characterization",
                "squid_characterization",
                "y11_response_fitting",
            ],
        },
    )

    assert decision.recommended is True
    assert decision.status == "recommended"
    assert decision.reasons == []


def test_squid_fitting_uses_profile_hint_when_squid_capability_missing() -> None:
    decision = evaluate_analysis_capability_gating(
        _analysis_by_id("squid_fitting"),
        dataset_profile={
            "device_type": "single_junction",
            "capabilities": ["y_parameter_characterization"],
        },
    )

    assert decision.recommended is False
    assert decision.status == "available"
    assert any(
        "Profile hint: missing capability SQUID Characterization" in reason
        for reason in decision.reasons
    )


def test_y11_fit_uses_profile_hint_when_excluded_capability_present() -> None:
    decision = evaluate_analysis_capability_gating(
        _analysis_by_id("y11_fit"),
        dataset_profile={
            "device_type": "traveling_wave",
            "capabilities": [
                "y_parameter_characterization",
                "y11_response_fitting",
                "traveling_wave_gain",
            ],
        },
    )

    assert decision.status == "available"
    assert any(
        "Profile hint: excluded by capability Traveling-wave Gain Characterization" in reason
        for reason in decision.reasons
    )
