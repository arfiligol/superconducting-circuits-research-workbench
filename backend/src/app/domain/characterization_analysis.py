from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from src.app.domain.datasets import (
    CharacterizationAnalysisRegistryRow,
    CharacterizationAnalysisTraceCompatibility,
    CharacterizationAvailabilityState,
    TraceAnalysisCapability,
    TraceAxis,
    TraceCapabilityReason,
    TraceMetadataSummary,
)

CharacterizationConfigFieldType = Literal[
    "number_range",
    "positive_number",
    "non_empty_text",
]


@dataclass(frozen=True)
class CharacterizationAnalysisConfigFieldSpec:
    field_key: str
    label: str
    schema_type: CharacterizationConfigFieldType
    required: bool = True


@dataclass(frozen=True)
class CharacterizationAnalysisInputRoleSpec:
    input_role: str
    capability_key: str
    input_role_label: str
    minimum_count: int
    required: bool
    accepted_families: tuple[str, ...]
    accepted_trace_mode_groups: tuple[str, ...]
    accepted_source_kinds: tuple[str, ...] = ()
    accepted_representations: tuple[str, ...] = ()
    required_axis_name: str | None = None


@dataclass(frozen=True)
class CharacterizationAnalysisSpec:
    analysis_id: str
    label: str
    dataset_families: tuple[str, ...]
    config_fields: tuple[CharacterizationAnalysisConfigFieldSpec, ...]
    recommended_trace_modes: tuple[str, ...]
    ready_state: CharacterizationAvailabilityState
    local_runtime_supported: bool
    input_roles: tuple[CharacterizationAnalysisInputRoleSpec, ...]
    unavailable_summary: str

    @property
    def required_config_fields(self) -> tuple[str, ...]:
        return tuple(field.field_key for field in self.config_fields if field.required)


@dataclass(frozen=True)
class CharacterizationAnalysisScopeEvaluation:
    spec: CharacterizationAnalysisSpec
    availability_state: CharacterizationAvailabilityState
    matched_trace_count: int
    selected_trace_count: int
    summary: str
    selected_scope_ready: bool
    missing_selected_trace_ids: tuple[str, ...]
    incompatible_selected_trace_ids: tuple[str, ...]


_CONFIG_RANGE = CharacterizationAnalysisConfigFieldSpec
_INPUT_ROLE = CharacterizationAnalysisInputRoleSpec

_ANALYSIS_SPECS: tuple[CharacterizationAnalysisSpec, ...] = (
    CharacterizationAnalysisSpec(
        analysis_id="admittance_extraction",
        label="Admittance Resonance Extraction",
        dataset_families=("fluxonium",),
        config_fields=(
            _CONFIG_RANGE(
                field_key="fit_window",
                label="Fit window",
                schema_type="number_range",
            ),
            _CONFIG_RANGE(
                field_key="residual_tolerance",
                label="Residual tolerance",
                schema_type="positive_number",
            ),
        ),
        recommended_trace_modes=("base",),
        ready_state="recommended",
        local_runtime_supported=True,
        input_roles=(
            _INPUT_ROLE(
                input_role="admittance_resonance_source",
                capability_key="admittance_resonance_source",
                input_role_label="Admittance resonance source",
                minimum_count=1,
                required=True,
                accepted_families=("y_matrix",),
                accepted_trace_mode_groups=("base",),
                accepted_source_kinds=(
                    "measurement",
                    "layout_simulation",
                    "circuit_simulation",
                ),
                accepted_representations=("real", "imaginary", "complex"),
                required_axis_name="frequency",
            ),
        ),
        unavailable_summary=(
            "No base-mode admittance trace currently satisfies the resonance extraction "
            "input requirements."
        ),
    ),
    CharacterizationAnalysisSpec(
        analysis_id="sideband_comparison",
        label="Sideband Comparison",
        dataset_families=("fluxonium",),
        config_fields=(
            _CONFIG_RANGE(
                field_key="comparison_window",
                label="Comparison window",
                schema_type="number_range",
            ),
        ),
        recommended_trace_modes=("sideband",),
        ready_state="available",
        local_runtime_supported=False,
        input_roles=(
            _INPUT_ROLE(
                input_role="sideband_trace",
                capability_key="sideband_trace",
                input_role_label="Sideband trace",
                minimum_count=2,
                required=True,
                accepted_families=("y_matrix",),
                accepted_trace_mode_groups=("sideband",),
                accepted_source_kinds=(
                    "measurement",
                    "layout_simulation",
                    "circuit_simulation",
                ),
                accepted_representations=("phase", "real", "imaginary", "complex"),
                required_axis_name="frequency",
            ),
        ),
        unavailable_summary=(
            "No sideband trace currently satisfies the comparison input requirements."
        ),
    ),
    CharacterizationAnalysisSpec(
        analysis_id="junction_parameter_identification",
        label="Junction Parameter Identification",
        dataset_families=("fluxonium",),
        config_fields=(
            _CONFIG_RANGE(
                field_key="fit_window",
                label="Fit window",
                schema_type="number_range",
            ),
            _CONFIG_RANGE(
                field_key="prior_family",
                label="Prior family",
                schema_type="non_empty_text",
            ),
        ),
        recommended_trace_modes=("base", "sideband"),
        ready_state="recommended",
        local_runtime_supported=False,
        input_roles=(
            _INPUT_ROLE(
                input_role="junction_identification_trace",
                capability_key="junction_identification_trace",
                input_role_label="Junction identification trace",
                minimum_count=1,
                required=True,
                accepted_families=("y_matrix",),
                accepted_trace_mode_groups=("base", "sideband"),
                accepted_source_kinds=(
                    "measurement",
                    "layout_simulation",
                    "circuit_simulation",
                ),
                accepted_representations=("complex",),
                required_axis_name="frequency",
            ),
        ),
        unavailable_summary=(
            "No compatible trace currently satisfies the junction identification prerequisites."
        ),
    ),
    CharacterizationAnalysisSpec(
        analysis_id="screening_summary",
        label="Screening Summary",
        dataset_families=("fluxonium",),
        config_fields=(
            _CONFIG_RANGE(
                field_key="screening_mode",
                label="Screening mode",
                schema_type="non_empty_text",
            ),
        ),
        recommended_trace_modes=("base",),
        ready_state="available",
        local_runtime_supported=False,
        input_roles=(
            _INPUT_ROLE(
                input_role="screening_trace",
                capability_key="screening_trace",
                input_role_label="Screening trace",
                minimum_count=1,
                required=True,
                accepted_families=("s_matrix",),
                accepted_trace_mode_groups=("base",),
                accepted_source_kinds=(
                    "measurement",
                    "layout_simulation",
                    "circuit_simulation",
                ),
                accepted_representations=("real", "imaginary", "complex", "magnitude"),
                required_axis_name="frequency",
            ),
        ),
        unavailable_summary=(
            "No base screening trace is currently available in this design scope."
        ),
    ),
    CharacterizationAnalysisSpec(
        analysis_id="quality_factor_fit",
        label="Quality Factor Fit",
        dataset_families=("resonator",),
        config_fields=(
            _CONFIG_RANGE(
                field_key="temperature_window",
                label="Temperature window",
                schema_type="number_range",
            ),
        ),
        recommended_trace_modes=("base",),
        ready_state="recommended",
        local_runtime_supported=False,
        input_roles=(
            _INPUT_ROLE(
                input_role="quality_factor_trace",
                capability_key="quality_factor_trace",
                input_role_label="Quality factor trace",
                minimum_count=1,
                required=True,
                accepted_families=("s_matrix",),
                accepted_trace_mode_groups=("base",),
                accepted_source_kinds=("measurement",),
                accepted_representations=("real", "imaginary", "complex", "magnitude"),
                required_axis_name="temperature",
            ),
        ),
        unavailable_summary=(
            "No temperature-sweep trace currently satisfies the quality-factor fit inputs."
        ),
    ),
    CharacterizationAnalysisSpec(
        analysis_id="coupler_shift_fit",
        label="Coupler Shift Fit",
        dataset_families=("transmon",),
        config_fields=(
            _CONFIG_RANGE(
                field_key="fit_window",
                label="Fit window",
                schema_type="number_range",
            ),
            _CONFIG_RANGE(
                field_key="cross_check_mode",
                label="Cross-check mode",
                schema_type="non_empty_text",
            ),
        ),
        recommended_trace_modes=("base",),
        ready_state="recommended",
        local_runtime_supported=False,
        input_roles=(
            _INPUT_ROLE(
                input_role="measurement_shift_trace",
                capability_key="measurement_shift_trace",
                input_role_label="Measurement shift trace",
                minimum_count=1,
                required=True,
                accepted_families=("z_matrix",),
                accepted_trace_mode_groups=("base",),
                accepted_source_kinds=("measurement",),
                accepted_representations=("real", "imaginary", "complex"),
                required_axis_name="bias",
            ),
            _INPUT_ROLE(
                input_role="simulation_shift_trace",
                capability_key="simulation_shift_trace",
                input_role_label="Simulation shift trace",
                minimum_count=1,
                required=True,
                accepted_families=("z_matrix",),
                accepted_trace_mode_groups=("base",),
                accepted_source_kinds=("layout_simulation", "circuit_simulation"),
                accepted_representations=("real", "imaginary", "complex"),
                required_axis_name="bias",
            ),
        ),
        unavailable_summary=(
            "Measurement and simulation shift traces are both required for this fit."
        ),
    ),
)


def list_characterization_analysis_specs() -> tuple[CharacterizationAnalysisSpec, ...]:
    return _ANALYSIS_SPECS


def get_characterization_analysis_spec(
    analysis_id: str,
) -> CharacterizationAnalysisSpec | None:
    normalized = analysis_id.casefold()
    return next(
        (spec for spec in _ANALYSIS_SPECS if spec.analysis_id.casefold() == normalized),
        None,
    )


def evaluate_trace_analysis_capabilities(
    *,
    dataset_family: str,
    trace: TraceMetadataSummary,
    axes: tuple[TraceAxis, ...],
) -> tuple[TraceAnalysisCapability, ...]:
    normalized_family = dataset_family.casefold()
    return tuple(
        capability
        for spec in _ANALYSIS_SPECS
        if normalized_family in spec.dataset_families
        for capability in _evaluate_trace_against_spec(spec=spec, trace=trace, axes=axes)
    )


def derive_characterization_analysis_ids(
    traces: tuple[TraceMetadataSummary, ...],
) -> tuple[str, ...]:
    present = {
        capability.analysis_id
        for trace in traces
        for capability in trace.analysis_capabilities
    }
    return tuple(spec.analysis_id for spec in _ANALYSIS_SPECS if spec.analysis_id in present)


def build_characterization_registry_rows(
    *,
    included_analysis_ids: tuple[str, ...],
    traces: tuple[TraceMetadataSummary, ...],
    selected_trace_ids: tuple[str, ...],
) -> tuple[CharacterizationAnalysisRegistryRow, ...]:
    rows: list[CharacterizationAnalysisRegistryRow] = []
    for analysis_id in included_analysis_ids:
        spec = get_characterization_analysis_spec(analysis_id)
        if spec is None:
            continue
        evaluation = evaluate_characterization_analysis_scope(
            spec=spec,
            traces=traces,
            selected_trace_ids=selected_trace_ids,
        )
        rows.append(
            CharacterizationAnalysisRegistryRow(
                analysis_id=spec.analysis_id,
                label=spec.label,
                availability_state=evaluation.availability_state,
                required_config_fields=spec.required_config_fields,
                trace_compatibility=CharacterizationAnalysisTraceCompatibility(
                    matched_trace_count=evaluation.matched_trace_count,
                    selected_trace_count=evaluation.selected_trace_count,
                    recommended_trace_modes=spec.recommended_trace_modes,
                    summary=evaluation.summary,
                ),
            )
        )
    return tuple(rows)


def evaluate_characterization_analysis_scope(
    *,
    spec: CharacterizationAnalysisSpec,
    traces: tuple[TraceMetadataSummary, ...],
    selected_trace_ids: tuple[str, ...],
) -> CharacterizationAnalysisScopeEvaluation:
    traces_by_id = {trace.trace_id: trace for trace in traces}
    selected_scope = tuple(
        traces_by_id[trace_id]
        for trace_id in selected_trace_ids
        if trace_id in traces_by_id
    )
    scope_traces = selected_scope if len(selected_trace_ids) > 0 else traces
    missing_selected_trace_ids = tuple(
        trace_id for trace_id in selected_trace_ids if trace_id not in traces_by_id
    )

    matched_trace_ids: set[str] = set()
    role_counts: dict[str, int] = {role.input_role: 0 for role in spec.input_roles}
    incompatible_selected_trace_ids: list[str] = []

    for trace in scope_traces:
        eligible_roles = {
            capability.input_role
            for capability in trace.analysis_capabilities
            if capability.analysis_id == spec.analysis_id and capability.status == "eligible"
        }
        if len(eligible_roles) == 0:
            if len(selected_trace_ids) > 0:
                incompatible_selected_trace_ids.append(trace.trace_id)
            continue
        matched_trace_ids.add(trace.trace_id)
        for input_role in eligible_roles:
            if input_role in role_counts:
                role_counts[input_role] += 1

    deficits = [
        (role, role.minimum_count - role_counts[role.input_role])
        for role in spec.input_roles
        if role.required and role_counts[role.input_role] < role.minimum_count
    ]
    selected_incompatible = tuple(incompatible_selected_trace_ids)
    selected_trace_count = len(selected_trace_ids)
    matched_trace_count = len(matched_trace_ids)

    if len(missing_selected_trace_ids) > 0:
        summary = _selected_scope_summary(
            spec,
            missing_count=len(missing_selected_trace_ids),
            incompatible_count=len(selected_incompatible),
            traces=scope_traces,
        )
        return CharacterizationAnalysisScopeEvaluation(
            spec=spec,
            availability_state="unavailable",
            matched_trace_count=matched_trace_count,
            selected_trace_count=selected_trace_count,
            summary=summary,
            selected_scope_ready=False,
            missing_selected_trace_ids=missing_selected_trace_ids,
            incompatible_selected_trace_ids=selected_incompatible,
        )

    if len(selected_incompatible) > 0:
        summary = _selected_scope_summary(
            spec,
            missing_count=0,
            incompatible_count=len(selected_incompatible),
            traces=scope_traces,
        )
        return CharacterizationAnalysisScopeEvaluation(
            spec=spec,
            availability_state="unavailable",
            matched_trace_count=matched_trace_count,
            selected_trace_count=selected_trace_count,
            summary=summary,
            selected_scope_ready=False,
            missing_selected_trace_ids=(),
            incompatible_selected_trace_ids=selected_incompatible,
        )

    if len(deficits) == 0 and (len(scope_traces) > 0 or len(selected_trace_ids) == 0):
        return CharacterizationAnalysisScopeEvaluation(
            spec=spec,
            availability_state=spec.ready_state,
            matched_trace_count=matched_trace_count,
            selected_trace_count=selected_trace_count,
            summary=_ready_scope_summary(
                spec,
                matched_trace_count=matched_trace_count,
                selected_trace_count=selected_trace_count,
            ),
            selected_scope_ready=True,
            missing_selected_trace_ids=(),
            incompatible_selected_trace_ids=(),
        )

    availability_state: CharacterizationAvailabilityState = (
        "available" if matched_trace_count > 0 else "unavailable"
    )
    summary = _deficit_summary(
        spec,
        matched_trace_count=matched_trace_count,
        deficits=tuple(deficits),
        selected_trace_count=selected_trace_count,
    )
    return CharacterizationAnalysisScopeEvaluation(
        spec=spec,
        availability_state=availability_state,
        matched_trace_count=matched_trace_count,
        selected_trace_count=selected_trace_count,
        summary=summary,
        selected_scope_ready=False,
        missing_selected_trace_ids=(),
        incompatible_selected_trace_ids=(),
    )


def validate_characterization_analysis_config(
    spec: CharacterizationAnalysisSpec,
    analysis_config: dict[str, object],
) -> str | None:
    for field in spec.config_fields:
        value = analysis_config.get(field.field_key)
        if value is None:
            if field.required:
                return f"characterization_setup.analysis_config.{field.field_key} is required."
            continue
        if field.schema_type == "number_range":
            if (
                not isinstance(value, list)
                or len(value) != 2
                or not all(isinstance(item, int | float) for item in value)
            ):
                return (
                    f"characterization_setup.analysis_config.{field.field_key} must be "
                    "an array of two numbers."
                )
            if float(value[0]) >= float(value[1]):
                return (
                    f"characterization_setup.analysis_config.{field.field_key} must be "
                    "strictly increasing."
                )
            continue
        if field.schema_type == "positive_number":
            if not isinstance(value, int | float) or float(value) <= 0:
                return (
                    f"characterization_setup.analysis_config.{field.field_key} must be "
                    "a positive number."
                )
            continue
        if field.schema_type == "non_empty_text" and (
            not isinstance(value, str) or len(value.strip()) == 0
        ):
            return (
                f"characterization_setup.analysis_config.{field.field_key} must be "
                "a non-empty string."
            )
    return None


def _evaluate_trace_against_spec(
    *,
    spec: CharacterizationAnalysisSpec,
    trace: TraceMetadataSummary,
    axes: tuple[TraceAxis, ...],
) -> tuple[TraceAnalysisCapability, ...]:
    return tuple(
        _evaluate_trace_against_role(spec=spec, role=role, trace=trace, axes=axes)
        for role in spec.input_roles
    )


def _evaluate_trace_against_role(
    *,
    spec: CharacterizationAnalysisSpec,
    role: CharacterizationAnalysisInputRoleSpec,
    trace: TraceMetadataSummary,
    axes: tuple[TraceAxis, ...],
) -> TraceAnalysisCapability:
    reasons: list[TraceCapabilityReason] = []

    if trace.family not in role.accepted_families:
        reasons.append(
            _capability_reason(
                code="family_mismatch",
                message=f"Requires {_format_token_list(role.accepted_families)} traces.",
                evidence={
                    "actual_family": trace.family,
                    "accepted_families": list(role.accepted_families),
                },
            )
        )
    if trace.trace_mode_group not in role.accepted_trace_mode_groups:
        reasons.append(
            _capability_reason(
                code="trace_mode_group_mismatch",
                message=(
                    f"Requires {_format_token_list(role.accepted_trace_mode_groups)} "
                    "trace mode coverage."
                ),
                evidence={
                    "actual_trace_mode_group": trace.trace_mode_group,
                    "accepted_trace_mode_groups": list(role.accepted_trace_mode_groups),
                },
            )
        )
    if len(role.accepted_source_kinds) > 0 and trace.source_kind not in role.accepted_source_kinds:
        reasons.append(
            _capability_reason(
                code="source_kind_mismatch",
                message=(
                    f"Requires {_format_token_list(role.accepted_source_kinds)} "
                    "trace sources."
                ),
                evidence={
                    "actual_source_kind": trace.source_kind,
                    "accepted_source_kinds": list(role.accepted_source_kinds),
                },
            )
        )
    if (
        len(role.accepted_representations) > 0
        and trace.representation not in role.accepted_representations
    ):
        reasons.append(
            _capability_reason(
                code="representation_mismatch",
                message=(
                    f"Requires {_format_token_list(role.accepted_representations)} "
                    "representation."
                ),
                evidence={
                    "actual_representation": trace.representation,
                    "accepted_representations": list(role.accepted_representations),
                },
            )
        )
    if role.required_axis_name is not None and not any(
        axis.name.casefold() == role.required_axis_name.casefold() for axis in axes
    ):
        reasons.append(
            _capability_reason(
                code="required_axis_missing",
                message=f"Requires a {role.required_axis_name} axis.",
                evidence={
                    "actual_axes": [axis.name for axis in axes],
                    "required_axis_name": role.required_axis_name,
                },
            )
        )

    eligible = len(reasons) == 0
    return TraceAnalysisCapability(
        capability_id=f"{spec.analysis_id}:{role.capability_key}",
        analysis_id=spec.analysis_id,
        analysis_label=spec.label,
        input_role=role.input_role,
        input_role_label=role.input_role_label,
        status="eligible" if eligible else "ineligible",
        summary=(
            f"Eligible as {role.input_role_label.lower()}."
            if eligible
            else reasons[0].message
        ),
        reasons=tuple(reasons),
    )


def _ready_scope_summary(
    spec: CharacterizationAnalysisSpec,
    *,
    matched_trace_count: int,
    selected_trace_count: int,
) -> str:
    count = selected_trace_count if selected_trace_count > 0 else matched_trace_count
    scope = "selected" if selected_trace_count > 0 else "design"
    noun = "trace" if count == 1 else "traces"
    verb = "is" if count == 1 else "are"
    return f"{count} {scope} {noun} {verb} eligible for {spec.label.lower()}."


def _deficit_summary(
    spec: CharacterizationAnalysisSpec,
    *,
    matched_trace_count: int,
    deficits: tuple[tuple[CharacterizationAnalysisInputRoleSpec, int], ...],
    selected_trace_count: int,
) -> str:
    if matched_trace_count == 0:
        return spec.unavailable_summary
    deficit_parts = [
        (
            f"{missing} more {role.input_role_label.lower()} "
            f"{'input is' if missing == 1 else 'inputs are'} required"
        )
        for role, missing in deficits
    ]
    scope = "selected" if selected_trace_count > 0 else "eligible"
    noun = "trace" if matched_trace_count == 1 else "traces"
    return (
        f"{matched_trace_count} {scope} {noun} match so far, but "
        f"{'; '.join(deficit_parts)}."
    )


def _selected_scope_summary(
    spec: CharacterizationAnalysisSpec,
    *,
    missing_count: int,
    incompatible_count: int,
    traces: tuple[TraceMetadataSummary, ...],
) -> str:
    issues: list[str] = []
    if missing_count > 0:
        issues.append(
            f"{missing_count} selected {'trace is' if missing_count == 1 else 'traces are'} "
            "not available in the current design scope"
        )
    if incompatible_count > 0:
        reason = _first_incompatible_reason(spec.analysis_id, traces)
        trace_phrase = "trace is" if incompatible_count == 1 else "traces are"
        issues.append(
            f"{incompatible_count} selected {trace_phrase} not eligible for "
            f"{spec.label.lower()}"
            + (f" because {reason}" if reason is not None else ".")
        )
    if len(issues) == 0:
        return spec.unavailable_summary
    return ". ".join(issues).rstrip(".") + "."


def _first_incompatible_reason(
    analysis_id: str,
    traces: tuple[TraceMetadataSummary, ...],
) -> str | None:
    for trace in traces:
        for capability in trace.analysis_capabilities:
            if capability.analysis_id != analysis_id or capability.status == "eligible":
                continue
            if len(capability.reasons) == 0:
                continue
            return capability.reasons[0].message.rstrip(".")
    return None


def _format_token_list(values: tuple[str, ...]) -> str:
    if len(values) == 1:
        return values[0].replace("_", " ")
    return ", ".join(value.replace("_", " ") for value in values[:-1]) + (
        f", or {values[-1].replace('_', ' ')}"
    )


def _capability_reason(
    *,
    code: str,
    message: str,
    evidence: dict[str, object],
) -> TraceCapabilityReason:
    return TraceCapabilityReason(code=code, message=message, evidence=evidence)
