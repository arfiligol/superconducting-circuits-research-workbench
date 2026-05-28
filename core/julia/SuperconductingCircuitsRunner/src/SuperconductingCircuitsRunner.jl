module SuperconductingCircuitsRunner

using Dates
using HTTP
using JSON3
using SHA
using UUIDs

export RunnerClaim
export execute_task
export manifest_sha256
export parse_task_claim
export run_polling_runner
export write_trace_zarr_package

include("staging/zarr_writer.jl")

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
    error("julia_simulation_frequency_sweep is not implemented yet. Refusing to write fixture output.")
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

end
