# This bridge owns Julia-to-Python transport, not the fitting semantics. The
# canonical Knowledge nodes are:
# https://github.com/arfiligol/SCQ_Design/blob/main/docs/knowledge/network-modeling/network-trace-views.qmd
# https://github.com/arfiligol/SCQ_Design/blob/main/docs/knowledge/network-modeling/notch-resonator-complex-s21-fit.qmd
# https://github.com/arfiligol/SCQ_Design/blob/main/docs/knowledge/network-modeling/poles-zeros-residues.qmd
# https://github.com/arfiligol/SCQ_Design/blob/main/docs/knowledge/network-modeling/vector-fitting-passivity.qmd
# https://github.com/arfiligol/SCQ_Design/blob/main/docs/knowledge/readout/readout-filter-s21-j-fit.qmd
# https://github.com/arfiligol/SCQ_Design/blob/main/docs/knowledge/josephson-physics/josephson-current-phase-energy-and-inductance.qmd
# https://github.com/arfiligol/SCQ_Design/blob/main/docs/knowledge/josephson-physics/dc-squid-flux-tunability.qmd

module SuperconductingCircuitsAnalysisBridge

export BridgeStatus,
    analysis_bridge_status,
    calibrate_d3_channel_residue_s21,
    extract_admittance_modes,
    fit_d3_system_a_lj_sweep,
    fit_d3_through_line_s21,
    fit_notch_s21,
    fit_squid_modes,
    fit_transmission_s21,
    fit_vector_s21,
    fit_y11_response,
    python_executable

const _PACKAGE_SRC_DIR = @__DIR__
const _REPO_ROOT = normpath(joinpath(_PACKAGE_SRC_DIR, "..", "..", "..", ".."))

function _default_python_executable()
    if haskey(ENV, "SC_WORKBENCH_ROOT")
        root = normpath(expanduser(ENV["SC_WORKBENCH_ROOT"]))
    else
        root = _REPO_ROOT
    end
    if Sys.iswindows()
        return joinpath(root, ".venv", "Scripts", "python.exe")
    end
    return joinpath(root, ".venv", "bin", "python")
end

if !haskey(ENV, "JULIA_PYTHONCALL_EXE")
    default_python = _default_python_executable()
    if isfile(default_python)
        ENV["JULIA_PYTHONCALL_EXE"] = default_python
    end
end
if !haskey(ENV, "JULIA_CONDAPKG_BACKEND")
    ENV["JULIA_CONDAPKG_BACKEND"] = "Null"
end

using PythonCall

Base.@kwdef struct BridgeStatus
    ok::Bool
    python_executable::String
    package_path::Union{Nothing,String}
    message::String
end

function python_executable()
    sys = pyimport("sys")
    return pyconvert(String, sys.executable)
end

function _py_module(name::AbstractString)
    try
        return pyimport(name)
    catch err
        error(
            "Could not import Python module $(name). Run `uv sync --all-packages` " *
            "and set JULIA_PYTHONCALL_EXE to the repo .venv python if needed. " *
            sprint(showerror, err),
        )
    end
end

function analysis_bridge_status()
    try
        pkg = _py_module("superconducting_circuits_analysis")
        package_path = pyconvert(String, pygetattr(pkg, "__file__"))
        return BridgeStatus(
            ok=true,
            python_executable=python_executable(),
            package_path=package_path,
            message="ready",
        )
    catch err
        return BridgeStatus(
            ok=false,
            python_executable=get(ENV, "JULIA_PYTHONCALL_EXE", ""),
            package_path=nothing,
            message=sprint(showerror, err),
        )
    end
end

function _py_to_julia(value)
    PythonCall.pyis(value, PythonCall.pybuiltins.None) && return nothing
    return pyconvert(Any, value)
end

function _require_vector_fit_v2(result)
    result isa AbstractDict || error("Python vector fitting returned a non-dictionary payload.")
    get(result, "schema_version", nothing) == "scalar-s21-vector-fit.v2" || error(
        "Python vector fitting must return schema scalar-s21-vector-fit.v2.",
    )
    get(result, "model", nothing) == "scalar_s21_vector" || error(
        "Python vector fitting must return model scalar_s21_vector.",
    )
    get(result, "status", nothing) in ("success", "failed") || error(
        "Python vector fitting returned an invalid status.",
    )
    return result
end

function _dataframe_from_path(path::AbstractString)
    pandas = _py_module("pandas")
    return pandas.read_csv(path)
end

function _python_table(table_or_path)
    table_or_path isa AbstractString && return _dataframe_from_path(table_or_path)
    return table_or_path
end

function _nonboolean_values(values, name::AbstractString)
    converted = collect(values)
    any(value -> value isa Bool, converted) && error(
        "$(name) must contain numeric values, not Booleans.",
    )
    return converted
end

function _real_vector(values, name::AbstractString)
    converted = Float64.(_nonboolean_values(values, name))
    all(isfinite, converted) || error("$(name) must contain only finite values.")
    return converted
end

function _complex_parts(values, name::AbstractString)
    converted = _nonboolean_values(values, name)
    real_values = Float64.(real.(converted))
    imag_values = Float64.(imag.(converted))
    all(isfinite, real_values) || error("real($(name)) must contain only finite values.")
    all(isfinite, imag_values) || error("imag($(name)) must contain only finite values.")
    return real_values, imag_values
end

function _optional_float_pair(values, name::AbstractString)
    isnothing(values) && return nothing
    return _float_pair(values, name)
end

function _float_pair(values, name::AbstractString)
    converted = Float64.(_nonboolean_values(values, name))
    length(converted) == 2 || error("$(name) must contain exactly two values.")
    all(isfinite, converted) || error("$(name) must contain only finite values.")
    converted[1] < converted[2] || error("$(name) lower bound must be less than upper bound.")
    return converted
end

function _float_windows(values, name::AbstractString)
    converted = [
        _float_pair(window, "$(name)[$(index)]") for (index, window) in enumerate(values)
    ]
    isempty(converted) && error("$(name) must contain at least one window.")
    return converted
end

function _required_mapping_value(mapping, key::AbstractString, name::AbstractString)
    mapping isa AbstractDict || error("$(name) must be a dictionary.")
    haskey(mapping, key) || error("$(name) is missing required key $(repr(key)).")
    return mapping[key]
end

function _system_a_observations(observations::AbstractVector)
    converted = Vector{Dict{String,Any}}()
    fields = (
        "trace_id",
        "lj_per_junction_h",
        "lower_frequency_hz",
        "upper_frequency_hz",
        "lower_response_parameter",
        "lower_extraction_method",
        "lower_source_trace_id",
        "upper_response_parameter",
        "upper_extraction_method",
        "upper_source_trace_id",
        "candidate_id",
        "reference_contract_id",
        "topology_id",
        "port_plane",
    )
    for (index, observation) in enumerate(observations)
        name = "observations[$(index)]"
        push!(
            converted,
            Dict(
                field => _required_mapping_value(observation, field, name) for
                field in fields
            ),
        )
    end
    isempty(converted) && error("observations must not be empty.")
    return converted
end

function _phasor_convention(value)
    value isa AbstractString || error(
        "phasor_convention must be exp_plus_iomega_t or exp_minus_iomega_t.",
    )
    converted = String(value)
    converted in ("exp_plus_iomega_t", "exp_minus_iomega_t") || error(
        "phasor_convention must be exp_plus_iomega_t or exp_minus_iomega_t.",
    )
    return converted
end

function _s21_fitting_module()
    return _py_module("superconducting_circuits_analysis.application.analysis.fitting.s_parameters")
end

function fit_notch_s21(frequencies_hz, s21; initial_guess=nothing, fit_window_hz=nothing)
    mod = _s21_fitting_module()
    frequencies = _real_vector(frequencies_hz, "frequencies_hz")
    real_values, imag_values = _complex_parts(s21, "s21")
    result = mod.fit_complex_s21_notch(
        frequencies,
        real_values,
        imag_values;
        initial_guess=initial_guess,
        fit_window_hz=_optional_float_pair(fit_window_hz, "fit_window_hz"),
    )
    return _py_to_julia(result)
end

function fit_transmission_s21(frequencies_hz, s21; initial_guess=nothing, fit_window_hz=nothing)
    mod = _s21_fitting_module()
    frequencies = _real_vector(frequencies_hz, "frequencies_hz")
    real_values, imag_values = _complex_parts(s21, "s21")
    result = mod.fit_complex_s21_transmission(
        frequencies,
        real_values,
        imag_values;
        initial_guess=initial_guess,
        fit_window_hz=_optional_float_pair(fit_window_hz, "fit_window_hz"),
    )
    return _py_to_julia(result)
end

"""
Fit one scalar complex S21 trace through the Python vector-fitting API.

The Python side uses a one-response scikit-rf carrier only; this bridge does not
turn the trace into a physical network model or establish passivity or
reciprocity.
"""
function fit_vector_s21(
    frequencies_hz,
    s21;
    n_resonators,
    min_q,
    bg_poles,
    max_iterations,
    restrict_to_input_span=true,
    fit_window_hz=nothing,
)
    mod = _s21_fitting_module()
    frequencies = _real_vector(frequencies_hz, "frequencies_hz")
    real_values, imag_values = _complex_parts(s21, "s21")
    result = mod.fit_complex_s21_vector(
        frequencies,
        real_values,
        imag_values;
        n_resonators=n_resonators,
        bg_poles=bg_poles,
        max_iterations=max_iterations,
        min_q=min_q,
        restrict_to_input_span=restrict_to_input_span,
        fit_window_hz=_optional_float_pair(fit_window_hz, "fit_window_hz"),
    )
    return _require_vector_fit_v2(_py_to_julia(result))
end

function calibrate_d3_channel_residue_s21(
    frequencies_hz,
    filter_off_reference_s21,
    empty_feedline_s21;
    phasor_convention,
    fit_window_hz,
    background_windows_hz,
    fp_hz,
    filter_off_reference_linewidth_hz,
    linear_ls_rcond,
    min_reference_magnitude,
    min_complex_r2,
    min_abs_r2,
    max_phase_rmse_rad,
    min_phase_magnitude,
    provenance,
)
    mod = _py_module(
        "superconducting_circuits_analysis.application.analysis.fitting.d3_purcell",
    )
    frequencies = _real_vector(frequencies_hz, "frequencies_hz")
    filter_real, filter_imag = _complex_parts(
        filter_off_reference_s21,
        "filter_off_reference_s21",
    )
    reference_real, reference_imag = _complex_parts(
        empty_feedline_s21,
        "empty_feedline_s21",
    )
    result = mod.calibrate_d3_channel_residue_s21(
        frequencies,
        filter_real,
        filter_imag,
        reference_real,
        reference_imag;
        phasor_convention=_phasor_convention(phasor_convention),
        fit_window_hz=_float_pair(fit_window_hz, "fit_window_hz"),
        background_windows_hz=_float_windows(
            background_windows_hz,
            "background_windows_hz",
        ),
        fp_hz=fp_hz,
        filter_off_reference_linewidth_hz=filter_off_reference_linewidth_hz,
        linear_ls_rcond=linear_ls_rcond,
        min_reference_magnitude=min_reference_magnitude,
        min_complex_r2=min_complex_r2,
        min_abs_r2=min_abs_r2,
        max_phase_rmse_rad=max_phase_rmse_rad,
        min_phase_magnitude=min_phase_magnitude,
        provenance=provenance,
    )
    return _py_to_julia(result)
end

"""
Fit response-extracted lower/upper System-A frequencies over an L_J sweep.

Each observation carries independent lower- and upper-branch S/Y/Z extraction
provenance. The Python implementation owns contract validation and fitting;
this bridge only transports the current v1 request and decodes its result.
"""
function fit_d3_system_a_lj_sweep(
    observations::AbstractVector;
    physical_bounds::AbstractDict,
    physical_seeds::AbstractVector,
    numerical_tolerances::AbstractDict,
    gates::AbstractDict,
    provenance::AbstractDict,
)::Dict{String,Any}
    mod = _py_module(
        "superconducting_circuits_analysis.application.analysis.fitting.d3_purcell",
    )
    result = mod.fit_d3_system_a_lj_sweep(
        _system_a_observations(observations);
        physical_bounds=physical_bounds,
        physical_seeds=physical_seeds,
        numerical_tolerances=numerical_tolerances,
        gates=gates,
        provenance=provenance,
    )
    decoded = _py_to_julia(result)
    decoded isa AbstractDict || error("Python System-A fit returned a non-dictionary payload.")
    get(decoded, "schema", nothing) == "d3_system_a_frequency_lj_sweep_fit.v1" || error(
        "Python System-A fit must return schema d3_system_a_frequency_lj_sweep_fit.v1.",
    )
    get(decoded, "status", nothing) in ("success", "rejected") || error(
        "Python System-A fit returned an invalid status.",
    )
    return Dict{String,Any}(String(key) => value for (key, value) in decoded)
end

function fit_d3_through_line_s21(
    frequencies_hz,
    measured_s21,
    empty_feedline_s21;
    phasor_convention,
    fit_window_hz,
    background_windows_hz,
    fp_hz,
    fr_hz,
    filter_off_reference_linewidth_hz,
    readout_off_reference_linewidth_hz,
    channel_calibration,
    j_bounds_hz,
    j_seeds_hz,
    linear_ls_rcond,
    min_reference_magnitude,
    min_complex_r2,
    min_abs_r2,
    max_phase_rmse_rad,
    min_phase_magnitude,
    min_normalized_bound_margin,
    least_squares_max_nfev,
    least_squares_ftol,
    least_squares_xtol,
    least_squares_gtol,
    least_squares_diff_step,
    min_successful_seed_count,
    min_successful_seed_fraction,
    near_optimal_mse_ratio,
    near_optimal_mse_absolute_tolerance,
    min_winning_seed_count,
    max_seed_spread_hz,
    provenance,
)
    mod = _py_module(
        "superconducting_circuits_analysis.application.analysis.fitting.d3_purcell",
    )
    frequencies = _real_vector(frequencies_hz, "frequencies_hz")
    measured_real, measured_imag = _complex_parts(measured_s21, "measured_s21")
    reference_real, reference_imag = _complex_parts(
        empty_feedline_s21,
        "empty_feedline_s21",
    )
    result = mod.fit_d3_through_line_s21(
        frequencies,
        measured_real,
        measured_imag,
        reference_real,
        reference_imag;
        phasor_convention=_phasor_convention(phasor_convention),
        fit_window_hz=_float_pair(fit_window_hz, "fit_window_hz"),
        background_windows_hz=_float_windows(
            background_windows_hz,
            "background_windows_hz",
        ),
        fp_hz=fp_hz,
        fr_hz=fr_hz,
        filter_off_reference_linewidth_hz=filter_off_reference_linewidth_hz,
        readout_off_reference_linewidth_hz=readout_off_reference_linewidth_hz,
        channel_calibration=channel_calibration,
        j_bounds_hz=_float_pair(j_bounds_hz, "j_bounds_hz"),
        j_seeds_hz=_real_vector(j_seeds_hz, "j_seeds_hz"),
        linear_ls_rcond=linear_ls_rcond,
        min_reference_magnitude=min_reference_magnitude,
        min_complex_r2=min_complex_r2,
        min_abs_r2=min_abs_r2,
        max_phase_rmse_rad=max_phase_rmse_rad,
        min_phase_magnitude=min_phase_magnitude,
        min_normalized_bound_margin=min_normalized_bound_margin,
        least_squares_max_nfev=least_squares_max_nfev,
        least_squares_ftol=least_squares_ftol,
        least_squares_xtol=least_squares_xtol,
        least_squares_gtol=least_squares_gtol,
        least_squares_diff_step=least_squares_diff_step,
        min_successful_seed_count=min_successful_seed_count,
        min_successful_seed_fraction=min_successful_seed_fraction,
        near_optimal_mse_ratio=near_optimal_mse_ratio,
        near_optimal_mse_absolute_tolerance=near_optimal_mse_absolute_tolerance,
        min_winning_seed_count=min_winning_seed_count,
        max_seed_spread_hz=max_seed_spread_hz,
        provenance=provenance,
    )
    return _py_to_julia(result)
end

function extract_admittance_modes(table_or_path)
    mod = _py_module(
        "superconducting_circuits_analysis.application.analysis.extraction.admittance",
    )
    return _py_to_julia(mod.extract_modes_from_dataframe(_python_table(table_or_path)))
end

# These bridge calls preserve the Python model boundary: L_jun is each
# junction's small-signal inductance and the ideal symmetric pair uses
# L_sq = L_jun / 2. They do not add flux, asymmetry, loop-inductance, or quantum
# semantics.
function fit_y11_response(
    table_or_path;
    ls1_init_nh,
    ls2_init_nh,
    c_init_pf,
    c_max_pf,
)
    mod = _py_module("superconducting_circuits_analysis.application.analysis.fitting.y11")
    result = mod.fit_y11_response(
        _python_table(table_or_path);
        ls1_init_nh=ls1_init_nh,
        ls2_init_nh=ls2_init_nh,
        c_init_pf=c_init_pf,
        c_max_pf=c_max_pf,
    )
    return _py_to_julia(result)
end

function fit_squid_modes(
    modes;
    model::Symbol=:with_ls,
    fixed_c_pf=nothing,
    bounds=nothing,
    fit_window=nothing,
)
    mod = _py_module("superconducting_circuits_analysis.application.analysis.fitting.modes")
    py_bounds = isnothing(bounds) ? Dict{String,Any}() : bounds
    py_fit_window = isnothing(fit_window) ? nothing : fit_window
    result = if model == :no_ls
        mod.fit_squid_model(modes, py_bounds, py_fit_window)
    elseif model == :with_ls
        mod.fit_squid_model_with_Ls(modes, py_bounds, py_fit_window)
    elseif model == :fixed_c
        isnothing(fixed_c_pf) && error(
            "fit_squid_modes(...; model=:fixed_c) requires fixed_c_pf.",
        )
        mod.fit_squid_model_with_Ls_fixed_C(modes, fixed_c_pf, py_bounds, py_fit_window)
    else
        error("model must be :no_ls, :with_ls, or :fixed_c.")
    end
    return _py_to_julia(result)
end

end
