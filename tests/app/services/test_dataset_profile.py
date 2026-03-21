"""Tests for dataset profile normalization and capability helpers."""

from legacy.legacy_nicegui_archived.services.dataset_profile import (
    CAPABILITY_SQUID_FIT,
    CAPABILITY_Y11_FIT,
    CAPABILITY_Y_PARAMETER,
    DEVICE_TYPE_UNSPECIFIED,
    build_dataset_profile_payload,
    capability_option_labels,
    device_type_option_labels,
    merge_dataset_profile_into_source_meta,
    normalize_dataset_profile,
    normalize_device_type,
    profile_summary_text,
    suggested_capabilities_for_device_type,
    template_capabilities_for_device_type,
)


def test_normalize_device_type_falls_back_to_unspecified() -> None:
    assert normalize_device_type("SQUID") == "squid"
    assert normalize_device_type("unknown-device") == DEVICE_TYPE_UNSPECIFIED


def test_template_capabilities_for_squid_include_squid_fit() -> None:
    capabilities = template_capabilities_for_device_type("squid")
    assert CAPABILITY_Y_PARAMETER in capabilities
    assert CAPABILITY_Y11_FIT in capabilities
    assert CAPABILITY_SQUID_FIT in capabilities


def test_suggested_capabilities_for_device_type_uses_template() -> None:
    suggested = suggested_capabilities_for_device_type("single_junction")
    assert suggested == ["y11_response_fitting", "y_parameter_characterization"]


def test_option_maps_contain_expected_labels() -> None:
    device_options = device_type_option_labels()
    capability_options = capability_option_labels()

    assert device_options["squid"] == "SQUID"
    assert capability_options["squid_characterization"] == "SQUID Characterization"


def test_normalize_dataset_profile_prefers_explicit_capabilities() -> None:
    profile = normalize_dataset_profile(
        {
            "dataset_profile": {
                "schema_version": "1.0",
                "device_type": "squid",
                "capabilities": ["squid_characterization", "y_parameter_characterization"],
                "source": "manual_override",
            }
        }
    )

    assert profile["device_type"] == "squid"
    assert profile["capabilities"] == ["squid_characterization", "y_parameter_characterization"]
    assert profile["source"] == "manual_override"


def test_normalize_dataset_profile_infers_from_record_index_when_missing_profile() -> None:
    profile = normalize_dataset_profile(
        source_meta={},
        record_index=[
            {
                "id": 1,
                "data_type": "y_parameters",
                "parameter": "Y11",
                "representation": "imaginary",
            }
        ],
    )

    assert profile["device_type"] == DEVICE_TYPE_UNSPECIFIED
    assert profile["source"] == "inferred"
    assert CAPABILITY_Y_PARAMETER in profile["capabilities"]
    assert CAPABILITY_Y11_FIT in profile["capabilities"]


def test_build_dataset_profile_payload_normalizes_keys() -> None:
    payload = build_dataset_profile_payload(
        device_type="SQUID",
        capabilities=["y_parameter_characterization", "squid_characterization", ""],
    )

    assert payload["schema_version"] == "1.0"
    assert payload["device_type"] == "squid"
    assert payload["capabilities"] == ["squid_characterization", "y_parameter_characterization"]
    assert payload["source"] == "manual_override"


def test_merge_dataset_profile_into_source_meta_preserves_existing_keys() -> None:
    merged = merge_dataset_profile_into_source_meta(
        {
            "origin": "measurement",
            "solver": "none",
        },
        profile_payload={
            "schema_version": "1.0",
            "device_type": "resonator",
            "capabilities": ["s_parameter_characterization"],
            "source": "manual_override",
        },
    )

    assert merged["origin"] == "measurement"
    assert merged["solver"] == "none"
    assert merged["dataset_profile"]["device_type"] == "resonator"


def test_profile_summary_text_includes_capability_labels() -> None:
    summary = profile_summary_text(
        {
            "device_type": "squid",
            "capabilities": ["squid_characterization", "y11_response_fitting"],
            "source": "template",
        }
    )

    assert "Device Type: squid" in summary
    assert "SQUID Characterization" in summary
    assert "Y11 Response Fitting" in summary
    assert "Source: template" in summary
