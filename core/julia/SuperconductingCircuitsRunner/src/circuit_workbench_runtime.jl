# This is the one-shot Julia execution side of the public Python Circuit
# Workbench runtime.  It deliberately consumes sealed JSON rather than Python
# callbacks so an entire action remains inside one Julia process.

const _CW_PLAN_SCHEMA = "circuit-workbench-plan.v1"
const _CW_REQUEST_SCHEMA = "circuit-workbench-run-request.v1"
const _CW_RECEIPT_SCHEMA = "circuit-workbench-run-receipt.v1"

struct _CWCandidateNotEvaluable <: Exception
    message::String
end
Base.showerror(io::IO, error::_CWCandidateNotEvaluable) = print(io, error.message)

struct _CWTargetedSchurNumericalError <: Exception
    message::String
end
Base.showerror(io::IO, error::_CWTargetedSchurNumericalError) = print(io, error.message)

function _cw_dict(value, label)::Dict{String,Any}
    value isa AbstractDict || error("$(label) must be an object.")
    return Dict{String,Any}(string(key) => item for (key, item) in pairs(value))
end

function _cw_array(value, label)::Vector{Any}
    value isa AbstractVector || error("$(label) must be an array.")
    return Any[value...]
end

function _cw_string(value, label)::String
    value isa AbstractString || error("$(label) must be a string.")
    isempty(value) && error("$(label) must be nonempty.")
    return String(value)
end

function _cw_number(value, label)::Float64
    value isa Real && !(value isa Bool) || error("$(label) must be numeric (not Bool).")
    result = Float64(value)
    isfinite(result) || error("$(label) must be finite.")
    return result
end

function _cw_integer(value, label)::Int
    number = _cw_number(value, label)
    isinteger(number) || error("$(label) must be an exact integer.")
    return Int(number)
end

function _cw_tree_sha256(root::AbstractString)::String
    isdir(root) || error("Required source tree is absent: $(root)")
    paths = String[]
    for (directory, _, files) in walkdir(root)
        for file in files
            path = joinpath(directory, file)
            relative = replace(relpath(path, root), '\\' => '/')
            (startswith(relative, ".git/") || startswith(relative, "test/") || occursin("/__pycache__/", "/" * relative) || endswith(relative, ".pyc")) && continue
            push!(paths, relative)
        end
    end
    sort!(paths)
    context = SHA2_256_CTX()
    for relative in paths
        update!(context, codeunits(relative)); update!(context, UInt8[0])
        update!(context, read(joinpath(root, relative))); update!(context, UInt8[0])
    end
    return bytes2hex(digest!(context))
end

function _cw_julia_executable()::String
    return realpath(joinpath(Sys.BINDIR, Base.julia_exename()))
end

function _cw_validate_runtime_identity(request)
    runtime = _cw_dict(get(request, "runtime", nothing), "request.runtime")
    runner_root = dirname(@__DIR__)
    core_root = dirname(dirname(pathof(SuperconductingCircuitsCore)))
    expected = Dict(
        "runner_tree_sha256" => _cw_tree_sha256(runner_root),
        "core_tree_sha256" => _cw_tree_sha256(core_root),
        "julia_executable_path" => _cw_julia_executable(),
        "julia_executable_sha256" => _cw_sha256(_cw_julia_executable()),
    )
    for (key, value) in expected
        get(runtime, key, nothing) == value || error("Runtime identity $(key) mismatches the executing source/runtime.")
    end
    return runtime
end

function _cw_sha256(path::AbstractString)::String
    return bytes2hex(sha256(read(path)))
end

function _cw_atomic_json(path::AbstractString, value)
    mkpath(dirname(path))
    temporary = string(path, ".tmp.", getpid())
    try
        open(temporary, "w") do io
            write(io, _cw_json(value))
        end
        mv(temporary, path; force=true)
    finally
        isfile(temporary) && rm(temporary; force=true)
    end
    return path
end

function _cw_json(value)
    if value isa AbstractDict
        keys_sorted = sort!(String.(collect(keys(value))))
        return "{" * join((JSON3.write(key) * ":" * _cw_json(value[key]) for key in keys_sorted), ",") * "}"
    elseif value isa AbstractVector || value isa Tuple
        return "[" * join((_cw_json(item) for item in value), ",") * "]"
    end
    return JSON3.write(value)
end

function _cw_hashable(value)
    if value isa AbstractFloat
        if isinteger(value) && abs(value) <= 9_007_199_254_740_991
            return Int(value)
        end
        return Dict("__float64__" => string(reinterpret(UInt64, Float64(value)); base=16, pad=16))
    elseif value isa AbstractDict
        return Dict(string(key) => _cw_hashable(item) for (key, item) in pairs(value))
    elseif value isa AbstractVector || value isa Tuple
        return [_cw_hashable(item) for item in value]
    end
    return value
end

_cw_fingerprint(value) = bytes2hex(sha256(codeunits(_cw_json(_cw_hashable(value)))) )

function _cw_endpoint(value, label)
    data = _cw_dict(value, label)
    return SuperconductingCircuitsCore.external_node(
        "cw_" * _cw_string(get(data, "component_id", nothing), "$(label).component_id") * "_" *
        _cw_string(get(data, "pin_name", nothing), "$(label).pin_name"),
    )
end

function _cw_parallel_lc!(plan, component, overrides)
    id = _cw_string(get(component, "id", nothing), "component.id")
    params = _cw_dict(get(component, "parameters", nothing), "component.parameters")
    capacitance = _cw_number(get(overrides, "$(id).capacitance_f", get(params, "capacitance_f", nothing)), "$(id).capacitance_f")
    inductance = _cw_number(get(overrides, "$(id).inductance_h", get(params, "inductance_h", nothing)), "$(id).inductance_h")
    conductance = _cw_number(get(overrides, "$(id).conductance_s", get(params, "conductance_s", 0.0)), "$(id).conductance_s")
    capacitance > 0 && inductance > 0 && conductance >= 0 || throw(
        _CWCandidateNotEvaluable("$(id) C/L values must be positive and G must be nonnegative."),
    )
    signal = SuperconductingCircuitsCore.external_node("cw_$(id)_signal")
    SuperconductingCircuitsCore.add_parallel_lc_resonator!(
        plan;
        id=id,
        node=signal,
        capacitance=capacitance,
        inductance=inductance,
    )
    conductance > 0 && SuperconductingCircuitsCore.series_resistor!(
        plan;
        id="$(id)_conductance",
        from=signal,
        to=SuperconductingCircuitsCore.ground(),
        resistance=1 / conductance,
        role=:shunt_conductance,
    )
end

function _cw_parameter(params, overrides, id, name)
    return _cw_number(get(overrides, "$(id).$(name)", get(params, name, nothing)), "$(id).$(name)")
end

function _cw_positive_integer(params, overrides, id, name)
    value = _cw_integer(get(overrides, "$(id).$(name)", get(params, name, nothing)), "$(id).$(name)")
    value > 0 || throw(_CWCandidateNotEvaluable("$(id).$(name) must be positive."))
    return value
end

_cw_node(id, name) = SuperconductingCircuitsCore.external_node("cw_$(id)_$(name)")

function _cw_transmission_line!(plan, component, overrides)
    id = _cw_string(get(component, "id", nothing), "component.id")
    params = _cw_dict(get(component, "parameters", nothing), "component.parameters")
    length_m = _cw_parameter(params, overrides, id, "length_m")
    n_sections = _cw_positive_integer(params, overrides, id, "n_sections")
    l_per_m_h = _cw_parameter(params, overrides, id, "l_per_m_h")
    c_per_m_f = _cw_parameter(params, overrides, id, "c_per_m_f")
    r_per_m_ohm = _cw_parameter(params, overrides, id, "r_per_m_ohm")
    g_per_m_s = _cw_parameter(params, overrides, id, "g_per_m_s")
    length_m > 0 && l_per_m_h > 0 && c_per_m_f > 0 && r_per_m_ohm >= 0 && g_per_m_s >= 0 ||
        throw(_CWCandidateNotEvaluable("$(id) RLGC values are outside the physical domain."))
    spec = SuperconductingCircuitsCore.RLGCSpec(
        length_m=length_m,
        n_sections=n_sections,
        l_per_m_h=l_per_m_h,
        c_per_m_f=c_per_m_f,
        r_per_m_ohm=r_per_m_ohm,
        g_per_m_s=g_per_m_s,
    )
    SuperconductingCircuitsCore.build_lc_ladder_line!(
        plan;
        id=id,
        head=_cw_node(id, "head"),
        tail=_cw_node(id, "tail"),
        spec=spec,
        head_termination=:external,
        tail_termination=:external,
    )
    return nothing
end

function _cw_linearized_floating_qubit!(plan, component, overrides)
    id = _cw_string(get(component, "id", nothing), "component.id")
    params = _cw_dict(get(component, "parameters", nothing), "component.parameters")
    branch_count = _cw_positive_integer(params, overrides, id, "josephson_branch_count")
    topology = branch_count == 2 ? :symmetric_squid : branch_count == 1 ? :single_junction :
        throw(_CWCandidateNotEvaluable("$(id).josephson_branch_count must be 1 or 2."))
    SuperconductingCircuitsCore.add_linearized_floating_qubit!(
        plan;
        id=id,
        readout_attachment=_cw_node(id, "readout_attachment"),
        island_1=_cw_node(id, "island_1"),
        island_2=_cw_node(id, "island_2"),
        c01_f=_cw_parameter(params, overrides, id, "c01_f"),
        c02_f=_cw_parameter(params, overrides, id, "c02_f"),
        c12_f=_cw_parameter(params, overrides, id, "c12_f"),
        cr1_f=_cw_parameter(params, overrides, id, "cr1_f"),
        cr2_f=_cw_parameter(params, overrides, id, "cr2_f"),
        l_j_per_junction_h=_cw_parameter(params, overrides, id, "l_j_per_junction_h"),
        junction_topology=topology,
    )
    return nothing
end

function _cw_segment_breakpoints(lengths, counts, label)
    length(lengths) == length(counts) || error("$(label) segment lengths/counts mismatch.")
    points = Float64[0.0]
    for (length_m, count) in zip(lengths, counts)
        length_m > 0 || throw(_CWCandidateNotEvaluable("$(label) segment lengths must be positive."))
        count > 0 || throw(_CWCandidateNotEvaluable("$(label) segment counts must be positive."))
        dx = length_m / count
        for _ in 1:count
            push!(points, points[end] + dx)
        end
    end
    return points
end

function _cw_intrinsic_interferometric_purcell_filter!(plan, component, overrides)
    id = _cw_string(get(component, "id", nothing), "component.id")
    params = _cw_dict(get(component, "parameters", nothing), "component.parameters")
    value(name) = _cw_parameter(params, overrides, id, name)
    count(name) = _cw_positive_integer(params, overrides, id, name)
    shared_short = value("shared_short_length_m")
    coupled = value("coupled_length_m")
    readout_open = value("readout_open_length_m")
    filter_open = value("filter_open_length_m")
    all(>(0), (shared_short, coupled, readout_open, filter_open)) ||
        throw(_CWCandidateNotEvaluable("$(id) resonator segment lengths must be positive."))
    readout_counts = (count("readout_short_sections"), count("coupled_sections"), count("readout_open_sections"))
    filter_counts = (count("filter_short_sections"), count("coupled_sections"), count("filter_open_sections"))
    readout_lengths = (shared_short, coupled, readout_open)
    filter_lengths = (shared_short, coupled, filter_open)
    readout_breakpoints = _cw_segment_breakpoints(readout_lengths, readout_counts, "$(id) readout")
    filter_breakpoints = _cw_segment_breakpoints(filter_lengths, filter_counts, "$(id) filter")
    readout_spec = SuperconductingCircuitsCore.RLGCSpec(
        length_m=readout_breakpoints[end],
        section_length_m=maximum(diff(readout_breakpoints)),
        n_sections=sum(readout_counts),
        l_per_m_h=value("readout_l_per_m_h"),
        c_per_m_f=value("readout_c_per_m_f"),
    )
    filter_spec = SuperconductingCircuitsCore.RLGCSpec(
        length_m=filter_breakpoints[end],
        section_length_m=maximum(diff(filter_breakpoints)),
        n_sections=sum(filter_counts),
        l_per_m_h=value("filter_l_per_m_h"),
        c_per_m_f=value("filter_c_per_m_f"),
    )
    l_matrix = [value("mtl_l11_per_m_h") value("mtl_l12_per_m_h"); value("mtl_l21_per_m_h") value("mtl_l22_per_m_h")]
    c_matrix = [value("mtl_c11_per_m_f") value("mtl_c12_per_m_f"); value("mtl_c21_per_m_f") value("mtl_c22_per_m_f")]
    mtl = SuperconductingCircuitsCore.MTLCoupledRLGCSpec(
        start1_m=shared_short,
        start2_m=shared_short,
        length_m=coupled,
        section_length_m=coupled / readout_counts[2],
        l_matrix_per_m_h=l_matrix,
        c_matrix_per_m_f=c_matrix,
    )
    finger_length = value("idc_finger_length_um")
    source_min = value("idc_source_min_um")
    source_max = value("idc_source_max_um")
    source_min <= source_max || throw(_CWCandidateNotEvaluable("$(id) IDC source support is inverted."))
    source_min <= finger_length <= source_max ||
        throw(_CWCandidateNotEvaluable("$(id).idc_finger_length_um lies outside its closed source support."))
    c1g = value("idc_filter_ground_slope_f_per_um") * finger_length + value("idc_filter_ground_intercept_f")
    c2g = value("idc_feedline_ground_slope_f_per_um") * finger_length + value("idc_feedline_ground_intercept_f")
    c12 = value("idc_mutual_slope_f_per_um") * finger_length + value("idc_mutual_intercept_f")
    all(>(0), (c1g, c2g, c12)) ||
        throw(_CWCandidateNotEvaluable("$(id) IDC OLS branches must evaluate positive."))
    c0r = value("c0r_f")
    c0r >= 0 || throw(_CWCandidateNotEvaluable("$(id).c0r_f must be nonnegative."))
    SuperconductingCircuitsCore.add_intrinsic_interferometric_purcell_filter!(
        plan;
        id=id,
        readout_attachment=_cw_node(id, "readout_attachment"),
        feedline_attachment=_cw_node(id, "feedline_attachment"),
        readout_spec=readout_spec,
        filter_spec=filter_spec,
        mtl_model=mtl,
        c1g_f=c1g,
        c2g_f=c2g,
        c12_f=c12,
        c0r_f=c0r,
        readout_breakpoints_m=readout_breakpoints,
        filter_breakpoints_m=filter_breakpoints,
    )
    return nothing
end

function _cw_build_plan(payload; overrides=Dict{String,Float64}())
    plan_payload = _cw_dict(payload, "request.plan")
    get(plan_payload, "schema", nothing) == _CW_PLAN_SCHEMA || error("Plan schema is not $(_CW_PLAN_SCHEMA).")
    plan = SuperconductingCircuitsCore.CircuitPlan(; id=_cw_string(get(plan_payload, "id", nothing), "plan.id"))
    components = _cw_array(get(plan_payload, "components", nothing), "plan.components")
    isempty(components) && error("Plan must contain at least one component.")
    component_ids = Set{String}()
    for raw in components
        component = _cw_dict(raw, "plan component")
        id = _cw_string(get(component, "id", nothing), "component.id")
        id in component_ids && error("Duplicate component id $(id).")
        push!(component_ids, id)
        type_id = _cw_string(get(component, "type_id", nothing), "component.type_id")
        type_id in (
            "workbench.parallel_lc_resonator.v1",
            "workbench.transmission_line.v1",
            "workbench.intrinsic_interferometric_purcell_filter.v1",
            "workbench.linearized_floating_qubit.v1",
        ) || error(
            "Unsupported Circuit Workbench Julia lowerer for component type $(type_id). " *
            "Register a reviewed Core lowerer before using it in a sealed run.",
        )
        type_id == "workbench.parallel_lc_resonator.v1" && _cw_parallel_lc!(plan, component, overrides)
        type_id == "workbench.transmission_line.v1" && _cw_transmission_line!(plan, component, overrides)
        type_id == "workbench.intrinsic_interferometric_purcell_filter.v1" && _cw_intrinsic_interferometric_purcell_filter!(plan, component, overrides)
        type_id == "workbench.linearized_floating_qubit.v1" && _cw_linearized_floating_qubit!(plan, component, overrides)
    end
    for (index, raw) in enumerate(_cw_array(get(plan_payload, "connections", Any[]), "plan.connections"))
        connection = _cw_dict(raw, "plan.connections[$index]")
        SuperconductingCircuitsCore.connect!(
            plan,
            _cw_endpoint(get(connection, "left", nothing), "connection.left"),
            _cw_endpoint(get(connection, "right", nothing), "connection.right"),
        )
    end
    for (index, raw) in enumerate(_cw_array(get(plan_payload, "ports", Any[]), "plan.ports"))
        port = _cw_dict(raw, "plan.ports[$index]")
        resistance = _cw_number(get(port, "resistance_ohm", nothing), "port.resistance_ohm")
        resistance > 0 || error("port.resistance_ohm must be positive.")
        SuperconductingCircuitsCore.external_port!(
            plan;
            id=_cw_string(get(port, "id", nothing), "port.id"),
            index=index,
            endpoint=_cw_endpoint(get(port, "endpoint", nothing), "port.endpoint"),
            resistance=resistance,
        )
    end
    report = SuperconductingCircuitsCore.validate_authoring(plan)
    SuperconductingCircuitsCore.has_errors(report) && error(
        "CircuitPlan authoring validation failed: " *
        join((string(issue.code, ": ", issue.message) for issue in SuperconductingCircuitsCore.errors(report)), "; "),
    )
    return SuperconductingCircuitsCore.compile_to_josephson(plan)
end

function _cw_variable_baseline(plan, variables)
    components = Dict(
        _cw_string(get(_cw_dict(raw, "plan component"), "id", nothing), "component.id") =>
        _cw_dict(raw, "plan component") for raw in _cw_array(get(plan, "components", nothing), "plan.components")
    )
    result = Float64[]
    for raw in variables
        variable = _cw_dict(raw, "variable")
        ref = _cw_dict(get(variable, "ref", nothing), "variable.ref")
        component_id = _cw_string(get(ref, "component_id", nothing), "variable.ref.component_id")
        parameter_name = _cw_string(get(ref, "parameter_name", nothing), "variable.ref.parameter_name")
        component = get(components, component_id, nothing)
        isnothing(component) && error("Variable references missing component $(component_id).")
        params = _cw_dict(get(component, "parameters", nothing), "component.parameters")
        value = _cw_number(get(params, parameter_name, nothing), "variable baseline")
        transform = string(get(variable, "transform", "identity"))
        transform == "identity" && push!(result, value)
        transform == "log" && value > 0 && push!(result, log(value))
        if transform == "unit_interval"
            lower = _cw_number(get(variable, "lower", nothing), "variable.lower")
            upper = _cw_number(get(variable, "upper", nothing), "variable.upper")
            isfinite(lower) && isfinite(upper) && lower < upper ||
                error("unit_interval variables require finite lower < upper.")
            lower <= value <= upper || error("unit_interval variable baseline must lie within [lower, upper].")
            push!(result, (value - lower) / (upper - lower))
        end
        transform in ("identity", "log", "unit_interval") || error("Unsupported variable transform $(transform).")
    end
    return result
end

function _cw_variable_bounds(variables)
    lower = Float64[]
    upper = Float64[]
    any_bound = false
    for raw in variables
        variable = _cw_dict(raw, "variable")
        transform = string(get(variable, "transform", "identity"))
        lo = get(variable, "lower", nothing)
        hi = get(variable, "upper", nothing)
        lo_value = isnothing(lo) ? -Inf : _cw_number(lo, "variable.lower")
        hi_value = isnothing(hi) ? Inf : _cw_number(hi, "variable.upper")
        any_bound |= !isnothing(lo) || !isnothing(hi)
        lo_value < hi_value || error("Variable lower must be less than upper.")
        if transform == "log"
            !isfinite(lo_value) || lo_value > 0 || error("Log variable lower must be positive.")
            push!(lower, isfinite(lo_value) ? log(lo_value) : -Inf)
            push!(upper, isfinite(hi_value) ? log(hi_value) : Inf)
        elseif transform == "identity"
            push!(lower, lo_value); push!(upper, hi_value)
        elseif transform == "unit_interval"
            isfinite(lo_value) && isfinite(hi_value) && lo_value < hi_value ||
                error("unit_interval variables require finite lower < upper.")
            push!(lower, 0.0); push!(upper, 1.0)
        else
            error("Unsupported variable transform $(transform).")
        end
    end
    any_bound || return nothing, nothing
    return lower, upper
end

function _cw_candidate_overrides(variables, latent)
    length(variables) == length(latent) || error("CMA candidate dimension mismatches variables.")
    result = Dict{String,Float64}()
    for index in eachindex(variables)
        variable = _cw_dict(variables[index], "variable")
        ref = _cw_dict(get(variable, "ref", nothing), "variable.ref")
        key = _cw_string(get(ref, "component_id", nothing), "variable.ref.component_id") * "." *
            _cw_string(get(ref, "parameter_name", nothing), "variable.ref.parameter_name")
        transform = string(get(variable, "transform", "identity"))
        value = if transform == "identity"
            Float64(latent[index])
        elseif transform == "log"
            exp(Float64(latent[index]))
        elseif transform == "unit_interval"
            lower = _cw_number(get(variable, "lower", nothing), "variable.lower")
            upper = _cw_number(get(variable, "upper", nothing), "variable.upper")
            isfinite(lower) && isfinite(upper) && lower < upper ||
                error("unit_interval variables require finite lower < upper.")
            lower + (upper - lower) * Float64(latent[index])
        else
            error("Unsupported variable transform $(transform).")
        end
        isfinite(value) || error("CMA candidate produced a non-finite physical parameter.")
        result[key] = value
    end
    return result
end

function _cw_requested_candidate_parameters(variables, latent)
    length(variables) == length(latent) || error("CMA candidate dimension mismatches variables.")
    result = Dict{String,Float64}()
    for index in eachindex(variables)
        variable = _cw_dict(variables[index], "variable")
        ref = _cw_dict(get(variable, "requested_ref", get(variable, "ref", nothing)), "variable.requested_ref")
        key = _cw_string(get(ref, "component_id", nothing), "variable.requested_ref.component_id") * "." *
            _cw_string(get(ref, "parameter_name", nothing), "variable.requested_ref.parameter_name")
        transform = string(get(variable, "transform", "identity"))
        value = if transform == "identity"
            Float64(latent[index])
        elseif transform == "log"
            exp(Float64(latent[index]))
        elseif transform == "unit_interval"
            lower = _cw_number(get(variable, "lower", nothing), "variable.lower")
            upper = _cw_number(get(variable, "upper", nothing), "variable.upper")
            isfinite(lower) && isfinite(upper) && lower < upper ||
                error("unit_interval variables require finite lower < upper.")
            lower + (upper - lower) * Float64(latent[index])
        else
            error("Unsupported variable transform $(transform).")
        end
        isfinite(value) || error("CMA candidate produced a non-finite physical parameter.")
        result[key] = value
    end
    return result
end

function _cw_s_parameter(compiled, spec)
    frequency_hz = _cw_number(get(spec, "frequency_hz", nothing), "cared output frequency_hz")
    frequency_hz > 0 || error("cared output frequency_hz must be positive.")
    output_port = _cw_integer(get(spec, "output_port", nothing), "cared output output_port")
    input_port = _cw_integer(get(spec, "input_port", nothing), "cared output input_port")
    output_port > 0 && input_port > 0 || error("S-parameter ports must be positive.")
    result = SuperconductingCircuitsCore.run_frequency_sweep(
        compiled.netlist,
        compiled.component_values,
        [frequency_hz];
        pump_frequencies_hz=[frequency_hz],
        sources=[(mode=(1,), port=input_port, current=0.0)],
        port_indices=[output_port, input_port],
        returnS=true,
        returnZ=false,
        returnQE=false,
        returnCM=false,
    )
    trace = get(result.traces[:zero_mode_s], "S$(output_port)$(input_port)", nothing)
    trace isa AbstractVector && length(trace) == 1 || error("Requested S$(output_port)$(input_port) trace is absent.")
    value = ComplexF64(only(trace))
    part = string(get(spec, "part", "abs"))
    part == "abs" && return abs(value)
    part == "real" && return real(value)
    part == "imag" && return imag(value)
    error("Unsupported S-parameter cared-output part $(part).")
end

function _cw_cared_outputs(compiled, objective)
    outputs = _cw_dict(get(objective, "cared_outputs", nothing), "objective.cared_outputs")
    result = Dict{String,Float64}()
    for name in sort!(collect(keys(outputs)))
        spec = _cw_dict(outputs[name], "cared output $(name)")
        kind = _cw_string(get(spec, "kind", nothing), "cared output $(name).kind")
        kind == "s_parameter" || error("Unsupported cared-output kind $(kind).")
        result[name] = _cw_s_parameter(compiled, spec)
    end
    return result
end

function _cw_coordinate_index(model, raw, label)
    ref = _cw_dict(raw, label)
    component_id = _cw_string(get(ref, "component_id", nothing), "$(label).component_id")
    coordinate = _cw_string(get(ref, "coordinate_name", nothing), "$(label).coordinate_name")
    # Runtime lowerers expose authored pins as `cw_<component>_<coordinate>`.
    # Composite Core builders may own an internal coordinate directly under the
    # component id (the intrinsic filter's filter_open_tail is one example).
    candidates = (
        "ext_cw_$(component_id)_$(coordinate)",
        "ext_$(component_id)_$(coordinate)",
    )
    indices = unique(Int[index for name in candidates for index in findall(==(name), model.node_names)])
    length(indices) == 1 || error(
        "Reduction coordinate $(component_id).$(coordinate) must resolve to exactly one compiled C/K coordinate.",
    )
    return only(indices)
end

function _cw_reduction_model(model, reduction)
    reduction isa AbstractDict || error("Direct Schur cared outputs require an explicit ReductionSpec.")
    data = _cw_dict(reduction, "request.reduction")
    get(data, "eliminated", nothing) == "complete_complement" || error("ReductionSpec must declare complete_complement.")
    dimension = length(model.node_names)
    basis = Matrix{Float64}(I, dimension, dimension)
    for raw_transform in _cw_array(get(data, "transforms", Any[]), "reduction.transforms")
        transform = _cw_dict(raw_transform, "reduction.transform")
        coordinates = _cw_array(get(transform, "coordinates", nothing), "reduction.transform.coordinates")
        matrix_rows = _cw_array(get(transform, "matrix", nothing), "reduction.transform.matrix")
        length(coordinates) == length(matrix_rows) && !isempty(coordinates) || error("Reduction transform matrix must be nonempty and square.")
        indices = [_cw_coordinate_index(model, raw, "reduction.transform.coordinate") for raw in coordinates]
        length(unique(indices)) == length(indices) || error("Reduction transform coordinates must be unique.")
        matrix = Matrix{Float64}(undef, length(indices), length(indices))
        for row in eachindex(matrix_rows)
            values = _cw_array(matrix_rows[row], "reduction.transform.matrix row")
            length(values) == length(indices) || error("Reduction transform matrix must be square.")
            for column in eachindex(values)
                matrix[row, column] = _cw_number(values[column], "reduction.transform.matrix entry")
            end
        end
        factor = lu(matrix; check=false)
        issuccess(factor) || error("Reduction transform matrix must be finite and invertible.")
        local_basis = Matrix{Float64}(I, dimension, dimension)
        local_basis[indices, indices] = matrix
        basis = basis * local_basis
    end
    retained = _cw_array(get(data, "retained", nothing), "reduction.retained")
    isempty(retained) && error("ReductionSpec retained coordinates cannot be empty.")
    indices = Int[]
    for raw in retained
        index = _cw_coordinate_index(model, raw, "reduction.retained coordinate")
        index in indices && error("Reduction retained coordinates must be ordered and unique.")
        push!(indices, index)
    end
    return (
        transpose(basis) * model.capacitance * basis,
        transpose(basis) * model.inverse_inductance * basis,
        transpose(basis) * model.conductance * basis,
        indices,
    )
end

const _CW_TARGETED_SCHUR_QUANTITIES = Set([
    "readout_diagonal_root_hz",
    "filter_diagonal_root_hz",
    "transfer_cofactor_zero_hz",
    "residue_normalized_midpoint_exchange_abs_real_hz",
    "diagonal_root_linewidth_sum_hz",
])

function _cw_targeted_schur_specs(objective)
    outputs = _cw_dict(get(objective, "cared_outputs", nothing), "objective.cared_outputs")
    length(outputs) == length(_CW_TARGETED_SCHUR_QUANTITIES) ||
        error("targeted_schur requires exactly its five cared outputs.")
    quantities = Dict{String,String}()
    anchors = nothing
    required_keys = Set([
        "kind",
        "quantity",
        "readout_root_anchor_hz",
        "filter_root_anchor_hz",
        "transfer_zero_anchor_hz",
    ])
    for (name, raw) in outputs
        spec = _cw_dict(raw, "cared output $(name)")
        Set(keys(spec)) == required_keys || error("targeted_schur cared-output $(name) has an invalid key set.")
        _cw_string(get(spec, "kind", nothing), "cared output $(name).kind") == "targeted_schur" ||
            error("targeted_schur requests cannot mix cared-output kinds.")
        quantity = _cw_string(get(spec, "quantity", nothing), "cared output $(name).quantity")
        quantity in _CW_TARGETED_SCHUR_QUANTITIES || error("Unsupported targeted_schur quantity $(quantity).")
        haskey(quantities, quantity) && error("targeted_schur quantity $(quantity) is declared more than once.")
        current_anchors = (
            readout=_cw_number(get(spec, "readout_root_anchor_hz", nothing), "targeted_schur readout_root_anchor_hz"),
            filter=_cw_number(get(spec, "filter_root_anchor_hz", nothing), "targeted_schur filter_root_anchor_hz"),
            transfer=_cw_number(get(spec, "transfer_zero_anchor_hz", nothing), "targeted_schur transfer_zero_anchor_hz"),
        )
        all(>(0), values(current_anchors)) || error("targeted_schur anchors must be positive.")
        isnothing(anchors) && (anchors = current_anchors)
        current_anchors == anchors || error("All targeted_schur cared outputs must share identical anchors.")
        quantities[quantity] = String(name)
    end
    Set(keys(quantities)) == _CW_TARGETED_SCHUR_QUANTITIES ||
        error("targeted_schur must declare each required quantity exactly once.")
    return quantities, anchors
end

function _cw_targeted_variable_key(variable)
    ref = _cw_dict(get(variable, "ref", nothing), "variable.ref")
    return _cw_string(get(ref, "component_id", nothing), "variable.ref.component_id") * "." *
        _cw_string(get(ref, "parameter_name", nothing), "variable.ref.parameter_name")
end

function _cw_targeted_perturbation(variable, value)
    current = Float64(value)
    isfinite(current) || error("targeted_schur training baseline must be finite.")
    parameter = _cw_dict(variable, "variable")
    lower = get(parameter, "lower", nothing)
    upper = get(parameter, "upper", nothing)
    lo = isnothing(lower) ? -Inf : _cw_number(lower, "variable.lower")
    hi = isnothing(upper) ? Inf : _cw_number(upper, "variable.upper")
    lo <= current <= hi || error("targeted_schur training baseline lies outside its variable bounds.")
    preferred = max(min(abs(current), floatmax(Float64) / 1.0e3) * 1.0e-3, 1.0e-15)
    for (direction, boundary) in ((1.0, hi), (-1.0, lo))
        available = isfinite(boundary) ? abs(boundary - current) : preferred
        available > 0 || continue
        step = min(preferred, available / 2)
        candidate = current + direction * step
        # At floating-point resolution a valid interval can contain only its
        # endpoint beside `current`; that endpoint is still a legal training
        # perturbation.
        candidate == current && isfinite(boundary) && (candidate = boundary)
        isfinite(candidate) && candidate != current && lo <= candidate <= hi && return candidate
    end
    error("Cannot train a targeted_schur affine term at a fixed variable bound.")
end

function _cw_targeted_portless_compiled(compiled)
    # Core deliberately reserves linear C/K/G extraction for a closed netlist.
    # A compiled port contributes its explicit R_port shunt (the target open
    # conductance); only the solver P row is removed for this extraction.
    netlist = Any[
        row for row in compiled.netlist
        if !(row isa Tuple && !isempty(row) && startswith(string(first(row)), "P"))
    ]
    return SuperconductingCircuitsCore.JosephsonCompiledCircuit(
        netlist=netlist,
        component_values=compiled.component_values,
        node_map=compiled.node_map,
        component_map=compiled.component_map,
        line_tap_map=compiled.line_tap_map,
        hb_intent_summary=compiled.hb_intent_summary,
        source_slot_map=compiled.source_slot_map,
        observable_request_map=compiled.observable_request_map,
        hb_validation_summary=compiled.hb_validation_summary,
        warnings=compiled.warnings,
        provenance=compiled.provenance,
        metadata=compiled.metadata,
    )
end

function _cw_targeted_schur_context(request, variables)
    objective = _cw_dict(get(request, "objective", nothing), "request.objective")
    _cw_targeted_schur_specs(objective)
    baseline_latent = isempty(variables) ? Float64[] : _cw_variable_baseline(get(request, "plan", nothing), variables)
    baseline_overrides = isempty(variables) ? Dict{String,Float64}() : _cw_candidate_overrides(variables, baseline_latent)
    reference_compiled = _cw_build_plan(get(request, "plan", nothing); overrides=baseline_overrides)
    reference_model = SuperconductingCircuitsCore.extract_linear_nodal_ckg_model(
        _cw_targeted_portless_compiled(reference_compiled),
    )
    c_ref, k_ref, g_ref, retained = _cw_reduction_model(reference_model, get(request, "reduction", nothing))
    length(retained) == 2 || error("targeted_schur requires exactly two retained complete-complement coordinates.")
    all(isfinite, c_ref) && all(isfinite, k_ref) && all(isfinite, g_ref) ||
        error("targeted_schur reference C/K/G matrices must be finite.")
    keys = String[]
    supported_parameters = Set([
        "readout_open_length_m",
        "shared_short_length_m",
        "coupled_length_m",
        "filter_open_length_m",
        "idc_finger_length_um",
    ])
    c_terms = Matrix{Float64}[]
    k_terms = Vector{Union{Nothing,Matrix{Float64}}}()
    for raw in variables
        variable = _cw_dict(raw, "variable")
        key = _cw_targeted_variable_key(variable)
        last(split(key, ".")) in supported_parameters || error(
            "targeted_schur supports only the four IPF segment lengths and IDC finger length.",
        )
        key in keys && error("targeted_schur variables must reference unique component parameters.")
        value = baseline_overrides[key]
        perturbed = _cw_targeted_perturbation(variable, value)
        perturbed_overrides = copy(baseline_overrides)
        perturbed_overrides[key] = perturbed
        candidate = _cw_build_plan(get(request, "plan", nothing); overrides=perturbed_overrides)
        candidate_model = SuperconductingCircuitsCore.extract_linear_nodal_ckg_model(
            _cw_targeted_portless_compiled(candidate),
        )
        candidate_model.node_names == reference_model.node_names ||
            error("targeted_schur variable $(key) changes compiled coordinate topology.")
        c1, k1, g1, retained1 = _cw_reduction_model(candidate_model, get(request, "reduction", nothing))
        retained1 == retained || error("targeted_schur variable $(key) changes retained coordinates.")
        isapprox(g1, g_ref; rtol=1.0e-12, atol=1.0e-18) ||
            error("targeted_schur variables must not change the fixed open conductance matrix.")
        push!(keys, key)
        push!(c_terms, (c1 - c_ref) / (perturbed - value))
        parameter_name = last(split(key, "."))
        if endswith(parameter_name, "_length_m") || parameter_name == "length_m"
            denominator = inv(perturbed) - inv(value)
            iszero(denominator) && error("targeted_schur length perturbation is singular.")
            push!(k_terms, (k1 - k_ref) / denominator)
        else
            isapprox(k1, k_ref; rtol=1.0e-10, atol=1.0e-18) ||
                error("targeted_schur non-length variable $(key) changes inverse inductance.")
            push!(k_terms, nothing)
        end
    end
    c0 = copy(c_ref)
    k0 = copy(k_ref)
    for index in eachindex(keys)
        c0 .-= baseline_overrides[keys[index]] .* c_terms[index]
        !isnothing(k_terms[index]) && (k0 .-= inv(baseline_overrides[keys[index]]) .* k_terms[index])
    end
    return (
        capacitance_zero=c0,
        stiffness_zero=k0,
        capacitance_terms=c_terms,
        stiffness_terms=k_terms,
        variable_keys=keys,
        baseline_parameters=baseline_overrides,
        conductance=Matrix{Float64}(g_ref),
        retained_indices=retained,
        eliminated_indices=[index for index in axes(c_ref, 1) if !(index in retained)],
        dimension=size(c_ref, 1),
        compiled_netlist_rows=length(reference_compiled.netlist),
    )
end

function _cw_targeted_candidate_context(context, overrides)
    capacitance = copy(context.capacitance_zero)
    stiffness = copy(context.stiffness_zero)
    for index in eachindex(context.variable_keys)
        value = get(overrides, context.variable_keys[index], context.baseline_parameters[context.variable_keys[index]])
        isfinite(value) || throw(_CWCandidateNotEvaluable("targeted_schur candidate parameter is non-finite."))
        capacitance .+= value .* context.capacitance_terms[index]
        if !isnothing(context.stiffness_terms[index])
            value > 0 || throw(_CWCandidateNotEvaluable("targeted_schur length parameter must be positive."))
            stiffness .+= inv(value) .* context.stiffness_terms[index]
        end
    end
    return (
        capacitance=Matrix{Float64}((capacitance + transpose(capacitance)) / 2),
        stiffness=Matrix{Float64}((stiffness + transpose(stiffness)) / 2),
        conductance=context.conductance,
        retained_indices=context.retained_indices,
        eliminated_indices=context.eliminated_indices,
        dimension=context.dimension,
    )
end

function _cw_targeted_schur_operator(context, omega)
    frequency = ComplexF64(omega)
    isfinite(real(frequency)) && isfinite(imag(frequency)) && real(frequency) > 0 ||
        throw(_CWTargetedSchurNumericalError("targeted_schur selected an invalid angular frequency."))
    dynamic = ComplexF64.(context.stiffness) .- frequency^2 .* context.capacitance .-
        im * frequency .* context.conductance
    derivative = -2 * frequency .* context.capacitance .- im .* context.conductance
    retained, eliminated = context.retained_indices, context.eliminated_indices
    if isempty(eliminated)
        return (dynamic=dynamic[retained, retained], derivative=derivative[retained, retained])
    end
    dee, der = dynamic[eliminated, eliminated], dynamic[eliminated, retained]
    dpe, dpr = derivative[eliminated, eliminated], derivative[eliminated, retained]
    factor = try
        lu(dee; check=true)
    catch exception
        exception isa SingularException || exception isa ZeroPivotException || rethrow()
        throw(_CWTargetedSchurNumericalError("targeted_schur eliminated block is singular."))
    end
    response = try
        factor \ der
    catch exception
        exception isa SingularException || exception isa ZeroPivotException || rethrow()
        throw(_CWTargetedSchurNumericalError("targeted_schur eliminated solve failed."))
    end
    response_derivative = factor \ (dpr - dpe * response)
    all(value -> isfinite(real(value)) && isfinite(imag(value)), response) ||
        throw(_CWTargetedSchurNumericalError("targeted_schur eliminated solve became non-finite."))
    effective = dynamic[retained, retained] - dynamic[retained, eliminated] * response
    effective_derivative = derivative[retained, retained] - derivative[retained, eliminated] * response -
        dynamic[retained, eliminated] * response_derivative
    return (
        dynamic=Matrix{ComplexF64}((effective + transpose(effective)) / 2),
        derivative=Matrix{ComplexF64}((effective_derivative + transpose(effective_derivative)) / 2),
    )
end

function _cw_targeted_schur_newton(value_and_derivative, initial, label; tolerance=1.0e-10)
    omega = ComplexF64(initial)
    for iteration in 1:32
        value, derivative = value_and_derivative(omega)
        all(isfinite, (real(value), imag(value), real(derivative), imag(derivative))) ||
            throw(_CWTargetedSchurNumericalError("$(label) evaluation became non-finite."))
        iszero(derivative) && throw(_CWTargetedSchurNumericalError("$(label) derivative is zero."))
        delta = value / derivative
        omega -= delta
        isfinite(real(omega)) && isfinite(imag(omega)) && real(omega) > 0 ||
            throw(_CWTargetedSchurNumericalError("$(label) selected an invalid root."))
        abs(delta) <= tolerance * max(abs(omega), 1.0) && return (root=omega, iterations=iteration, derivative=value_and_derivative(omega)[2])
    end
    throw(_CWTargetedSchurNumericalError("$(label) did not settle within 32 iterations."))
end

function _cw_targeted_simple_root!(context, root, row, column, label; require_nonpole=false)
    operator = _cw_targeted_schur_operator(context, root)
    value = operator.dynamic[row, column]
    derivative = operator.derivative[row, column]
    frequency_scale = max(abs(root), 1.0)
    scale = max(
        opnorm(operator.dynamic, Inf),
        frequency_scale * opnorm(operator.derivative, Inf),
        floatmin(Float64),
    )
    abs(value) <= sqrt(eps(Float64)) * scale ||
        throw(_CWTargetedSchurNumericalError("$(label) residual is not numerically resolved."))
    abs(derivative) * frequency_scale > 4096 * context.dimension * eps(Float64) * scale ||
        throw(_CWTargetedSchurNumericalError("$(label) is not machine-resolved as a simple root."))
    if require_nonpole
        denominator = det(operator.dynamic)
        isfinite(real(denominator)) && isfinite(imag(denominator)) &&
            abs(denominator) > 4096 * context.dimension * eps(Float64) * scale^2 ||
            throw(_CWTargetedSchurNumericalError("$(label) coincides with an unresolved response pole."))
    end
    return nothing
end

function _cw_targeted_schur_outputs(context, anchors)
    readout = _cw_targeted_schur_newton(2pi * anchors.readout, "targeted_schur readout diagonal root") do omega
        operator = _cw_targeted_schur_operator(context, omega)
        operator.dynamic[1, 1], operator.derivative[1, 1]
    end
    filter = _cw_targeted_schur_newton(2pi * anchors.filter, "targeted_schur filter diagonal root") do omega
        operator = _cw_targeted_schur_operator(context, omega)
        operator.dynamic[2, 2], operator.derivative[2, 2]
    end
    zero = _cw_targeted_schur_newton(2pi * anchors.transfer, "targeted_schur transfer cofactor zero"; tolerance=sqrt(eps(Float64))) do omega
        operator = _cw_targeted_schur_operator(context, omega)
        operator.dynamic[2, 1], operator.derivative[2, 1]
    end
    _cw_targeted_simple_root!(context, readout.root, 1, 1, "targeted_schur readout diagonal root")
    _cw_targeted_simple_root!(context, filter.root, 2, 2, "targeted_schur filter diagonal root")
    _cw_targeted_simple_root!(context, zero.root, 2, 1, "targeted_schur transfer cofactor zero"; require_nonpole=true)
    slopes = (-readout.derivative, -filter.derivative)
    normalization = sqrt(slopes[1] * slopes[2])
    isfinite(real(normalization)) && isfinite(imag(normalization)) && !iszero(normalization) ||
        throw(_CWTargetedSchurNumericalError("targeted_schur residue normalization is singular."))
    midpoint = (readout.root + filter.root) / 2
    exchange = _cw_targeted_schur_operator(context, midpoint).dynamic[1, 2] / normalization
    roots_hz = (readout.root / (2pi), filter.root / (2pi))
    linewidths = (-2 * imag(roots_hz[1]), -2 * imag(roots_hz[2]))
    all(value -> isfinite(value) && value >= 0, linewidths) ||
        throw(_CWTargetedSchurNumericalError("targeted_schur diagonal-root linewidths are invalid."))
    return Dict(
        "readout_diagonal_root_hz" => Float64(real(roots_hz[1])),
        "filter_diagonal_root_hz" => Float64(real(roots_hz[2])),
        "transfer_cofactor_zero_hz" => Float64(real(zero.root / (2pi))),
        "residue_normalized_midpoint_exchange_abs_real_hz" => Float64(abs(real(exchange)) / (2pi)),
        "diagonal_root_linewidth_sum_hz" => Float64(sum(linewidths)),
    )
end

function _cw_direct_cared_outputs(compiled, objective, reduction; targeted_context=nothing, overrides=Dict{String,Float64}())
    outputs = _cw_dict(get(objective, "cared_outputs", nothing), "objective.cared_outputs")
    kinds = [_cw_string(get(_cw_dict(spec, "cared output"), "kind", nothing), "cared output kind") for spec in values(outputs)]
    if any(==("targeted_schur"), kinds)
        all(==("targeted_schur"), kinds) || error("A direct request cannot mix targeted_schur with other cared-output kinds.")
        isnothing(compiled) || error("targeted_schur must use its fixed affine C/K context.")
        isnothing(targeted_context) && error("targeted_schur fixed context is absent.")
        quantities, anchors = _cw_targeted_schur_specs(objective)
        bundle = _cw_targeted_schur_outputs(_cw_targeted_candidate_context(targeted_context, overrides), anchors)
        return Dict{String,Float64}(name => bundle[quantity] for (quantity, name) in quantities)
    end
    isnothing(compiled) && error("Direct cared outputs require a compiled circuit.")
    model = SuperconductingCircuitsCore.extract_linear_nodal_ckg_model(compiled)
    uses_schur = any(==("schur_dynamic_stiffness_abs"), kinds)
    uses_closed = any(==("closed_mode_frequency_hz"), kinds)
    uses_schur && uses_closed && error("A direct request cannot mix closed-mode and explicit Schur cared-output kinds.")
    if uses_schur
        all(==("schur_dynamic_stiffness_abs"), kinds) || error("Unsupported direct cared-output kind.")
        capacitance, inverse_inductance, conductance, terminals = _cw_reduction_model(model, reduction)
        result = Dict{String,Float64}()
        for name in sort!(collect(keys(outputs)))
            spec = _cw_dict(outputs[name], "cared output $(name)")
            frequency = _cw_number(get(spec, "frequency_hz", nothing), "Schur cared output frequency_hz")
            frequency > 0 || error("Schur cared output frequency_hz must be positive.")
            schur = SuperconductingCircuitsCore.schur_dynamic_stiffness(
                capacitance, inverse_inductance, conductance, 2pi * frequency, terminals,
            )
            row = _cw_integer(get(spec, "row", nothing), "Schur cared output row")
            column = _cw_integer(get(spec, "column", nothing), "Schur cared output column")
            1 <= row <= size(schur.dynamic_stiffness, 1) && 1 <= column <= size(schur.dynamic_stiffness, 2) || error("Schur cared-output row/column is out of bounds.")
            result[name] = abs(schur.dynamic_stiffness[row, column])
        end
        return result
    end
    isnothing(reduction) || error("Closed-mode direct cared outputs do not accept an ignored ReductionSpec.")
    all(iszero, model.conductance) || error(
        "closed_mode_frequency_hz requires zero conductance; use explicit C/K/G Schur cared outputs for a lossy Plan.",
    )
    reduced = SuperconductingCircuitsCore.reduce_free_charge_coordinates(
        SuperconductingCircuitsCore.extract_linear_nodal_model(compiled),
    )
    modes = SuperconductingCircuitsCore.solve_generalized_modes(reduced)
    result = Dict{String,Float64}()
    for name in sort!(collect(keys(outputs)))
        spec = _cw_dict(outputs[name], "cared output $(name)")
        kind = _cw_string(get(spec, "kind", nothing), "cared output $(name).kind")
        kind == "closed_mode_frequency_hz" || error("Direct backend supports only closed_mode_frequency_hz or schur_dynamic_stiffness_abs cared outputs.")
        index = _cw_integer(get(spec, "mode_index", nothing), "cared output mode_index")
        1 <= index <= length(modes.frequencies_hz) || error("Requested closed mode index is out of bounds.")
        result[name] = modes.frequencies_hz[index]
    end
    return result
end

function _cw_expression(value, outputs)::Float64
    value isa Real && return _cw_number(value, "expression literal")
    node = _cw_dict(value, "expression")
    if haskey(node, "output")
        output = _cw_string(node["output"], "expression.output")
        haskey(outputs, output) || error("Unknown cared output $(output).")
        return outputs[output]
    end
    haskey(node, "const") && return _cw_number(node["const"], "expression.const")
    op = _cw_string(get(node, "op", nothing), "expression.op")
    args = [_cw_expression(item, outputs) for item in _cw_array(get(node, "args", nothing), "expression.args")]
    op == "add" && return sum(args)
    op == "sub" && length(args) == 2 && return args[1] - args[2]
    op == "mul" && return prod(args)
    op == "div" && length(args) == 2 && args[2] != 0 && return args[1] / args[2]
    op == "abs" && length(args) == 1 && return abs(args[1])
    op == "square" && length(args) == 1 && return args[1]^2
    op == "neg" && length(args) == 1 && return -args[1]
    op == "sum_squares" && return sum(abs2, args)
    op == "less_equal" && length(args) == 2 && return args[1] <= args[2] ? 1.0 : 0.0
    op == "greater_equal" && length(args) == 2 && return args[1] >= args[2] ? 1.0 : 0.0
    error("Invalid restricted objective expression $(op).")
end

function _cw_objective(payload, outputs)
    residuals = _cw_dict(get(payload, "residuals", nothing), "objective.residuals")
    values = Dict{String,Float64}(name => _cw_expression(spec, outputs) for (name, spec) in residuals)
    cost = _cw_expression(get(payload, "cost", nothing), values)
    isfinite(cost) || error("Objective cost is non-finite.")
    return values, cost
end

function _cw_gate_values(request, outputs)
    values = Any[]
    for raw in _cw_array(get(request, "gates", Any[]), "request.gates")
        gate = _cw_dict(raw, "gate")
        state = _cw_string(get(gate, "state", nothing), "gate.state")
        state in ("active", "proposed", "inactive") || error("Gate state must be active, proposed, or inactive.")
        authority = get(gate, "human_authority", nothing)
        state == "active" && !(authority isa AbstractString && !isempty(authority)) && error("Active Gate lacks Human authority.")
        value = _cw_expression(get(gate, "expression", nothing), outputs)
        push!(values, Dict("id" => _cw_string(get(gate, "id", nothing), "gate.id"), "state" => state, "value" => value))
    end
    return values
end

function _cw_validate_artifacts(request)
    bindings = _cw_dict(get(request, "artifacts", Dict{String,Any}()), "request.artifacts")
    sealed = Dict{String,Any}()
    for name in sort!(collect(keys(bindings)))
        binding = _cw_dict(bindings[name], "artifact $(name)")
        _cw_string(get(binding, "schema", nothing), "artifact $(name).schema")
        units = get(binding, "units", nothing)
        valid_units = (units isa AbstractString && !isempty(units)) || (units isa AbstractDict && !isempty(units))
        valid_units || error("Artifact $(name) requires declared units.")
        isempty(_cw_dict(get(binding, "provenance", nothing), "artifact $(name).provenance")) && error(
            "Artifact $(name) requires nonempty provenance.",
        )
        path = _cw_string(get(binding, "path", nothing), "artifact $(name).path")
        isfile(path) || error("Artifact $(name) bound path is absent: $(path)")
        expected = _cw_string(get(binding, "source_sha256", nothing), "artifact $(name).source_sha256")
        actual = _cw_sha256(path)
        expected == actual || error("Artifact $(name) source_sha256 mismatch: expected=$(expected) actual=$(actual)")
        sealed[name] = merge(copy(binding), Dict("path" => abspath(path), "source_sha256" => actual))
    end
    return sealed
end

function _cw_candidate_status(gates)
    rejected = [gate["id"] for gate in gates if gate["state"] == "active" && gate["value"] == 0.0]
    return isempty(rejected) ? "PASS" : "REJECTED_BY_GATE", rejected
end

function _cw_uses_targeted_schur(objective)
    outputs = _cw_dict(get(objective, "cared_outputs", nothing), "objective.cared_outputs")
    return any(
        _cw_string(get(_cw_dict(spec, "cared output"), "kind", nothing), "cared output kind") == "targeted_schur"
        for spec in values(outputs)
    )
end

function _cw_evaluate(request; overrides=Dict{String,Float64}(), candidate_parameters=Dict{String,Float64}(), targeted_context=nothing)
    artifacts = _cw_validate_artifacts(request)
    objective = _cw_dict(get(request, "objective", nothing), "request.objective")
    backend = _cw_string(get(request, "backend", nothing), "request.backend")
    targeted = _cw_uses_targeted_schur(objective)
    backend == "direct" || !targeted || error("targeted_schur is available only on the direct backend.")
    if targeted && isnothing(targeted_context)
        targeted_context = _cw_targeted_schur_context(
            request,
            _cw_array(get(request, "variables", Any[]), "request.variables"),
        )
    end
    compiled = targeted ? nothing : _cw_build_plan(get(request, "plan", nothing); overrides=overrides)
    backend == "hb" && !isnothing(get(request, "reduction", nothing)) && error(
        "HB V1 has no registered ReductionSpec executor; refusing to ignore a declared reduction."
    )
    outputs = backend == "hb" ? _cw_cared_outputs(compiled, objective) :
        backend == "direct" ? _cw_direct_cared_outputs(
            compiled,
            objective,
            get(request, "reduction", nothing);
            targeted_context=targeted_context,
            overrides=overrides,
        ) : error("Unsupported backend $(backend).")
    residuals, cost = _cw_objective(objective, outputs)
    gates = _cw_gate_values(request, outputs)
    status, rejecting_gates = _cw_candidate_status(gates)
    return Dict{String,Any}(
        "status" => status,
        "rejecting_gate_ids" => rejecting_gates,
        "validated_artifacts" => artifacts,
        "cared_outputs" => outputs,
        "residuals" => residuals,
        "cost" => cost,
        "gates" => gates,
        "candidate_parameters" => candidate_parameters,
        "applied_parameter_bindings" => overrides,
        "compiled_netlist_rows" => targeted ? targeted_context.compiled_netlist_rows : length(compiled.netlist),
    )
end

function _cw_expected_candidate_error(exception)
    return exception isa _CWCandidateNotEvaluable || exception isa _CWTargetedSchurNumericalError || exception isa SuperconductingCircuitsCore.HBSolverNumericalError ||
        exception isa SingularException || exception isa PosDefException ||
        exception isa ZeroPivotException || exception isa RankDeficientException ||
        exception isa LAPACKException
end

function _cw_candidate_key(latent)
    return _cw_fingerprint([Float64(value) for value in latent])
end

function _cw_ledger_seed()
    return _cw_fingerprint(Dict("schema" => "circuit-workbench-optimization-ledger.v1"))
end

function _cw_validate_ledger_entries!(ledger, fingerprint)
    entries = _cw_array(get(ledger, "entries", nothing), "optimization ledger entries")
    previous = _cw_ledger_seed()
    for (index, raw) in enumerate(entries)
        entry = _cw_dict(raw, "optimization ledger entry")
        _cw_integer(get(entry, "candidate_index", nothing), "ledger candidate_index") == index ||
            error("Optimization ledger candidate indices must be contiguous and ordered.")
        latent = [_cw_number(value, "ledger latent value") for value in _cw_array(get(entry, "latent", nothing), "ledger latent")]
        candidate_key = _cw_string(get(entry, "candidate_key", nothing), "ledger candidate_key")
        candidate_key == _cw_candidate_key(latent) || error(
            "Optimization ledger candidate key does not match its latent vector.",
        )
        get(entry, "previous_entry_sha256", nothing) == previous || error(
            "Optimization ledger hash chain is broken.",
        )
        expected = get(entry, "entry_sha256", nothing)
        body = copy(entry)
        delete!(body, "entry_sha256")
        actual = _cw_fingerprint(body)
        expected == actual || error("Optimization ledger entry hash mismatch.")
        previous = actual
    end
    get(ledger, "history_sha256", nothing) == previous || error(
        "Optimization ledger history hash mismatch.",
    )
    ledger["entries"] = entries
    return ledger
end

function _cw_load_ledger(path, fingerprint)
    if !isfile(path)
        return Dict{String,Any}(
            "schema" => "circuit-workbench-optimization-ledger.v1",
            "request_fingerprint_sha256" => fingerprint,
            "history_sha256" => _cw_ledger_seed(),
            "entries" => Any[],
        )
    end
    ledger = _cw_dict(JSON3.read(read(path, String)), "optimization ledger")
    get(ledger, "schema", nothing) == "circuit-workbench-optimization-ledger.v1" || error("Optimization ledger schema mismatch.")
    get(ledger, "request_fingerprint_sha256", nothing) == fingerprint || error("Optimization ledger belongs to a different sealed request fingerprint.")
    return _cw_validate_ledger_entries!(ledger, fingerprint)
end

function _cw_validate_existing_optimization_receipt!(receipt_path, request)
    isfile(receipt_path) || return nothing
    receipt = _cw_dict(JSON3.read(read(receipt_path, String)), "existing optimization receipt")
    get(receipt, "schema", nothing) == _CW_RECEIPT_SCHEMA || error("Existing optimization receipt schema mismatch.")
    canonical = get(receipt, "canonical_sha256", nothing)
    receipt_body = copy(receipt)
    delete!(receipt_body, "canonical_sha256")
    canonical == _cw_fingerprint(receipt_body) || error("Existing optimization receipt canonical hash mismatch.")
    fingerprint = _cw_string(get(request, "fingerprint_sha256", nothing), "request.fingerprint_sha256")
    get(receipt, "request_fingerprint_sha256", nothing) == fingerprint || error(
        "Existing optimization receipt belongs to a different sealed request.",
    )
    expected_ledger_path = joinpath(dirname(abspath(receipt_path)), "circuit-workbench-optimization-ledger.v1.json")
    result = get(receipt, "result", nothing)
    if result isa AbstractDict
        ledger_path = _cw_string(get(result, "ledger_path", nothing), "existing optimization receipt ledger_path")
        abspath(ledger_path) == expected_ledger_path || error("Existing optimization receipt ledger path is not standard.")
    end
    if isfile(expected_ledger_path)
        get(receipt, "ledger_sha256", nothing) == _cw_sha256(expected_ledger_path) || error(
            "Existing optimization receipt ledger hash mismatches current ledger bytes.",
        )
        _cw_load_ledger(expected_ledger_path, fingerprint)
    elseif !isnothing(get(receipt, "ledger_sha256", nothing))
        error("Existing optimization receipt ledger is absent.")
    end
    return nothing
end

function _cw_ledger_entry_cost(entry)
    outcome = _cw_dict(get(entry, "outcome", nothing), "ledger outcome")
    status = _cw_string(get(outcome, "status", nothing), "ledger outcome status")
    status == "PASS" || return Inf
    return _cw_number(get(outcome, "cost", nothing), "ledger outcome cost")
end

function _cw_optimize(request, ledger_path)
    optimizer = _cw_dict(get(request, "optimizer", nothing), "request.optimizer")
    get(optimizer, "algorithm", nothing) == "cma_es" || error("Circuit Workbench V1 supports only cma_es.")
    _cw_string(get(optimizer, "human_authority", nothing), "optimizer.human_authority")
    variables = _cw_array(get(request, "variables", nothing), "request.variables")
    isempty(variables) && error("CMA-ES requires at least one variable.")
    controls = _cw_dict(get(optimizer, "controls", nothing), "optimizer.controls")
    resource_controls = _cw_dict(get(optimizer, "resource_controls", Dict{String,Any}()), "optimizer.resource_controls")
    all(key == "worker_count" for key in keys(resource_controls)) || error("worker_count is the only supported optimizer resource control.")
    worker_count = _cw_integer(get(resource_controls, "worker_count", 1), "optimizer.resource_controls.worker_count")
    worker_count >= 1 || error("worker_count must be positive.")
    Threads.nthreads() >= worker_count || error("Julia action has fewer threads than requested worker_count.")
    sigma = _cw_number(get(controls, "initial_sigma", nothing), "optimizer.controls.initial_sigma")
    sigma > 0 || error("optimizer initial_sigma must be positive.")
    maxiter = _cw_integer(get(controls, "maxiter", nothing), "optimizer.controls.maxiter")
    maxfevals = _cw_integer(get(controls, "maxfevals", nothing), "optimizer.controls.maxfevals")
    popsize = _cw_integer(get(controls, "popsize", nothing), "optimizer.controls.popsize")
    maxiter > 0 && maxfevals > 0 && popsize > 0 || error("CMA controls must be positive integers.")
    seed = UInt(_cw_integer(get(optimizer, "seed", nothing), "optimizer.seed"))
    initial = _cw_variable_baseline(get(request, "plan", nothing), variables)
    lower, upper = _cw_variable_bounds(variables)
    fingerprint = _cw_string(get(request, "fingerprint_sha256", nothing), "request.fingerprint_sha256")
    objective_spec = _cw_dict(get(request, "objective", nothing), "request.objective")
    targeted_context = _cw_uses_targeted_schur(objective_spec) ?
        _cw_targeted_schur_context(request, variables) : nothing
    ledger = _cw_load_ledger(ledger_path, fingerprint)
    entries = _cw_array(get(ledger, "entries", nothing), "optimization ledger entries")
    cache = Dict{String,Dict{String,Any}}()
    for raw in entries
        entry = _cw_dict(raw, "optimization ledger entry")
        key = _cw_string(get(entry, "candidate_key", nothing), "ledger candidate_key")
        haskey(cache, key) && error("Optimization ledger contains duplicate candidate identity.")
        cache[key] = entry
    end
    evaluate_candidate = latent -> try
        overrides = _cw_candidate_overrides(variables, latent)
        _cw_evaluate(
            request;
            overrides=overrides,
            candidate_parameters=_cw_requested_candidate_parameters(variables, latent),
            targeted_context=targeted_context,
        )
    catch exception
        _cw_expected_candidate_error(exception) || rethrow()
        Dict{String,Any}("status" => "NOT_EVALUABLE", "failure" => sprint(showerror, exception))
    end
    objective = candidates -> begin
        size(candidates, 1) == length(variables) || error("CMA matrix dimension mismatches variables.")
        count = size(candidates, 2)
        latents = [Float64.(view(candidates, :, column)) for column in 1:count]
        keys = [_cw_candidate_key(latent) for latent in latents]
        tasks = Dict{String,Task}()
        for column in 1:count
            key = keys[column]
            if !haskey(cache, key) && !haskey(tasks, key)
                latent = latents[column]
                if worker_count == 1
                    tasks[key] = @async evaluate_candidate(latent)
                else
                    tasks[key] = Threads.@spawn evaluate_candidate(latent)
                end
            end
        end
        outcomes = Vector{Any}(undef, count)
        for column in 1:count
            key = keys[column]
            if haskey(cache, key)
                outcomes[column] = get(cache[key], "outcome", nothing)
            else
                outcomes[column] = fetch(tasks[key])
            end
        end
        for column in 1:count
            key = keys[column]
            if !haskey(cache, key)
                entry = Dict{String,Any}(
                    "candidate_index" => length(entries) + 1,
                    "candidate_key" => key,
                    "latent" => latents[column],
                    "outcome" => outcomes[column],
                    "previous_entry_sha256" => ledger["history_sha256"],
                )
                entry["entry_sha256"] = _cw_fingerprint(entry)
                push!(entries, entry)
                cache[key] = entry
                ledger["history_sha256"] = entry["entry_sha256"]
            end
        end
        ledger["entries"] = entries
        _cw_atomic_json(ledger_path, ledger)
        return [haskey(cache, key) ? _cw_ledger_entry_cost(cache[key]) : error("Candidate ledger entry missing.") for key in keys]
    end
    cma = CMAEvolutionStrategy.minimize(
        objective,
        initial,
        sigma;
        lower=lower,
        upper=upper,
        seed=seed,
        popsize=popsize,
        maxiter=maxiter,
        maxfevals=maxfevals,
        parallel_evaluation=true,
        multi_threading=false,
        verbosity=0,
    )
    best_entry = nothing
    best_cost = Inf
    for entry in entries
        cost = _cw_ledger_entry_cost(_cw_dict(entry, "optimization ledger entry"))
        if cost < best_cost
            best_cost = cost
            best_entry = _cw_dict(entry, "optimization ledger entry")
        end
    end
    best = isnothing(best_entry) ? nothing : get(best_entry, "outcome", nothing)
    return Dict{String,Any}(
        "best" => best,
        "winner_candidate_key" => isnothing(best_entry) ? nothing : best_entry["candidate_key"],
        "winner_candidate_index" => isnothing(best_entry) ? nothing : best_entry["candidate_index"],
        "winner_physical_parameters" => isnothing(best) ? nothing : get(best, "candidate_parameters", nothing),
        "ledger_path" => abspath(ledger_path),
        "ledger_sha256" => _cw_sha256(ledger_path),
        "generation_count" => Int(cma.stop.it),
        "candidate_count" => length(entries),
        "optimizer_stop_reason" => String(cma.stop.reason),
    )
end

function _cw_receipt(request, status, request_path; result=nothing, failure=nothing, ledger_sha=nothing)
    plan = _cw_dict(get(request, "plan", nothing), "request.plan")
    runtime = _cw_dict(get(request, "runtime", nothing), "request.runtime")
    lifecycle_state = _cw_string(get(request, "lifecycle_state", nothing), "request.lifecycle_state")
    lifecycle_state in ("CONVERGING", "ACCEPTED", "STABILIZED") || error(
        "Request lifecycle_state must be CONVERGING, ACCEPTED, or STABILIZED.",
    )
    data_classification = _cw_string(get(request, "data_classification", nothing), "request.data_classification")
    data_classification in ("public", "project-internal", "NCUAS-private", "report-safe-derived") || error(
        "Request data_classification must be public, project-internal, NCUAS-private, or report-safe-derived.",
    )
    output_sha = isnothing(result) ? nothing : _cw_fingerprint(result)
    ledger_sha = isnothing(result) ? ledger_sha : get(result, "ledger_sha256", nothing)
    receipt = Dict{String,Any}(
        "schema" => _CW_RECEIPT_SCHEMA,
        "run_id" => _cw_string(get(request, "run_id", nothing), "request.run_id"),
        "request_fingerprint_sha256" => _cw_string(get(request, "fingerprint_sha256", nothing), "request.fingerprint_sha256"),
        "request_path" => abspath(request_path),
        "request_sha256" => _cw_sha256(request_path),
        "plan_sha256" => _cw_string(get(plan, "canonical_sha256", nothing), "plan.canonical_sha256"),
        "python_runtime_source_sha256" => _cw_string(get(runtime, "python_package_source_sha256", nothing), "runtime.python_package_source_sha256"),
        "julia_version" => string(VERSION),
        "runner_tree_sha256" => _cw_string(get(runtime, "runner_tree_sha256", nothing), "runtime.runner_tree_sha256"),
        "core_tree_sha256" => _cw_string(get(runtime, "core_tree_sha256", nothing), "runtime.core_tree_sha256"),
        "julia_executable_sha256" => _cw_string(get(runtime, "julia_executable_sha256", nothing), "runtime.julia_executable_sha256"),
        "status" => status,
        "lifecycle_state" => lifecycle_state,
        "data_classification" => data_classification,
        "promotion_eligible" => false,
        "artifact_bindings" => get(request, "artifacts", Dict{String,Any}()),
        "output_sha256" => output_sha,
        "ledger_sha256" => ledger_sha,
        "nonclaims" => [
            "no artifact bytes are copied into this receipt",
            "no promotion or publication claim",
        ],
        "result" => result,
        "failure" => failure,
    )
    receipt["canonical_sha256"] = _cw_fingerprint(receipt)
    return receipt
end

"""Execute one sealed Circuit Workbench request and atomically write its receipt."""
function execute_circuit_workbench_action(request_path::AbstractString, receipt_path::AbstractString)
    basename(request_path) == "circuit-workbench-run-request.v1.json" || error("Request must use the standard durable request filename.")
    basename(receipt_path) == "circuit-workbench-run-receipt.v1.json" || error("Receipt must use the standard durable receipt filename.")
    dirname(abspath(request_path)) == dirname(abspath(receipt_path)) || error("Request and receipt must share one run directory.")
    request = _cw_dict(JSON3.read(read(request_path, String)), "request")
    ledger_path = joinpath(dirname(receipt_path), "circuit-workbench-optimization-ledger.v1.json")
    if get(request, "action", nothing) == "optimize" && !isfile(receipt_path) && isfile(ledger_path)
        error("Existing optimization ledger has no sealed receipt anchor.")
    end
    try
        get(request, "schema", nothing) == _CW_REQUEST_SCHEMA || error("Request schema is not $(_CW_REQUEST_SCHEMA).")
        action = _cw_string(get(request, "action", nothing), "request.action")
        action in ("evaluate", "optimize") || error("Unsupported Circuit Workbench action $(action).")
        lifecycle_state = _cw_string(get(request, "lifecycle_state", nothing), "request.lifecycle_state")
        lifecycle_state in ("CONVERGING", "ACCEPTED", "STABILIZED") || error(
            "Request lifecycle_state must be CONVERGING, ACCEPTED, or STABILIZED.",
        )
        data_classification = _cw_string(get(request, "data_classification", nothing), "request.data_classification")
        data_classification in ("public", "project-internal", "NCUAS-private", "report-safe-derived") || error(
            "Request data_classification must be public, project-internal, NCUAS-private, or report-safe-derived.",
        )
        expected = get(request, "fingerprint_sha256", nothing)
        request_without_fingerprint = Dict{String,Any}(request)
        delete!(request_without_fingerprint, "fingerprint_sha256")
        actual = _cw_fingerprint(request_without_fingerprint)
        expected == actual || error("Request fingerprint_sha256 mismatches canonical request bytes: expected=$(expected) actual=$(actual).")
        basename(dirname(abspath(request_path))) == _cw_string(get(request, "run_id", nothing), "request.run_id") || error("Request run_id does not match its standard durable path.")
        _cw_validate_runtime_identity(request)
        plan = _cw_dict(get(request, "plan", nothing), "request.plan")
        plan_hash = get(plan, "canonical_sha256", nothing)
        plan_body = Dict{String,Any}(plan)
        delete!(plan_body, "canonical_sha256")
        plan_hash == _cw_fingerprint(plan_body) || error("Plan canonical_sha256 mismatches canonical Plan bytes.")
        result = if action == "evaluate"
            _cw_evaluate(request)
        else
            _cw_validate_existing_optimization_receipt!(receipt_path, request)
            _cw_optimize(
                request, joinpath(dirname(receipt_path), "circuit-workbench-optimization-ledger.v1.json"),
            )
        end
        status = if action == "evaluate"
            result["status"]
        elseif !isnothing(result["best"])
            "PASS"
        else
            ledger = _cw_load_ledger(result["ledger_path"], _cw_string(get(request, "fingerprint_sha256", nothing), "request.fingerprint_sha256"))
            outcomes = [_cw_dict(get(_cw_dict(entry, "ledger entry"), "outcome", nothing), "ledger outcome") for entry in _cw_array(ledger["entries"], "ledger entries")]
            !isempty(outcomes) && all(get(outcome, "status", nothing) == "REJECTED_BY_GATE" for outcome in outcomes) ? "REJECTED_BY_GATE" : "NOT_EVALUABLE"
        end
        receipt = _cw_receipt(request, status, request_path; result=result)
        _cw_atomic_json(receipt_path, receipt)
        return receipt_path
    catch exception
        failure = Dict(
            "error_code" => "circuit_workbench_action_failed",
            "category" => "task_execution_failed",
            "retryable" => false,
            "type" => string(typeof(exception)),
            "message" => sprint(showerror, exception),
        )
        try
            ledger_path = joinpath(dirname(receipt_path), "circuit-workbench-optimization-ledger.v1.json")
            _cw_atomic_json(
                receipt_path,
                _cw_receipt(
                    request,
                    "FAILED",
                    request_path;
                    failure=failure,
                    ledger_sha=isfile(ledger_path) ? _cw_sha256(ledger_path) : nothing,
                ),
            )
        catch
            # The original execution defect remains authoritative when even its
            # sealed request cannot support a failure receipt.
        end
        rethrow()
    end
end
