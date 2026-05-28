Base.@kwdef struct LumpedResonator <: AbstractCircuitComponent
    id::String = "res"
    capacitance::Float64
    inductance::Float64
end

component_id(component::LumpedResonator) = component.id
component_pins(::LumpedResonator) = [:signal]
component_lines(::LumpedResonator) = Symbol[]
default_line(::LumpedResonator) = nothing

function component_parameters(component::LumpedResonator)
    return [
        ParameterMetadata(
            name=:capacitance,
            role=NumericParameter(),
            owner=component.id,
            targets=[:capacitance],
            sweep_name=:capacitance,
            units="F",
            assumptions=["changing capacitance does not change component topology"],
        ),
        ParameterMetadata(
            name=:inductance,
            role=NumericParameter(),
            owner=component.id,
            targets=[:inductance],
            sweep_name=:inductance,
            units="H",
            assumptions=["changing inductance does not change component topology"],
        ),
    ]
end
