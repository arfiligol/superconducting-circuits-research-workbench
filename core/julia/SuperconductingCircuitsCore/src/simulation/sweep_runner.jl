struct SweepAxis
    name::String
    values::Vector{Float64}

    function SweepAxis(name::AbstractString, values)
        name_value = String(name)
        value_vector = collect(Float64.(values))
        _require(!isempty(name_value), "SweepAxis name must not be empty.")
        _require(!isempty(value_vector), "SweepAxis values must not be empty.")
        return new(name_value, value_vector)
    end
end

struct SweepSpec
    axes::Vector{SweepAxis}

    function SweepSpec(axes)
        axis_vector = SweepAxis[axis for axis in axes]
        names = [axis.name for axis in axis_vector]
        _require(length(unique(names)) == length(names), "SweepSpec axis names must be unique.")
        return new(axis_vector)
    end
end

struct SweepPointResult
    point_index::Int
    parameters::Dict{String,Float64}
    success::Bool
    result::Any
    error_message::Union{Nothing,String}
end

struct SweepResult
    axes::Vector{SweepAxis}
    points::Vector{SweepPointResult}
end

function _sweep_parameter_points(sweep_spec::SweepSpec)
    if isempty(sweep_spec.axes)
        return [Dict{String,Float64}()]
    end

    points = Dict{String,Float64}[Dict{String,Float64}()]
    for axis in sweep_spec.axes
        expanded = Dict{String,Float64}[]
        for base_point in points
            for value in axis.values
                next_point = copy(base_point)
                next_point[axis.name] = value
                push!(expanded, next_point)
            end
        end
        points = expanded
    end
    return points
end

function _run_sweep_point(base_builder::Function, point_index::Int, parameters::Dict{String,Float64}, evaluator::Function)
    try
        built = base_builder(parameters)
        result = evaluator(built, parameters)
        return SweepPointResult(point_index, parameters, true, result, nothing)
    catch err
        return SweepPointResult(point_index, parameters, false, nothing, sprint(showerror, err))
    end
end

"""
    run_design_sweep(base_builder, sweep_spec; threaded=true, evaluator=identity)

Run a Cartesian product parameter sweep. `base_builder(parameters)` may return a
finalized netlist, or any named tuple/object that the optional `evaluator`
understands. Failures are captured per point instead of aborting the full sweep.
"""
function run_design_sweep(
    base_builder::Function,
    sweep_spec::SweepSpec;
    threaded::Bool=true,
    evaluator::Function=(built, _parameters) -> built,
)
    points = _sweep_parameter_points(sweep_spec)
    results = Vector{SweepPointResult}(undef, length(points))

    if threaded && Threads.nthreads() > 1 && length(points) > 1
        Threads.@threads for idx in eachindex(points)
            results[idx] = _run_sweep_point(base_builder, idx, points[idx], evaluator)
        end
    else
        for idx in eachindex(points)
            results[idx] = _run_sweep_point(base_builder, idx, points[idx], evaluator)
        end
    end

    return SweepResult(sweep_spec.axes, results)
end
