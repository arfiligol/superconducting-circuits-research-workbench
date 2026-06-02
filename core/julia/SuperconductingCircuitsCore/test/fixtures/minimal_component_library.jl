module MinimalComponentLibrary

using SuperconductingCircuitsCore

import SuperconductingCircuitsCore:
    component_id,
    component_pins,
    component_lines,
    default_line,
    component_parameters

struct TestLineComponent <: AbstractCircuitComponent
    id::String
    line_names::Vector{Symbol}
    default::Union{Nothing,Symbol}
end

struct TestGroundedComponent <: AbstractCircuitComponent
    id::String
end

component_id(component::TestLineComponent) = component.id
component_pins(::TestLineComponent) = [:left, :right, :feed]
component_lines(component::TestLineComponent) = component.line_names
default_line(component::TestLineComponent) = component.default
component_parameters(component::TestLineComponent) = [
    ParameterMetadata(
        name=:line_length_m,
        role=StructuralParameter(),
        owner=component.id,
        targets=[:line_length],
        sweep_name=:line_length_m,
        units="m",
        assumptions=["line length may change segmentation"],
    ),
]

component_id(component::TestGroundedComponent) = component.id
component_pins(::TestGroundedComponent) = [:signal]
component_lines(::TestGroundedComponent) = Symbol[]
default_line(::TestGroundedComponent) = nothing
component_parameters(component::TestGroundedComponent) = [
    ParameterMetadata(
        name=:capacitance,
        role=NumericParameter(),
        owner=component.id,
        targets=[:capacitance],
        sweep_name=:capacitance,
        units="F",
    ),
]

end
