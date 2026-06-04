"""Domain value-object tests for trace metadata normalization."""

from superconducting_circuits_analysis.domain import ModeGroup, ParameterKey, TraceKind


def test_trace_kind_normalizes_known_aliases_to_canonical_values() -> None:
    assert TraceKind.from_token("s_params") is TraceKind.S_PARAMETERS
    assert TraceKind.from_token("s_matrix") is TraceKind.S_PARAMETERS
    assert TraceKind.from_token("Y_PARAMETERS") is TraceKind.Y_PARAMETERS
    assert TraceKind.from_token("y_matrix") is TraceKind.Y_PARAMETERS
    assert TraceKind.from_token("z_params") is TraceKind.Z_PARAMETERS
    assert TraceKind.from_token("impedance_matrix") is TraceKind.Z_PARAMETERS
    assert TraceKind.from_token("other") is TraceKind.UNKNOWN


def test_trace_kind_exposes_accepted_tokens_for_repository_filters() -> None:
    assert TraceKind.S_PARAMETERS.accepted_tokens == (
        "s_parameters",
        "s_params",
        "s_matrix",
        "scattering",
        "scattering_matrix",
    )
    assert TraceKind.Y_PARAMETERS.accepted_tokens == (
        "y_parameters",
        "y_params",
        "y_matrix",
        "admittance",
        "admittance_matrix",
    )
    assert TraceKind.Z_PARAMETERS.accepted_tokens == (
        "z_parameters",
        "z_params",
        "z_matrix",
        "impedance",
        "impedance_matrix",
    )


def test_mode_group_normalize_supports_aliases_and_defaults() -> None:
    assert ModeGroup.normalize("signal", allow_all=False) is ModeGroup.BASE
    assert ModeGroup.normalize("sideband", allow_all=False) is ModeGroup.SIDEBAND
    assert ModeGroup.normalize("all", allow_all=True) is ModeGroup.ALL
    assert ModeGroup.normalize("unknown", allow_all=False) is ModeGroup.UNKNOWN


def test_parameter_key_extracts_canonical_name_and_sideband_metadata() -> None:
    base = ParameterKey.from_raw("Y11")
    sideband = ParameterKey.from_raw("Y11 [om=(-1,), im=(-1,)]")
    zero_mode = ParameterKey.from_raw("Y11 [om=(0,), im=(0,)]")

    assert base.canonical == "Y11"
    assert base.has_sideband_suffix is False
    assert base.mode_group is ModeGroup.BASE

    assert sideband.canonical == "Y11"
    assert sideband.has_sideband_suffix is True
    assert sideband.mode_group is ModeGroup.SIDEBAND

    assert zero_mode.canonical == "Y11"
    assert zero_mode.has_sideband_suffix is True
    assert zero_mode.mode_group is ModeGroup.BASE
