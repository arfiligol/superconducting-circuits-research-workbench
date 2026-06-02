abstract type AbstractSweepAxis end

function _sweep_is_named_tuple_value(value)
    return nameof(typeof(value)) == Symbol("Named", "Tuple")
end

function _axis_values(values, label::AbstractString)
    collected = Any[value for value in values]
    !isempty(collected) || _validation_error("$(label) values must not be empty.")
    return collected
end

struct StructuralAxis <: AbstractSweepAxis
    values::Vector{Any}
    StructuralAxis(values) = new(_axis_values(values, "StructuralAxis"))
end

struct NumericAxis <: AbstractSweepAxis
    values::Vector{Any}
    NumericAxis(values) = new(_axis_values(values, "NumericAxis"))
end

struct DriveAxis <: AbstractSweepAxis
    values::Vector{Any}
    DriveAxis(values) = new(_axis_values(values, "DriveAxis"))
end

struct AnalysisAxis <: AbstractSweepAxis
    values::Vector{Any}
    AnalysisAxis(values) = new(_axis_values(values, "AnalysisAxis"))
end

struct SweepSpec
    axes::Dict{Symbol,AbstractSweepAxis}
    compile_policy::Any
    executor::Any
    acceleration_policy::Any
    classification_policy::Any
end

function _normalize_axes(axes)
    normalized = Dict{Symbol,AbstractSweepAxis}()
    if _sweep_is_named_tuple_value(axes)
        for name in keys(axes)
            axis = getfield(axes, name)
            axis isa AbstractSweepAxis || _validation_error("Sweep axis '$(name)' must be an AbstractSweepAxis.")
            normalized[Symbol(name)] = axis
        end
    elseif axes isa AbstractDict
        for (name, axis) in axes
            axis isa AbstractSweepAxis || _validation_error("Sweep axis '$(name)' must be an AbstractSweepAxis.")
            normalized[Symbol(name)] = axis
        end
    else
        _validation_error("SweepSpec axes must be a named tuple or dictionary.")
    end
    return normalized
end

function SweepSpec(;
    axes,
    compile_policy=CompileByTopologyKey(),
    executor=SerialExecutor(),
    acceleration_policy=NoAcceleration(),
    classification_policy=StrictSweepClassification(),
)
    return SweepSpec(
        _normalize_axes(axes),
        compile_policy,
        executor,
        acceleration_policy,
        classification_policy,
    )
end

function _axis_role(axis::AbstractSweepAxis)
    axis isa StructuralAxis && return StructuralParameter()
    axis isa NumericAxis && return NumericParameter()
    axis isa DriveAxis && return DriveParameter()
    axis isa AnalysisAxis && return AnalysisParameter()
    return AnalysisParameter()
end

function _axis_role_symbol(axis::AbstractSweepAxis)
    axis isa StructuralAxis && return :structural
    axis isa NumericAxis && return :numeric
    axis isa DriveAxis && return :drive
    axis isa AnalysisAxis && return :analysis
    return :unknown
end

function _axis_names(sweep::SweepSpec)
    return sort(collect(keys(sweep.axes)))
end

function _sweep_points(sweep::SweepSpec)
    names = _axis_names(sweep)
    isempty(names) && return [Dict{Symbol,Any}()]

    points = Dict{Symbol,Any}[Dict{Symbol,Any}()]
    for name in names
        expanded = Dict{Symbol,Any}[]
        for point in points
            for value in sweep.axes[name].values
                next = copy(point)
                next[name] = value
                push!(expanded, next)
            end
        end
        points = expanded
    end
    return points
end
