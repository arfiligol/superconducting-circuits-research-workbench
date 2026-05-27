module SuperconductingCircuitsRunner

using Dates
using HTTP
using JSON3
using SHA
using UUIDs

export RunnerClaim
export manifest_sha256
export parse_task_claim
export run_polling_runner
export write_smoke_result_package

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
            manifest_path = write_smoke_result_package(claim.task_dir; task_id=claim.task_id)
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
        "manifest_path" => relpath(manifest_path, pwd()),
        "manifest_sha256" => manifest_sha256(manifest_path),
        "output_target" => Dict{String,Any}(
            "dataset_id" => claim.dataset_id,
            "design_id" => claim.design_id,
        ),
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

function write_smoke_result_package(task_dir::AbstractString; task_id::AbstractString)
    task_root = abspath(task_dir)
    result_root = joinpath(task_root, "result.zarr")
    mkpath(joinpath(result_root, "axes"))
    mkpath(joinpath(result_root, "traces", "S11"))
    mkpath(joinpath(task_root, "logs"))

    _write_group(result_root)
    _write_group(joinpath(result_root, "axes"))
    _write_group(joinpath(result_root, "traces"))
    _write_group(joinpath(result_root, "traces", "S11"))

    frequency = Float64[4.0e9, 4.5e9, 5.0e9, 5.5e9, 6.0e9]
    real = Float64[1.0, 0.5, 0.0, -0.5, -1.0]
    imag = Float64[0.0, 0.1, 0.2, 0.1, 0.0]
    _write_zarr_array(joinpath(result_root, "axes", "frequency"), frequency, [5])
    _write_zarr_array(joinpath(result_root, "traces", "S11", "real"), real, [5])
    _write_zarr_array(joinpath(result_root, "traces", "S11", "imag"), imag, [5])

    log_path = joinpath(task_root, "logs", "runner.log")
    write(log_path, "SuperconductingCircuitsRunner smoke task completed at $(_timestamp_now()).\n")

    manifest = Dict{String,Any}(
        "schema_version" => "sc.runner.result.v1",
        "task_id" => string(task_id),
        "producer" => Dict{String,Any}(
            "runner" => "SuperconductingCircuitsRunner",
            "runner_version" => "0.1.0",
            "core_version" => "0.1.0",
            "julia_version" => string(VERSION),
        ),
        "array_store" => Dict{String,Any}(
            "format" => "zarr",
            "zarr_format" => 2,
            "uri" => "result.zarr",
        ),
        "sweep" => Dict{String,Any}(
            "total_points" => 1,
            "success_points" => 1,
            "failed_points" => 0,
            "failed" => Any[],
        ),
        "traces" => Any[
            Dict{String,Any}(
                "trace_key" => "S11",
                "family" => "s_matrix",
                "parameter" => "S11",
                "representation" => "complex",
                "real_path" => "/traces/S11/real",
                "imag_path" => "/traces/S11/imag",
                "shape" => Any[5],
                "chunk_shape" => Any[5],
                "dtype" => "float64",
                "axes" => Any[
                    Dict{String,Any}(
                        "name" => "frequency",
                        "unit" => "Hz",
                        "path" => "/axes/frequency",
                    ),
                ],
            ),
        ],
        "summary_tables" => Any[],
        "logs" => Any[
            Dict{String,Any}(
                "kind" => "runner_log",
                "path" => "logs/runner.log",
            ),
        ],
    )
    manifest_path = joinpath(task_root, "manifest.json")
    _write_manifest_atomic(manifest_path, manifest)
    return manifest_path
end

function manifest_sha256(path::AbstractString)::String
    return bytes2hex(sha256(read(path)))
end

function _write_group(path::AbstractString)
    mkpath(path)
    write(joinpath(path, ".zgroup"), JSON3.write(Dict("zarr_format" => 2)))
    return nothing
end

function _write_zarr_array(path::AbstractString, values::Vector{Float64}, shape::Vector{Int})
    mkpath(path)
    metadata = Dict{String,Any}(
        "zarr_format" => 2,
        "shape" => shape,
        "chunks" => shape,
        "dtype" => "<f8",
        "compressor" => nothing,
        "fill_value" => nothing,
        "order" => "C",
        "filters" => nothing,
    )
    write(joinpath(path, ".zarray"), JSON3.write(metadata))
    chunk_key = join(fill("0", length(shape)), ".")
    open(joinpath(path, chunk_key), "w") do io
        write(io, values)
        flush(io)
    end
    return nothing
end

function _write_manifest_atomic(path::AbstractString, manifest::Dict{String,Any})
    mkpath(dirname(path))
    tmp = path * ".tmp"
    open(tmp, "w") do io
        write(io, JSON3.write(manifest))
        flush(io)
    end
    mv(tmp, path; force=true)
    return path
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
