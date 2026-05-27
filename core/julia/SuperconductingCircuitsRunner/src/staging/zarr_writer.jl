function write_trace_zarr_package(
    output_dir::AbstractString;
    task_id::AbstractString,
    traces::AbstractVector,
    axes::AbstractVector,
    manifest_metadata::AbstractDict=Dict{String,Any}(),
)::String
    task_root = abspath(output_dir)
    result_root = joinpath(task_root, "result.zarr")
    logs_dir = joinpath(task_root, "logs")

    mkpath(logs_dir)
    _write_group(result_root)
    _write_group(joinpath(result_root, "axes"))
    _write_group(joinpath(result_root, "traces"))

    axis_by_name = Dict{String,Dict{String,Any}}()
    for raw_axis in axes
        axis = _json_dict(raw_axis)
        axis_name = string(axis["name"])
        axis_path = string(get(axis, "path", "/axes/$(axis_name)"))
        values = _float64_array(axis["values"])
        _reject_unsafe_zarr_path(axis_path)
        _write_zarr_nd_array(
            joinpath(result_root, _zarr_relative_path(axis_path)),
            values;
            chunk_shape=[length(values)],
        )
        axis_by_name[axis_name] = Dict{String,Any}(
            "name" => axis_name,
            "unit" => string(get(axis, "unit", "")),
            "path" => axis_path,
            "length" => length(values),
        )
    end

    manifest_traces = Any[]
    for raw_trace in traces
        trace = _json_dict(raw_trace)
        trace_key = string(trace["trace_key"])
        real = _float64_array(trace["real"])
        imag = _float64_array(trace["imag"])
        size(real) == size(imag) || error("Trace $(trace_key) real/imag arrays must have identical shape.")

        shape = collect(Int, size(real))
        chunk_shape = collect(Int, get(trace, "chunk_shape", shape))
        length(shape) == length(chunk_shape) || error("Trace $(trace_key) chunk_shape rank must match shape.")
        all(>(0), chunk_shape) || error("Trace $(trace_key) chunk_shape values must be positive.")

        trace_group_path = "/traces/$(trace_key)"
        real_path = "$(trace_group_path)/real"
        imag_path = "$(trace_group_path)/imag"
        _write_group(joinpath(result_root, "traces", trace_key))
        _write_zarr_nd_array(
            joinpath(result_root, _zarr_relative_path(real_path)),
            real;
            chunk_shape=chunk_shape,
        )
        _write_zarr_nd_array(
            joinpath(result_root, _zarr_relative_path(imag_path)),
            imag;
            chunk_shape=chunk_shape,
        )

        trace_axes = _manifest_axes_for_trace(
            get(trace, "axes", Any[]),
            axis_by_name,
            shape,
            trace_key,
        )
        push!(manifest_traces, Dict{String,Any}(
            "trace_key" => trace_key,
            "family" => string(get(trace, "family", "s_matrix")),
            "parameter" => string(get(trace, "parameter", trace_key)),
            "representation" => string(get(trace, "representation", "complex")),
            "real_path" => real_path,
            "imag_path" => imag_path,
            "shape" => shape,
            "chunk_shape" => chunk_shape,
            "dtype" => "float64",
            "axes" => trace_axes,
        ))
    end

    log_path = joinpath(logs_dir, "runner.log")
    write(log_path, string(get(
        manifest_metadata,
        "log_message",
        "SuperconductingCircuitsRunner wrote a staged result at $(_timestamp_now()).\n",
    )))

    manifest = Dict{String,Any}(
        "schema_version" => "sc.runner.result.v1",
        "task_id" => string(task_id),
        "producer" => get(
            manifest_metadata,
            "producer",
            Dict{String,Any}(
                "runner" => "SuperconductingCircuitsRunner",
                "runner_version" => "0.1.0",
                "core_version" => "0.1.0",
                "julia_version" => string(VERSION),
            ),
        ),
        "array_store" => Dict{String,Any}(
            "format" => "zarr",
            "zarr_format" => 2,
            "uri" => "result.zarr",
        ),
        "sweep" => get(
            manifest_metadata,
            "sweep",
            Dict{String,Any}(
                "total_points" => 0,
                "success_points" => 0,
                "failed_points" => 0,
                "failed" => Any[],
            ),
        ),
        "traces" => manifest_traces,
        "summary_tables" => get(manifest_metadata, "summary_tables", Any[]),
        "logs" => Any[
            Dict{String,Any}(
                "kind" => "runner_log",
                "path" => "logs/runner.log",
            ),
        ],
    )
    return _write_manifest_atomic(joinpath(task_root, "manifest.json"), manifest)
end

function _manifest_axes_for_trace(raw_axes, axis_by_name, shape, trace_key)
    length(raw_axes) == length(shape) || error("Trace $(trace_key) axes must match trace rank.")
    manifest_axes = Any[]
    for (axis_index, raw_axis) in enumerate(raw_axes)
        axis_name = raw_axis isa AbstractDict ? string(raw_axis["name"]) : string(raw_axis)
        axis = get(axis_by_name, axis_name, nothing)
        isnothing(axis) && error("Trace $(trace_key) references unknown axis $(axis_name).")
        Int(axis["length"]) == shape[axis_index] || error(
            "Trace $(trace_key) axis $(axis_name) length does not match dimension $(axis_index).",
        )
        push!(manifest_axes, Dict{String,Any}(
            "name" => axis["name"],
            "unit" => axis["unit"],
            "path" => axis["path"],
        ))
    end
    return manifest_axes
end

function _write_group(path::AbstractString)
    mkpath(path)
    write(joinpath(path, ".zgroup"), JSON3.write(Dict("zarr_format" => 2)))
    return nothing
end

function _write_zarr_nd_array(
    path::AbstractString,
    values::Array{Float64};
    chunk_shape::Vector{Int},
)
    shape = collect(Int, size(values))
    length(shape) == length(chunk_shape) || error("chunk_shape rank must match array rank.")
    all(>(0), chunk_shape) || error("chunk_shape values must be positive.")

    mkpath(path)
    metadata = Dict{String,Any}(
        "zarr_format" => 2,
        "shape" => shape,
        "chunks" => chunk_shape,
        "dtype" => "<f8",
        "compressor" => nothing,
        "fill_value" => nothing,
        "order" => "F",
        "filters" => nothing,
    )
    write(joinpath(path, ".zarray"), JSON3.write(metadata))

    chunk_counts = [cld(shape[index], chunk_shape[index]) for index in eachindex(shape)]
    chunk_ranges = (0:(count - 1) for count in chunk_counts)
    for chunk_index in Iterators.product(chunk_ranges...)
        ranges = ntuple(length(shape)) do index
            start_index = chunk_index[index] * chunk_shape[index] + 1
            stop_index = min(start_index + chunk_shape[index] - 1, shape[index])
            start_index:stop_index
        end
        chunk = Array(values[ranges...])
        chunk_key = join(string.(chunk_index), ".")
        open(joinpath(path, chunk_key), "w") do io
            write(io, vec(chunk))
            flush(io)
        end
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

function _float64_array(values)::Array{Float64}
    if values isa AbstractArray
        return Array{Float64}(values)
    end
    error("Expected an array of Float64-compatible values.")
end

function _zarr_relative_path(path::AbstractString)::String
    return joinpath(split(lstrip(path, '/'), '/')...)
end

function _reject_unsafe_zarr_path(path::AbstractString)
    startswith(path, "/") || error("Zarr paths must be absolute inside the Zarr root.")
    parts = split(lstrip(path, '/'), '/')
    any(part -> part == ".." || isempty(part), parts) && error("Zarr path contains unsafe segments.")
    return nothing
end
