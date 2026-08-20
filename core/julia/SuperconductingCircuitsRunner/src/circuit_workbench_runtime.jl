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
    capacitance > 0 && inductance > 0 || throw(_CWCandidateNotEvaluable("$(id) LC values must be positive."))
    signal = SuperconductingCircuitsCore.external_node("cw_$(id)_signal")
    SuperconductingCircuitsCore.add_parallel_lc_resonator!(
        plan;
        id=id,
        node=signal,
        capacitance=capacitance,
        inductance=inductance,
    )
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
        type_id == "workbench.parallel_lc_resonator.v1" || error(
            "Unsupported Circuit Workbench Julia lowerer for component type $(type_id). " *
            "Register a reviewed Core lowerer before using it in a sealed run.",
        )
        _cw_parallel_lc!(plan, component, overrides)
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
        transform in ("identity", "log") || error("Unsupported variable transform $(transform).")
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
        value = transform == "identity" ? Float64(latent[index]) : transform == "log" ? exp(Float64(latent[index])) : error("Unsupported variable transform $(transform).")
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
        value = transform == "identity" ? Float64(latent[index]) : transform == "log" ? exp(Float64(latent[index])) : error("Unsupported variable transform $(transform).")
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
    coordinate == "signal" || error("Builtin parallel-LC reduction exposes only the signal coordinate.")
    # Core's external-node lowering prefixes the authored endpoint in its
    # closed-nodal ordering; this is the explicit public builtin coordinate map.
    node_name = "ext_cw_$(component_id)_signal"
    index = findfirst(==(node_name), model.node_names)
    isnothing(index) && error("Reduction coordinate $(component_id).$(coordinate) is absent from compiled C/K model.")
    return index
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
    return transpose(basis) * model.capacitance * basis, transpose(basis) * model.inverse_inductance * basis, indices
end

function _cw_direct_cared_outputs(compiled, objective, reduction)
    model = SuperconductingCircuitsCore.extract_linear_nodal_model(compiled)
    outputs = _cw_dict(get(objective, "cared_outputs", nothing), "objective.cared_outputs")
    kinds = [_cw_string(get(_cw_dict(spec, "cared output"), "kind", nothing), "cared output kind") for spec in values(outputs)]
    uses_schur = any(==("schur_dynamic_stiffness_abs"), kinds)
    uses_closed = any(==("closed_mode_frequency_hz"), kinds)
    uses_schur && uses_closed && error("A direct request cannot mix closed-mode and explicit Schur cared-output kinds.")
    if uses_schur
        all(==("schur_dynamic_stiffness_abs"), kinds) || error("Unsupported direct cared-output kind.")
        capacitance, inverse_inductance, terminals = _cw_reduction_model(model, reduction)
        result = Dict{String,Float64}()
        for name in sort!(collect(keys(outputs)))
            spec = _cw_dict(outputs[name], "cared output $(name)")
            frequency = _cw_number(get(spec, "frequency_hz", nothing), "Schur cared output frequency_hz")
            frequency > 0 || error("Schur cared output frequency_hz must be positive.")
            schur = SuperconductingCircuitsCore.schur_dynamic_stiffness(
                capacitance, inverse_inductance, 2pi * frequency, terminals,
            )
            row = _cw_integer(get(spec, "row", nothing), "Schur cared output row")
            column = _cw_integer(get(spec, "column", nothing), "Schur cared output column")
            1 <= row <= size(schur.dynamic_stiffness, 1) && 1 <= column <= size(schur.dynamic_stiffness, 2) || error("Schur cared-output row/column is out of bounds.")
            result[name] = abs(schur.dynamic_stiffness[row, column])
        end
        return result
    end
    isnothing(reduction) || error("Closed-mode direct cared outputs do not accept an ignored ReductionSpec.")
    reduced = SuperconductingCircuitsCore.reduce_free_charge_coordinates(model)
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

function _cw_evaluate(request; overrides=Dict{String,Float64}(), candidate_parameters=Dict{String,Float64}())
    artifacts = _cw_validate_artifacts(request)
    compiled = _cw_build_plan(get(request, "plan", nothing); overrides=overrides)
    objective = _cw_dict(get(request, "objective", nothing), "request.objective")
    backend = _cw_string(get(request, "backend", nothing), "request.backend")
    backend == "hb" && !isnothing(get(request, "reduction", nothing)) && error(
        "HB V1 has no registered ReductionSpec executor; refusing to ignore a declared reduction."
    )
    outputs = backend == "hb" ? _cw_cared_outputs(compiled, objective) :
        backend == "direct" ? _cw_direct_cared_outputs(compiled, objective, get(request, "reduction", nothing)) : error("Unsupported backend $(backend).")
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
        "compiled_netlist_rows" => length(compiled.netlist),
    )
end

function _cw_expected_candidate_error(exception)
    return exception isa _CWCandidateNotEvaluable || exception isa SuperconductingCircuitsCore.HBSolverNumericalError ||
        exception isa SingularException || exception isa PosDefException ||
        exception isa ZeroPivotException || exception isa RankDeficientException ||
        exception isa LAPACKException
end

function _cw_candidate_key(latent)
    return _cw_fingerprint([Float64(value) for value in latent])
end

function _cw_load_ledger(path, fingerprint)
    if !isfile(path)
        return Dict{String,Any}("schema" => "circuit-workbench-optimization-ledger.v1", "request_fingerprint_sha256" => fingerprint, "entries" => Any[])
    end
    ledger = _cw_dict(JSON3.read(read(path, String)), "optimization ledger")
    get(ledger, "schema", nothing) == "circuit-workbench-optimization-ledger.v1" || error("Optimization ledger schema mismatch.")
    get(ledger, "request_fingerprint_sha256", nothing) == fingerprint || error("Optimization ledger belongs to a different sealed request fingerprint.")
    ledger["entries"] = _cw_array(get(ledger, "entries", nothing), "optimization ledger entries")
    return ledger
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
        _cw_evaluate(request; overrides=overrides, candidate_parameters=_cw_requested_candidate_parameters(variables, latent))
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
                )
                push!(entries, entry)
                cache[key] = entry
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

function _cw_receipt(request, status, request_path; result=nothing, failure=nothing)
    plan = _cw_dict(get(request, "plan", nothing), "request.plan")
    runtime = _cw_dict(get(request, "runtime", nothing), "request.runtime")
    output_sha = isnothing(result) ? nothing : _cw_fingerprint(result)
    ledger_sha = isnothing(result) ? nothing : get(result, "ledger_sha256", nothing)
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
        "lifecycle_state" => "CONVERGING",
        "data_classification" => "project-internal",
        "promotion_eligible" => false,
        "artifact_bindings" => get(request, "artifacts", Dict{String,Any}()),
        "output_sha256" => output_sha,
        "ledger_sha256" => ledger_sha,
        "nonclaims" => [
            "no artifact bytes are copied into this receipt",
            "project-internal runtime evidence only",
            "no promotion or publication claim",
        ],
        "result" => result,
        "failure" => failure,
    )
    receipt["canonical_sha256"] = _cw_fingerprint(receipt)
    return receipt
end

function execute_circuit_workbench_action(request_path::AbstractString, receipt_path::AbstractString)
    basename(request_path) == "circuit-workbench-run-request.v1.json" || error("Request must use the standard durable request filename.")
    basename(receipt_path) == "circuit-workbench-run-receipt.v1.json" || error("Receipt must use the standard durable receipt filename.")
    dirname(abspath(request_path)) == dirname(abspath(receipt_path)) || error("Request and receipt must share one run directory.")
    request = _cw_dict(JSON3.read(read(request_path, String)), "request")
    get(request, "schema", nothing) == _CW_REQUEST_SCHEMA || error("Request schema is not $(_CW_REQUEST_SCHEMA).")
    action = _cw_string(get(request, "action", nothing), "request.action")
    action in ("evaluate", "optimize") || error("Unsupported Circuit Workbench action $(action).")
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
    result = action == "evaluate" ? _cw_evaluate(request) : _cw_optimize(
        request, joinpath(dirname(receipt_path), "circuit-workbench-optimization-ledger.v1.json"),
    )
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
end
