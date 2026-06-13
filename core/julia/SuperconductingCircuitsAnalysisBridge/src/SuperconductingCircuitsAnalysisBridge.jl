module SuperconductingCircuitsAnalysisBridge

export BridgeStatus,
    analysis_bridge_status,
    extract_admittance_modes,
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

function _real_vector(values, name::AbstractString)
    converted = Float64.(collect(values))
    all(isfinite, converted) || error("$(name) must contain only finite values.")
    return converted
end

function _complex_parts(values, name::AbstractString)
    converted = collect(values)
    real_values = Float64.(real.(converted))
    imag_values = Float64.(imag.(converted))
    all(isfinite, real_values) || error("real($(name)) must contain only finite values.")
    all(isfinite, imag_values) || error("imag($(name)) must contain only finite values.")
    return real_values, imag_values
end

function _optional_float_pair(values, name::AbstractString)
    isnothing(values) && return nothing
    converted = Float64.(collect(values))
    length(converted) == 2 || error("$(name) must contain exactly two values.")
    all(isfinite, converted) || error("$(name) must contain only finite values.")
    converted[1] < converted[2] || error("$(name) lower bound must be less than upper bound.")
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

function fit_vector_s21(
    frequencies_hz,
    s21;
    n_resonators,
    bg_poles=2,
    min_q=2.0,
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

function extract_admittance_modes(table_or_path)
    mod = _py_module(
        "superconducting_circuits_analysis.application.analysis.extraction.admittance",
    )
    return _py_to_julia(mod.extract_modes_from_dataframe(_python_table(table_or_path)))
end

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
