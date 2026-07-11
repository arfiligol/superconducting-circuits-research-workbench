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
    restrict_to_input_span=true,
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
        min_q=min_q,
        restrict_to_input_span=restrict_to_input_span,
    )
    return _py_to_julia(result)
end

function calibrate_d3_channel_residue_s21(
    frequencies_hz,
    filter_only_s21,
    empty_feedline_s21;
    phasor_convention,
    fit_window_hz,
    background_windows_hz,
    fp_hz,
    filter_loaded_linewidth_hz,
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
    filter_real, filter_imag = _complex_parts(filter_only_s21, "filter_only_s21")
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
        filter_loaded_linewidth_hz=filter_loaded_linewidth_hz,
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

function fit_d3_through_line_s21(
    frequencies_hz,
    measured_s21,
    empty_feedline_s21;
    phasor_convention,
    fit_window_hz,
    background_windows_hz,
    fp_hz,
    fr_hz,
    filter_loaded_linewidth_hz,
    readout_loaded_linewidth_hz,
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
        filter_loaded_linewidth_hz=filter_loaded_linewidth_hz,
        readout_loaded_linewidth_hz=readout_loaded_linewidth_hz,
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
