module SuperconductingCircuitsRunner

using Dates
using HTTP
using JSON3
using SHA
import SuperconductingCircuitsCore
using UUIDs

export RunnerClaim
export execute_task
export manifest_sha256
export parse_task_claim
export run_polling_runner
export write_trace_zarr_package

include("staging/zarr_writer.jl")

const _SUPPORTED_FREQUENCY_SWEEP_DEFINITION_IDS = Set([
    "c8f08463-bf18-4f8e-a5d5-735f3d7b0d6e",
    "runner_mvp_minimal_core_plan",
])

const _MVP_SHUNT_CAPACITANCE_F = 60.0e-15
const _MVP_PORT_RESISTANCE_OHM = 50.0

struct _RunnerMvpOnePortComponent <: SuperconductingCircuitsCore.AbstractCircuitComponent
    id::String
    capacitance_f::Float64
end

SuperconductingCircuitsCore.component_id(component::_RunnerMvpOnePortComponent) = component.id
SuperconductingCircuitsCore.component_pins(::_RunnerMvpOnePortComponent) = [:signal]
SuperconductingCircuitsCore.component_lines(::_RunnerMvpOnePortComponent) = Symbol[]
SuperconductingCircuitsCore.default_line(::_RunnerMvpOnePortComponent) = nothing
SuperconductingCircuitsCore.component_parameters(component::_RunnerMvpOnePortComponent) = [
    SuperconductingCircuitsCore.ParameterMetadata(
        name=:mvp_shunt_capacitance_f,
        role=SuperconductingCircuitsCore.NumericParameter(),
        owner=component.id,
        targets=[:shunt_capacitance],
        sweep_name=:mvp_shunt_capacitance_f,
        units="F",
        assumptions=["MVP Runner adapter component-library parameter; topology is fixed."],
    ),
]

struct RunnerClaim
    task_id::String
    task_kind::String
    input::Dict{String,Any}
    dataset_id::Union{String,Nothing}
    design_id::Union{String,Nothing}
    task_dir::String
    result_zarr::String
    manifest::String
end

function parse_task_claim(payload)::Union{RunnerClaim,Nothing}
    root = _json_dict(payload)
    task = get(root, "task", nothing)
    staging = get(root, "staging", nothing)
    if isnothing(task) || isnothing(staging)
        return nothing
    end
    task = _json_dict(task)
    staging = _json_dict(staging)
    output_target = get(task, "output_target", Dict{String,Any}())
    return RunnerClaim(
        string(task["task_id"]),
        string(task["task_kind"]),
        _json_dict(get(task, "input", Dict{String,Any}())),
        _optional_string(output_target, "dataset_id"),
        _optional_string(output_target, "design_id"),
        string(staging["task_dir"]),
        string(staging["result_zarr"]),
        string(staging["manifest"]),
    )
end

function run_polling_runner(;
    backend_url::AbstractString="http://127.0.0.1:8000",
    runner_id::AbstractString="runner_local_001",
    poll_interval::Real=2,
    once::Bool=false,
)
    normalized_url = rstrip(string(backend_url), '/')
    while true
        claim = claim_task(normalized_url)
        if isnothing(claim)
            if once
                return nothing
            end
            sleep(poll_interval)
            continue
        end
        try
            report_progress(normalized_url, claim.task_id; percent_complete=10, summary="Runner started.")
            manifest_path = execute_task(claim)
            report_progress(normalized_url, claim.task_id; percent_complete=90, summary="Runner result staged.")
            report_complete(normalized_url, claim, runner_id, manifest_path)
        catch err
            report_fail(normalized_url, claim.task_id, runner_id, err)
        end
        if once
            return claim
        end
    end
end

function claim_task(backend_url::AbstractString)::Union{RunnerClaim,Nothing}
    response = HTTP.post("$(backend_url)/runner/v1/tasks/claim"; headers=_json_headers())
    payload = JSON3.read(String(response.body))
    if !Bool(payload.ok)
        error("runner task claim failed: $(String(response.body))")
    end
    return parse_task_claim(payload.data)
end

function report_progress(
    backend_url::AbstractString,
    task_id::AbstractString;
    percent_complete::Integer,
    summary::AbstractString,
)
    HTTP.post(
        "$(backend_url)/runner/v1/tasks/$(task_id)/progress";
        headers=_json_headers(),
        body=JSON3.write(Dict(
            "percent_complete" => percent_complete,
            "summary" => string(summary),
        )),
    )
    return nothing
end

function report_complete(
    backend_url::AbstractString,
    claim::RunnerClaim,
    runner_id::AbstractString,
    manifest_path::AbstractString,
)
    body = Dict{String,Any}(
        "runner_id" => string(runner_id),
        "manifest_path" => _staging_relative_manifest_path(claim, manifest_path),
        "manifest_sha256" => manifest_sha256(manifest_path),
    )
    response = HTTP.post(
        "$(backend_url)/runner/v1/tasks/$(claim.task_id)/complete";
        headers=_json_headers(),
        body=JSON3.write(body),
    )
    payload = JSON3.read(String(response.body))
    if !Bool(payload.ok)
        error("runner completion failed: $(String(response.body))")
    end
    return payload
end

function report_fail(
    backend_url::AbstractString,
    task_id::AbstractString,
    runner_id::AbstractString,
    err,
)
    HTTP.post(
        "$(backend_url)/runner/v1/tasks/$(task_id)/fail";
        headers=_json_headers(),
        body=JSON3.write(Dict(
            "runner_id" => string(runner_id),
            "error_type" => string(typeof(err)),
            "message" => sprint(showerror, err),
        )),
    )
    return nothing
end

function execute_task(claim::RunnerClaim)::String
    if claim.task_kind == "julia_simulation_parameter_sweep"
        return execute_simulation_parameter_sweep(claim)
    elseif claim.task_kind == "julia_simulation_frequency_sweep"
        return execute_simulation_frequency_sweep(claim)
    elseif startswith(claim.task_kind, "julia_analysis_")
        return execute_analysis_task(claim)
    elseif startswith(claim.task_kind, "julia_postprocess_")
        return execute_postprocess_task(claim)
    end
    error("Unsupported Julia Runner task kind: $(claim.task_kind)")
end

function execute_simulation_parameter_sweep(claim::RunnerClaim)::String
    error("julia_simulation_parameter_sweep is not implemented yet. Refusing to write fixture output.")
end

function execute_simulation_frequency_sweep(claim::RunnerClaim)::String
    setup = _required_simulation_setup(claim)
    frequencies_hz = _frequency_sweep_hz(setup)
    _require_solver_family(setup, "josephson_circuits")
    source_config = _source_config(setup)
    pump_frequencies_hz = _pump_frequencies_hz(setup, frequencies_hz)
    port_indices = _source_port_indices(setup)
    definition_id = _definition_id(claim)
    definition_id in _SUPPORTED_FREQUENCY_SWEEP_DEFINITION_IDS || error(
        "Unsupported definition_id/design path for julia_simulation_frequency_sweep: $(definition_id). " *
        "No Runner frequency-sweep plan builder is registered for this definition.",
    )

    compiled = try
        plan = _build_mvp_frequency_sweep_plan(definition_id, setup)
        authoring_report = SuperconductingCircuitsCore.validate_authoring(plan)
        if SuperconductingCircuitsCore.has_errors(authoring_report)
            error("CircuitPlan authoring validation failed: $(_validation_report_message(authoring_report))")
        end
        SuperconductingCircuitsCore.compile_to_josephson(plan)
    catch err
        error(
            "Julia Core compiler failed for definition_id $(definition_id): $(sprint(showerror, err)). " *
            "Refusing to write fixture output.",
        )
    end
    if isempty(compiled.netlist)
        error(
            "Julia Core compile_to_josephson returned an empty netlist for definition_id $(definition_id). " *
            "Real frequency sweep execution is blocked until Julia Core compiler lowering emits target rows. " *
            "Refusing to write fixture output.",
        )
    end

    result = try
        SuperconductingCircuitsCore.run_frequency_sweep(
            compiled.netlist,
            compiled.component_values,
            frequencies_hz;
            sources=source_config,
            pump_frequencies_hz=pump_frequencies_hz,
            port_indices=port_indices,
        )
    catch err
        error(
            "Julia Core simulation failed for definition_id $(definition_id): $(sprint(showerror, err)). " *
            "Refusing to write fixture output.",
        )
    end
    traces = try
        _trace_zarr_payloads(result, frequencies_hz)
    catch err
        error(
            "Trace extraction failed for definition_id $(definition_id): $(sprint(showerror, err)). " *
            "Refusing to write fixture output.",
        )
    end
    isempty(traces) && error("Simulation completed but produced no S-parameter traces. Refusing to write fixture output.")

    return write_trace_zarr_package(
        claim.task_dir;
        task_id=claim.task_id,
        axes=[
            Dict{String,Any}(
                "name" => "frequency",
                "unit" => "Hz",
                "path" => "/axes/frequency",
                "values" => frequencies_hz,
            ),
        ],
        traces=traces,
        manifest_metadata=Dict{String,Any}(
            "log_message" => "SuperconductingCircuitsRunner executed julia_simulation_frequency_sweep at $(_timestamp_now()).\n",
            "sweep" => Dict{String,Any}(
                "total_points" => length(frequencies_hz),
                "success_points" => length(frequencies_hz),
                "failed_points" => 0,
                "failed" => Any[],
            ),
        ),
    )
end

function execute_analysis_task(claim::RunnerClaim)::String
    error("$(claim.task_kind) is not implemented yet. Refusing to write fixture output.")
end

function execute_postprocess_task(claim::RunnerClaim)::String
    error("$(claim.task_kind) is not implemented yet. Refusing to write fixture output.")
end

function manifest_sha256(path::AbstractString)::String
    return bytes2hex(sha256(read(path)))
end

function _staging_relative_manifest_path(
    claim::RunnerClaim,
    manifest_path::AbstractString,
)::String
    staging_root = dirname(dirname(abspath(claim.task_dir)))
    return relpath(abspath(manifest_path), staging_root)
end

function _optional_string(payload::AbstractDict, key::AbstractString)::Union{String,Nothing}
    value = get(payload, key, nothing)
    return isnothing(value) ? nothing : string(value)
end

function _json_headers()
    return ["Content-Type" => "application/json"]
end

function _json_dict(payload)::Dict{String,Any}
    if payload isa AbstractDict
        return Dict{String,Any}(string(key) => _json_value(value) for (key, value) in pairs(payload))
    end
    return Dict{String,Any}()
end

function _json_value(value)
    if value isa AbstractDict
        return _json_dict(value)
    elseif value isa AbstractVector
        return Any[_json_value(item) for item in value]
    elseif isnothing(value)
        return nothing
    else
        return value
    end
end

function _timestamp_now()::String
    return Dates.format(now(UTC), dateformat"yyyy-mm-ddTHH:MM:SSZ")
end

function _required_simulation_setup(claim::RunnerClaim)::Dict{String,Any}
    setup = get(claim.input, "simulation_setup", nothing)
    setup isa AbstractDict || error("Missing simulation_setup for julia_simulation_frequency_sweep.")
    return _json_dict(setup)
end

function _definition_id(claim::RunnerClaim)::String
    for key in ("definition_id", "circuit_definition_id")
        value = get(claim.input, key, nothing)
        if !isnothing(value) && !isempty(string(value))
            return string(value)
        end
    end
    if !isnothing(claim.design_id) && !isempty(claim.design_id)
        return claim.design_id
    end
    error("Missing definition_id/design path for julia_simulation_frequency_sweep.")
end

function _frequency_sweep_hz(setup::AbstractDict)::Vector{Float64}
    sweep = _required_dict(setup, "frequency_sweep", "simulation_setup.frequency_sweep")
    start_ghz = _required_number(sweep, "start_ghz", "simulation_setup.frequency_sweep.start_ghz")
    stop_ghz = _required_number(sweep, "stop_ghz", "simulation_setup.frequency_sweep.stop_ghz")
    point_count = _required_int(sweep, "point_count", "simulation_setup.frequency_sweep.point_count")
    point_count > 0 || error("simulation_setup.frequency_sweep.point_count must be positive.")
    stop_ghz >= start_ghz || error("simulation_setup.frequency_sweep.stop_ghz must be greater than or equal to start_ghz.")
    spacing = lowercase(string(get(sweep, "spacing", "linear")))

    if spacing == "linear"
        return collect(range(start_ghz * 1.0e9, stop_ghz * 1.0e9; length=point_count))
    elseif spacing == "log"
        start_ghz > 0 || error("simulation_setup.frequency_sweep.start_ghz must be positive for log spacing.")
        stop_ghz > 0 || error("simulation_setup.frequency_sweep.stop_ghz must be positive for log spacing.")
        return collect(exp.(range(log(start_ghz * 1.0e9), log(stop_ghz * 1.0e9); length=point_count)))
    end
    error("Unsupported frequency sweep spacing: $(spacing). Supported spacing values: linear, log.")
end

function _require_solver_family(setup::AbstractDict, expected::AbstractString)
    solver = _required_dict(setup, "solver", "simulation_setup.solver")
    family = string(get(solver, "solver_family", ""))
    !isempty(family) || error("Missing simulation_setup.solver.solver_family.")
    family == expected || error("Unsupported solver family: $(family). Supported solver family: $(expected).")
    return family
end

function _build_mvp_frequency_sweep_plan(definition_id::AbstractString, setup::AbstractDict)
    component = _RunnerMvpOnePortComponent("mvp_one_port_shunt", _MVP_SHUNT_CAPACITANCE_F)
    plan = SuperconductingCircuitsCore.CircuitPlan(;
        id="runner_frequency_sweep_$(definition_id)",
        metadata=Dict{Symbol,Any}(
            :runner_adapter => :frequency_sweep_mvp,
            :definition_id => string(definition_id),
            :external_ports => [
                (name="port_1", index=1, resistance_ohm=_MVP_PORT_RESISTANCE_OHM),
            ],
        ),
    )
    registered = SuperconductingCircuitsCore.register_component!(plan, component)
    signal = SuperconductingCircuitsCore.pin(registered, :signal)
    port = SuperconductingCircuitsCore.external_node("port_1")
    SuperconductingCircuitsCore.connect!(plan, signal, port)
    SuperconductingCircuitsCore.shunt_capacitor!(
        plan;
        id="runner_mvp_shunt_capacitor",
        at=signal,
        capacitance=component.capacitance_f,
        parameters=SuperconductingCircuitsCore.ParameterMetadata[
            SuperconductingCircuitsCore.ParameterMetadata(
                name=:runner_mvp_shunt_capacitance_f,
                role=SuperconductingCircuitsCore.NumericParameter(),
                owner=component.id,
                targets=[:runner_mvp_shunt_capacitor],
                sweep_name=:runner_mvp_shunt_capacitance_f,
                units="F",
                assumptions=["MVP fixed-topology one-port shunt capacitance."],
            ),
        ],
    )
    SuperconductingCircuitsCore.register_parameter!(
        plan,
        SuperconductingCircuitsCore.ParameterMetadata(
            name=:frequency_range_hz,
            role=SuperconductingCircuitsCore.DriveParameter(),
            owner="runner_frequency_sweep_adapter",
            targets=[:frequency_sweep],
            sweep_name=:frequency,
            units="Hz",
            assumptions=["Runner adapter parameter; does not alter CircuitPlan topology."],
        ),
    )
    return plan
end

function _validation_report_message(report)
    return join([string(issue.code, ": ", issue.message) for issue in SuperconductingCircuitsCore.errors(report)], "; ")
end

function _source_config(setup::AbstractDict)
    sources = _source_specs(setup)
    configs = Any[]
    for source in sources
        kind = string(get(source, "kind", ""))
        kind == "port_drive" || error("Unsupported source kind: $(kind). Supported source kind: port_drive.")
        port = _source_target_port(source)
        current = Float64(get(source, "current", 0.0))
        push!(configs, (mode=(1,), port=port, current=current))
    end
    return configs
end

function _pump_frequencies_hz(setup::AbstractDict, frequencies_hz::Vector{Float64})
    sources = _source_specs(setup)
    pump = Float64[]
    for source in sources
        frequency_ghz = get(source, "frequency_ghz", nothing)
        if !isnothing(frequency_ghz)
            push!(pump, Float64(frequency_ghz) * 1.0e9)
        end
    end
    return isempty(pump) ? (first(frequencies_hz),) : Tuple(pump)
end

function _source_port_indices(setup::AbstractDict)::Vector{Int}
    return sort!(unique([_source_target_port(source) for source in _source_specs(setup)]))
end

function _source_specs(setup::AbstractDict)::Vector{Dict{String,Any}}
    raw_sources = get(setup, "sources", nothing)
    raw_sources isa AbstractVector && !isempty(raw_sources) ||
        error("Missing source config: simulation_setup.sources must contain at least one source.")
    return [_json_dict(source) for source in raw_sources]
end

function _source_target_port(source::AbstractDict)::Int
    target = string(get(source, "target", ""))
    match_result = match(r"^port_(\d+)$", target)
    isnothing(match_result) && error("Unsupported source target: $(target). Expected target format port_N.")
    return parse(Int, match_result.captures[1])
end

function _trace_zarr_payloads(result, frequencies_hz::Vector{Float64})
    zero_mode_s = get(result.traces, :zero_mode_s, Dict{String,Vector{ComplexF64}}())
    traces = Any[]
    for trace_key in sort(collect(keys(zero_mode_s)))
        values = ComplexF64.(zero_mode_s[trace_key])
        length(values) == length(frequencies_hz) ||
            error("Trace $(trace_key) length does not match the frequency axis length.")
        push!(
            traces,
            Dict{String,Any}(
                "trace_key" => trace_key,
                "family" => "s_matrix",
                "parameter" => trace_key,
                "representation" => "complex",
                "real" => real.(values),
                "imag" => imag.(values),
                "axes" => ["frequency"],
                "chunk_shape" => [length(values)],
            ),
        )
    end
    return traces
end

function _required_dict(payload::AbstractDict, key::AbstractString, field_name::AbstractString)
    value = get(payload, key, nothing)
    value isa AbstractDict || error("$(field_name) must be an object.")
    return _json_dict(value)
end

function _required_number(payload::AbstractDict, key::AbstractString, field_name::AbstractString)::Float64
    value = get(payload, key, nothing)
    value isa Real || error("$(field_name) must be a number.")
    return Float64(value)
end

function _required_int(payload::AbstractDict, key::AbstractString, field_name::AbstractString)::Int
    value = get(payload, key, nothing)
    if value isa Integer
        return Int(value)
    elseif value isa Real && isinteger(value)
        return Int(value)
    end
    error("$(field_name) must be an integer.")
end

end
