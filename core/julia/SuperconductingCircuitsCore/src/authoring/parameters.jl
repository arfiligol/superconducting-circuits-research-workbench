abstract type AbstractParameterRole end

struct StructuralParameter <: AbstractParameterRole end
struct NumericParameter <: AbstractParameterRole end
struct DriveParameter <: AbstractParameterRole end
struct AnalysisParameter <: AbstractParameterRole end

Base.@kwdef struct ParameterMetadata
    name::Symbol
    role::AbstractParameterRole
    owner::String
    targets::Vector{Symbol} = Symbol[]
    sweep_name::Symbol = name
    units::Union{Nothing,String} = nothing
    valid_domain::Any = nothing
    assumptions::Vector{String} = String[]
end

struct ParameterBinding
    name::Symbol
    value::Any
end

parameter_role(meta::ParameterMetadata) = meta.role
parameter_owner(meta::ParameterMetadata) = meta.owner

is_structural(meta::ParameterMetadata) = meta.role isa StructuralParameter
is_numeric(meta::ParameterMetadata) = meta.role isa NumericParameter
is_drive(meta::ParameterMetadata) = meta.role isa DriveParameter
is_analysis(meta::ParameterMetadata) = meta.role isa AnalysisParameter

function _role_strength(role::AbstractParameterRole)
    role isa StructuralParameter && return 4
    role isa NumericParameter && return 3
    role isa DriveParameter && return 3
    role isa AnalysisParameter && return 3
    return 0
end

function strongest_parameter_role(roles)
    role_vector = AbstractParameterRole[role for role in roles]
    isempty(role_vector) && return AnalysisParameter()
    strongest = role_vector[1]
    for role in role_vector[2:end]
        if _role_strength(role) > _role_strength(strongest)
            strongest = role
        end
    end
    return strongest
end

