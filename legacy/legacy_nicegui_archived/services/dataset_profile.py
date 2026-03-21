"""Dataset profile normalization and capability templates."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any, TypedDict

DATASET_PROFILE_SCHEMA_VERSION = "1.0"

DEVICE_TYPE_UNSPECIFIED = "unspecified"

DATASET_DEVICE_TYPES: tuple[str, ...] = (
    DEVICE_TYPE_UNSPECIFIED,
    "single_junction",
    "squid",
    "traveling_wave",
    "resonator",
    "other",
)

CAPABILITY_Y_PARAMETER = "y_parameter_characterization"
CAPABILITY_S_PARAMETER = "s_parameter_characterization"
CAPABILITY_Y11_FIT = "y11_response_fitting"
CAPABILITY_SQUID_FIT = "squid_characterization"
CAPABILITY_TWPA_GAIN = "traveling_wave_gain"

CAPABILITY_LABELS: dict[str, str] = {
    CAPABILITY_Y_PARAMETER: "Y-parameter Characterization",
    CAPABILITY_S_PARAMETER: "S-parameter Characterization",
    CAPABILITY_Y11_FIT: "Y11 Response Fitting",
    CAPABILITY_SQUID_FIT: "SQUID Characterization",
    CAPABILITY_TWPA_GAIN: "Traveling-wave Gain Characterization",
}

DEVICE_TYPE_LABELS: dict[str, str] = {
    DEVICE_TYPE_UNSPECIFIED: "Unspecified",
    "single_junction": "Single Junction",
    "squid": "SQUID",
    "traveling_wave": "Traveling Wave",
    "resonator": "Resonator",
    "other": "Other",
}

DEVICE_TYPE_CAPABILITY_TEMPLATES: dict[str, tuple[str, ...]] = {
    DEVICE_TYPE_UNSPECIFIED: (),
    "single_junction": (
        CAPABILITY_Y_PARAMETER,
        CAPABILITY_Y11_FIT,
    ),
    "squid": (
        CAPABILITY_Y_PARAMETER,
        CAPABILITY_Y11_FIT,
        CAPABILITY_SQUID_FIT,
    ),
    "traveling_wave": (
        CAPABILITY_S_PARAMETER,
        CAPABILITY_TWPA_GAIN,
    ),
    "resonator": (
        CAPABILITY_S_PARAMETER,
        CAPABILITY_Y_PARAMETER,
    ),
    "other": (),
}

PROFILE_SOURCES: tuple[str, ...] = ("inferred", "template", "manual_override")


class DatasetProfile(TypedDict):
    """Canonical dataset profile payload (hint-only for analysis availability)."""

    schema_version: str
    device_type: str
    capabilities: list[str]
    source: str


def normalize_device_type(raw_value: object) -> str:
    """Normalize dataset profile device_type."""
    normalized = str(raw_value or "").strip().lower()
    if normalized in DATASET_DEVICE_TYPES:
        return normalized
    return DEVICE_TYPE_UNSPECIFIED


def normalize_capabilities(raw_values: object) -> list[str]:
    """Normalize, deduplicate, and sort capability keys."""
    if not isinstance(raw_values, Sequence) or isinstance(raw_values, str | bytes):
        return []

    normalized: set[str] = set()
    for raw in raw_values:
        capability = str(raw or "").strip().lower()
        if not capability:
            continue
        normalized.add(capability)
    return sorted(normalized)


def capability_label(capability_key: str) -> str:
    """Resolve a user-facing label for one capability key."""
    return CAPABILITY_LABELS.get(capability_key, capability_key.replace("_", " ").title())


def device_type_label(device_type_key: str) -> str:
    """Resolve a user-facing label for one device_type key."""
    canonical_device_type = normalize_device_type(device_type_key)
    return DEVICE_TYPE_LABELS.get(
        canonical_device_type,
        canonical_device_type.replace("_", " ").title(),
    )


def device_type_option_labels() -> dict[str, str]:
    """Build stable option labels for dataset profile device type selector."""
    return {device_type: device_type_label(device_type) for device_type in DATASET_DEVICE_TYPES}


def capability_option_labels() -> dict[str, str]:
    """Build stable option labels for dataset profile capability multi-select."""
    return {
        capability_key: capability_label(capability_key)
        for capability_key in sorted(CAPABILITY_LABELS)
    }


def template_capabilities_for_device_type(device_type: str) -> list[str]:
    """Return template capabilities for one canonical device_type."""
    canonical_device_type = normalize_device_type(device_type)
    template = DEVICE_TYPE_CAPABILITY_TEMPLATES.get(canonical_device_type, ())
    return sorted(template)


def suggested_capabilities_for_device_type(device_type: str) -> list[str]:
    """Return recommended capabilities for one device type."""
    return template_capabilities_for_device_type(device_type)


def infer_capabilities_from_record_index(
    record_index: Sequence[Mapping[str, object]] | None,
) -> list[str]:
    """Infer baseline capabilities from dataset record metadata only."""
    if not record_index:
        return []

    capabilities: set[str] = set()
    for record in record_index:
        data_type = str(record.get("data_type", "")).strip().lower()
        parameter = str(record.get("parameter", "")).strip().upper()

        if data_type in {"y_parameters", "y_params"}:
            capabilities.add(CAPABILITY_Y_PARAMETER)
            if parameter.startswith("Y11"):
                capabilities.add(CAPABILITY_Y11_FIT)
        elif data_type in {"s_parameters", "s_params"}:
            capabilities.add(CAPABILITY_S_PARAMETER)
    return sorted(capabilities)


def normalize_profile_source(raw_value: object, *, default: str) -> str:
    """Normalize dataset profile source marker."""
    normalized = str(raw_value or "").strip().lower()
    if normalized in PROFILE_SOURCES:
        return normalized
    return default


def normalize_dataset_profile(
    source_meta: Mapping[str, object] | None,
    *,
    record_index: Sequence[Mapping[str, object]] | None = None,
) -> DatasetProfile:
    """Return one canonical dataset profile with backward-compatible fallback."""
    profile_payload = {}
    if isinstance(source_meta, Mapping):
        profile_raw = source_meta.get("dataset_profile")
        if isinstance(profile_raw, Mapping):
            profile_payload = dict(profile_raw)

    device_type = normalize_device_type(profile_payload.get("device_type"))
    template_capabilities = template_capabilities_for_device_type(device_type)
    inferred_capabilities = infer_capabilities_from_record_index(record_index)
    explicit_capabilities = normalize_capabilities(profile_payload.get("capabilities", []))

    if explicit_capabilities:
        capabilities = explicit_capabilities
        default_source = "manual_override"
    else:
        capabilities = sorted(set(template_capabilities) | set(inferred_capabilities))
        default_source = "template" if template_capabilities else "inferred"

    source = normalize_profile_source(profile_payload.get("source"), default=default_source)
    schema_version = str(
        profile_payload.get("schema_version") or DATASET_PROFILE_SCHEMA_VERSION
    ).strip()
    if not schema_version:
        schema_version = DATASET_PROFILE_SCHEMA_VERSION

    return {
        "schema_version": schema_version,
        "device_type": device_type,
        "capabilities": capabilities,
        "source": source,
    }


def build_dataset_profile_payload(
    *,
    device_type: object,
    capabilities: object,
    source: object = "manual_override",
) -> DatasetProfile:
    """Build a canonical profile payload for persistence in source_meta."""
    return {
        "schema_version": DATASET_PROFILE_SCHEMA_VERSION,
        "device_type": normalize_device_type(device_type),
        "capabilities": normalize_capabilities(capabilities),
        "source": normalize_profile_source(source, default="manual_override"),
    }


def merge_dataset_profile_into_source_meta(
    source_meta: Mapping[str, object] | None,
    *,
    profile_payload: Mapping[str, object],
) -> dict[str, Any]:
    """Merge one canonical profile payload into dataset source_meta."""
    merged = dict(source_meta) if isinstance(source_meta, Mapping) else {}
    merged["dataset_profile"] = dict(profile_payload)
    return merged


def profile_summary_text(profile: Mapping[str, object]) -> str:
    """Build a compact summary text for one normalized profile."""
    device_type = normalize_device_type(profile.get("device_type"))
    capabilities = normalize_capabilities(profile.get("capabilities", []))
    if capabilities:
        capability_text = ", ".join(capability_label(item) for item in capabilities)
    else:
        capability_text = "None"
    source = normalize_profile_source(profile.get("source"), default="inferred")
    return f"Device Type: {device_type} | Capabilities: {capability_text} | Source: {source}"


def design_profile_summary_text(profile: Mapping[str, object]) -> str:
    """Build a product-facing summary using Design terminology over dataset_profile storage."""
    device_type = normalize_device_type(profile.get("device_type"))
    capabilities = normalize_capabilities(profile.get("capabilities", []))
    capability_text = (
        ", ".join(capability_label(item) for item in capabilities) if capabilities else "None"
    )
    source = normalize_profile_source(profile.get("source"), default="inferred")
    return (
        f"Design Type: {device_type_label(device_type)} | "
        f"Characterization Hints: {capability_text} | "
        f"Profile Source: {source}"
    )
