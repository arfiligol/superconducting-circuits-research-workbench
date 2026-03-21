"""Runtime evaluator for dataset-profile capability hints."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from legacy.legacy_nicegui_archived.services.dataset_profile import (
    DatasetProfile,
    capability_label,
    normalize_capabilities,
    normalize_device_type,
)


def _analysis_sequence_field(analysis: Mapping[str, object], key: str) -> list[object]:
    raw_value = analysis.get(key, [])
    return list(raw_value) if isinstance(raw_value, list | tuple | set) else []


@dataclass(frozen=True)
class AnalysisCapabilityDecision:
    """Hint-only capability decision for one analysis on one dataset profile."""

    recommended: bool
    status: str
    reasons: list[str]


def evaluate_analysis_capability_gating(
    analysis: Mapping[str, object],
    *,
    dataset_profile: DatasetProfile,
) -> AnalysisCapabilityDecision:
    """Evaluate capability hints for one analysis.

    This evaluator never hard-blocks execution. Trace compatibility remains the
    sole runtime authority for run availability; profile capabilities only
    contribute recommendation/hint text.
    """
    capabilities = set(normalize_capabilities(dataset_profile.get("capabilities", [])))
    device_type = normalize_device_type(dataset_profile.get("device_type"))

    required = set(
        normalize_capabilities(_analysis_sequence_field(analysis, "required_capabilities"))
    )
    excluded = set(
        normalize_capabilities(_analysis_sequence_field(analysis, "excluded_capabilities"))
    )
    recommended_for = {
        normalize_device_type(raw_device_type)
        for raw_device_type in _analysis_sequence_field(analysis, "recommended_for")
    }

    missing = sorted(required - capabilities)
    blocked = sorted(excluded & capabilities)
    reasons: list[str] = []
    reasons.extend(
        f"Profile hint: missing capability {capability_label(capability)}" for capability in missing
    )
    reasons.extend(
        f"Profile hint: excluded by capability {capability_label(capability)}"
        for capability in blocked
    )

    recommended = not reasons and device_type in recommended_for
    status = "recommended" if recommended else "available"
    return AnalysisCapabilityDecision(
        recommended=recommended,
        status=status,
        reasons=reasons,
    )
