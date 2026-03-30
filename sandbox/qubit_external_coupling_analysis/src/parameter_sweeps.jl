abstract type AbstractParameterSweepAxis end

Base.@kwdef struct ScalarParameterSweepAxis <: AbstractParameterSweepAxis
    parameter::Symbol
    label::String
    unit::String
    values::Vector{Float64}
    display_divisor::Float64 = 1.0
end

Base.@kwdef struct DifferenceScaleSweepAxis <: AbstractParameterSweepAxis
    positive_parameter::Symbol
    negative_parameter::Symbol
    label::String
    unit::String
    average_value::Float64
    base_difference_value::Float64
    scale_values::Vector{Float64}
end

Base.@kwdef struct ParameterSetSweepAxis <: AbstractParameterSweepAxis
    label::String
    unit::String
    value_labels::Vector{String}
    display_values::Vector{Float64}
    assignments::Vector{Dict{Symbol,Float64}}
end

axis_label(axis::AbstractParameterSweepAxis) = axis.label
axis_unit(axis::AbstractParameterSweepAxis) = axis.unit
axis_length(axis::ScalarParameterSweepAxis) = length(axis.values)
axis_length(axis::DifferenceScaleSweepAxis) = length(axis.scale_values)
axis_length(axis::ParameterSetSweepAxis) = length(axis.assignments)

function axis_point(axis::ScalarParameterSweepAxis, index::Int)
    value = axis.values[index]
    display_value = value / axis.display_divisor
    return (
        assignments=Dict(axis.parameter => value),
        display_value=display_value,
        value_label=@sprintf("%.6g", display_value),
    )
end

function axis_point(axis::DifferenceScaleSweepAxis, index::Int)
    scale_value = axis.scale_values[index]
    difference = axis.base_difference_value * scale_value
    positive_value = axis.average_value + (difference / 2)
    negative_value = axis.average_value - (difference / 2)
    return (
        assignments=Dict(
            axis.positive_parameter => positive_value,
            axis.negative_parameter => negative_value,
        ),
        display_value=scale_value,
        value_label=@sprintf("%.6g", scale_value),
    )
end

function axis_point(axis::ParameterSetSweepAxis, index::Int)
    return (
        assignments=axis.assignments[index],
        display_value=axis.display_values[index],
        value_label=axis.value_labels[index],
    )
end

function describe_sweep_point(axes::Vector{<:AbstractParameterSweepAxis}, coordinates::Tuple)
    if isempty(axes)
        return ""
    end
    parts = String[]
    for (axis_index, axis) in enumerate(axes)
        point = axis_point(axis, coordinates[axis_index] + 1)
        push!(parts, "$(axis_label(axis))=$(point.value_label) $(axis_unit(axis))")
    end
    return join(parts, " | ")
end

function sweep_point_count(axes::Vector{<:AbstractParameterSweepAxis})
    total = 1
    for axis in axes
        total *= max(axis_length(axis), 1)
    end
    return total
end

function decode_sweep_index(axes::Vector{<:AbstractParameterSweepAxis}, sweep_index::Int)
    if isempty(axes)
        return ()
    end
    remaining = sweep_index
    coordinates = zeros(Int, length(axes))
    for axis_index in length(axes):-1:1
        axis_size = max(axis_length(axes[axis_index]), 1)
        coordinates[axis_index] = remaining % axis_size
        remaining ÷= axis_size
    end
    return Tuple(coordinates)
end

function encode_sweep_index(axes::Vector{<:AbstractParameterSweepAxis}, coordinates::Tuple)
    if isempty(axes)
        return 0
    end
    encoded = 0
    for (axis_index, axis) in enumerate(axes)
        axis_size = max(axis_length(axis), 1)
        coordinate = axis_index <= length(coordinates) ? coordinates[axis_index] : 0
        coordinate = min(max(coordinate, 0), axis_size - 1)
        encoded = (encoded * axis_size) + coordinate
    end
    return encoded
end

function update_config_from_assignments(cfg::StudyConfig, assignments::Dict{Symbol,Float64})
    return updated_config(cfg; (key => value for (key, value) in assignments)...)
end

function evaluate_parameter_sweep_point(
    evaluator,
    base_cfg::StudyConfig,
    axes::Vector{<:AbstractParameterSweepAxis},
    sweep_index::Int,
)
    coordinates = decode_sweep_index(axes, sweep_index)
    cfg = base_cfg
    metadata = Dict{Symbol,Any}(
        :sweep_index => sweep_index,
        :axis_count => length(axes),
    )

    for (axis_index, axis) in enumerate(axes)
        point = axis_point(axis, coordinates[axis_index] + 1)
        cfg = update_config_from_assignments(cfg, point.assignments)
        metadata[Symbol("axis_$(axis_index)_label")] = axis_label(axis)
        metadata[Symbol("axis_$(axis_index)_unit")] = axis_unit(axis)
        metadata[Symbol("axis_$(axis_index)_coordinate")] = coordinates[axis_index]
        metadata[Symbol("axis_$(axis_index)_value")] = point.display_value
        metadata[Symbol("axis_$(axis_index)_value_label")] = point.value_label
    end

    result = evaluator(cfg, sweep_index, coordinates)
    for (key, value) in pairs(result)
        metadata[key] = value
    end

    return (; (key => metadata[key] for key in keys(metadata))...)
end

function persist_parameter_sweep_batch(batch_rows, persisted_csv_path; append::Bool)
    batch_df = DataFrame(batch_rows)
    CSV.write(persisted_csv_path, batch_df; append=append)
end

function run_parameter_sweep(
    evaluator,
    base_cfg::StudyConfig,
    axes::Vector{<:AbstractParameterSweepAxis};
    progress_label::AbstractString="Parameter sweep",
    progress_detail_builder::Union{Nothing,Function}=nothing,
    batch_size::Int=sweep_point_count(axes),
    persisted_csv_path::Union{Nothing,AbstractString}=nothing,
    use_threads::Bool=false,
    max_parallel_workers::Int=Base.Threads.nthreads(),
    return_dataframe::Bool=true,
)
    total_points = sweep_point_count(axes)
    effective_batch_size = max(batch_size, 1)
    collected_rows = return_dataframe && isnothing(persisted_csv_path) ? NamedTuple[] : nothing
    completed_points = Base.Threads.Atomic{Int}(0)
    requested_workers = max(max_parallel_workers, 1)
    worker_count = min(requested_workers, Base.Threads.nthreads())

    if !isnothing(persisted_csv_path)
        mkpath(dirname(persisted_csv_path))
        if isfile(persisted_csv_path)
            rm(persisted_csv_path; force=true)
        end
    end

    for batch_start in 0:effective_batch_size:(total_points - 1)
        batch_stop = min(batch_start + effective_batch_size - 1, total_points - 1)
        batch_indices = collect(batch_start:batch_stop)
        batch_rows = Vector{NamedTuple}(undef, length(batch_indices))

        if use_threads && worker_count > 1 && length(batch_indices) > 1
            work_channel = Channel{Tuple{Int,Int}}(length(batch_indices))
            for (local_index, sweep_index) in enumerate(batch_indices)
                put!(work_channel, (local_index, sweep_index))
            end
            close(work_channel)

            Base.Threads.foreach(work_channel; ntasks=worker_count) do (local_index, sweep_index)
                row = evaluate_parameter_sweep_point(evaluator, base_cfg, axes, sweep_index)
                batch_rows[local_index] = row
                current = Base.Threads.atomic_add!(completed_points, 1) + 1
                coordinates = decode_sweep_index(axes, sweep_index)
                detail = isnothing(progress_detail_builder) ?
                    describe_sweep_point(axes, coordinates) :
                    progress_detail_builder(row, axes, sweep_index, coordinates)
                print_progress_update(
                    progress_label,
                    current,
                    total_points;
                    detail=detail,
                )
            end
        else
            for (local_index, sweep_index) in enumerate(batch_indices)
                row = evaluate_parameter_sweep_point(evaluator, base_cfg, axes, sweep_index)
                batch_rows[local_index] = row
                current = Base.Threads.atomic_add!(completed_points, 1) + 1
                coordinates = decode_sweep_index(axes, sweep_index)
                detail = isnothing(progress_detail_builder) ?
                    describe_sweep_point(axes, coordinates) :
                    progress_detail_builder(row, axes, sweep_index, coordinates)
                print_progress_update(
                    progress_label,
                    current,
                    total_points;
                    detail=detail,
                )
            end
        end

        if !isnothing(persisted_csv_path)
            persist_parameter_sweep_batch(
                batch_rows,
                persisted_csv_path;
                append=(batch_start > 0),
            )
        end
        if !isnothing(collected_rows)
            append!(collected_rows, batch_rows)
        end
    end

    if !isnothing(persisted_csv_path)
        return return_dataframe ? CSV.read(persisted_csv_path, DataFrame) : DataFrame()
    end
    return DataFrame(collected_rows)
end
