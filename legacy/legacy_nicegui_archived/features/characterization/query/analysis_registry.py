"""Static analysis metadata registry for Characterization."""

from __future__ import annotations

from typing import Literal, NotRequired, TypedDict

from legacy.legacy_nicegui_archived.features.characterization.query.capability import (
    AnalysisCapabilityDecision,
    evaluate_analysis_capability_gating,
)
from legacy.legacy_nicegui_archived.services.analysis_scope_evaluator import (
    get_available_analyses,
    is_analysis_completed,
)


class AnalysisConfigField(TypedDict):
    """One typed analysis configuration field declaration."""

    name: str
    label: str
    type: Literal["select", "number"]
    default: str | float | int | None
    options: NotRequired[list[str]]


class AnalysisDescriptor(TypedDict):
    """Typed descriptor for one analysis entry in the registry."""

    id: str
    label: str
    icon: str
    requires: dict[str, object]
    auto_run: bool
    config_fields: list[AnalysisConfigField]
    scope: Literal["per_dataset", "cross_dataset"]
    description: str
    completed_methods: list[str]
    required_capabilities: list[str]
    excluded_capabilities: list[str]
    recommended_for: list[str]


ANALYSIS_REGISTRY: list[AnalysisDescriptor] = [
    {
        "id": "admittance_extraction",
        "label": "Admittance Extraction",
        "icon": "query_stats",
        "requires": {"data_type": "y_parameters", "representation": "imaginary"},
        "auto_run": True,
        "config_fields": [],
        "scope": "per_dataset",
        "description": "Finds resonance modes by identifying zero-crossings in Im(Y).",
        "completed_methods": ["admittance_zero_crossing"],
        "required_capabilities": ["y_parameter_characterization"],
        "excluded_capabilities": [],
        "recommended_for": ["single_junction", "squid", "resonator"],
    },
    {
        "id": "s21_resonance_fit",
        "label": "S21 Resonance Fit",
        "icon": "tune",
        "requires": {"data_type": "s_parameters", "parameter": ["S21", "S11"]},
        "auto_run": False,
        "config_fields": [
            {
                "name": "model",
                "label": "Model",
                "type": "select",
                "options": ["notch", "transmission"],
                "default": "notch",
            },
            {"name": "resonators", "label": "Resonators (N)", "type": "number", "default": 1},
            {"name": "f_min", "label": "f_min (GHz)", "type": "number", "default": None},
            {"name": "f_max", "label": "f_max (GHz)", "type": "number", "default": None},
        ],
        "scope": "per_dataset",
        "description": "Fits the S-parameter data to extract Qi, Qc, and fr.",
        "completed_methods": [
            "complex_notch_fit_S21",
            "transmission_fit_S21",
            "vector_fit_S21",
            "complex_notch_fit_S11",
            "transmission_fit_S11",
            "vector_fit_S11",
        ],
        "required_capabilities": ["s_parameter_characterization"],
        "excluded_capabilities": [],
        "recommended_for": ["traveling_wave", "resonator"],
    },
    {
        "id": "squid_fitting",
        "label": "SQUID Fitting",
        "icon": "science",
        "requires": {"data_type": "y_parameters", "representation": "imaginary"},
        "auto_run": False,
        "config_fields": [
            {
                "name": "fit_model",
                "label": "Model",
                "type": "select",
                "options": ["NO_LS", "WITH_LS", "FIXED_C"],
                "default": "WITH_LS",
            },
            {"name": "ls_min_nh", "label": "Ls min (nH)", "type": "number", "default": 0.0},
            {"name": "ls_max_nh", "label": "Ls max (nH)", "type": "number", "default": None},
            {"name": "c_min_pf", "label": "C min (pF)", "type": "number", "default": 0.0},
            {"name": "c_max_pf", "label": "C max (pF)", "type": "number", "default": None},
            {"name": "fixed_c_pf", "label": "Fixed C (pF)", "type": "number", "default": None},
            {
                "name": "fit_min_nh",
                "label": "Fit L_jun min (nH)",
                "type": "number",
                "default": None,
            },
            {
                "name": "fit_max_nh",
                "label": "Fit L_jun max (nH)",
                "type": "number",
                "default": None,
            },
        ],
        "scope": "per_dataset",
        "description": "Fits flux-dependent resonance frequencies to a SQUID-LC model.",
        "completed_methods": ["lc_squid_fit"],
        "required_capabilities": [
            "y_parameter_characterization",
            "squid_characterization",
        ],
        "excluded_capabilities": [],
        "recommended_for": ["squid"],
    },
    {
        "id": "y11_fit",
        "label": "Y11 Response Fit",
        "icon": "insights",
        "requires": {
            "data_type": "y_parameters",
            "parameter": ["Y11"],
            "representation": "imaginary",
        },
        "auto_run": False,
        "config_fields": [
            {
                "name": "ls1_init_nh",
                "label": "Ls1 init (nH)",
                "type": "number",
                "default": 0.01,
            },
            {
                "name": "ls2_init_nh",
                "label": "Ls2 init (nH)",
                "type": "number",
                "default": 0.01,
            },
            {"name": "c_init_pf", "label": "C init (pF)", "type": "number", "default": 0.885},
            {"name": "c_max_pf", "label": "C max (pF)", "type": "number", "default": 3.0},
        ],
        "scope": "per_dataset",
        "description": "Detailed fitting of the Y11 response over frequency and flux.",
        "completed_methods": ["y11_fit"],
        "required_capabilities": [
            "y_parameter_characterization",
            "y11_response_fitting",
        ],
        "excluded_capabilities": ["traveling_wave_gain"],
        "recommended_for": ["single_junction", "squid"],
    },
    {
        "id": "parameter_comparison",
        "label": "Parameter Comparison",
        "icon": "compare_arrows",
        "requires": {},  # cross_dataset bypasses standard record checks
        "auto_run": False,
        "config_fields": [
            {
                "name": "parameter",
                "label": "Parameter",
                "type": "select",
                "options": ["mode_1_ghz", "mode_ghz", "fr_ghz", "Qi", "Qc", "Ls_nH", "C_pF"],
                "default": "mode_1_ghz",
            }
        ],
        "scope": "cross_dataset",
        "description": "Compare derived parameters across multiple datasets.",
        "completed_methods": [],
        "required_capabilities": [],
        "excluded_capabilities": [],
        "recommended_for": [],
    },
]


def list_dataset_analyses() -> list[AnalysisDescriptor]:
    """Return only per-dataset analyses from the static registry."""
    return [analysis for analysis in ANALYSIS_REGISTRY if analysis["scope"] == "per_dataset"]


def list_cross_dataset_analyses() -> list[AnalysisDescriptor]:
    """Return only cross-dataset analyses from the static registry."""
    return [analysis for analysis in ANALYSIS_REGISTRY if analysis["scope"] == "cross_dataset"]


def get_analysis_descriptor(analysis_id: str) -> AnalysisDescriptor | None:
    """Lookup one analysis descriptor by id."""
    for analysis in ANALYSIS_REGISTRY:
        if analysis["id"] == analysis_id:
            return analysis
    return None


__all__ = [
    "ANALYSIS_REGISTRY",
    "AnalysisCapabilityDecision",
    "AnalysisConfigField",
    "AnalysisDescriptor",
    "evaluate_analysis_capability_gating",
    "get_analysis_descriptor",
    "get_available_analyses",
    "is_analysis_completed",
    "list_cross_dataset_analyses",
    "list_dataset_analyses",
]
