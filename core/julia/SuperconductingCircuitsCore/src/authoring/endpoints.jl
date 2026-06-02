abstract type AbstractCircuitEndpoint end
abstract type AbstractNodeEndpoint <: AbstractCircuitEndpoint end
abstract type AbstractLineSpanEndpoint <: AbstractCircuitEndpoint end
abstract type AbstractLoopEndpoint <: AbstractCircuitEndpoint end

struct PinEndpoint <: AbstractNodeEndpoint
    component_id::String
    pin::Symbol
end

struct ProbeEndpoint <: AbstractNodeEndpoint
    component_id::String
    probe::Symbol
end

struct AnchorRef
    component_id::String
    anchor::Symbol
end

struct LineRef
    component_id::String
    line::Symbol
end

struct LineTapEndpoint <: AbstractNodeEndpoint
    line_ref::LineRef
    at_m::Float64

    function LineTapEndpoint(line_ref::LineRef, at_m::Real)
        at_value = Float64(at_m)
        at_value >= 0 || _validation_error("LineTapEndpoint at_m must be non-negative.")
        return new(line_ref, at_value)
    end
end

struct LineSpanEndpoint <: AbstractLineSpanEndpoint
    line_ref::LineRef
    from_m::Float64
    to_m::Float64

    function LineSpanEndpoint(line_ref::LineRef, from_m::Real, to_m::Real)
        from_value = Float64(from_m)
        to_value = Float64(to_m)
        from_value >= 0 || _validation_error("LineSpanEndpoint from_m must be non-negative.")
        to_value > from_value || _validation_error("LineSpanEndpoint to_m must be greater than from_m.")
        return new(line_ref, from_value, to_value)
    end
end

struct GroundEndpoint <: AbstractNodeEndpoint end

struct ExternalNodeEndpoint <: AbstractNodeEndpoint
    name::String

    function ExternalNodeEndpoint(name::AbstractString)
        value = String(name)
        !isempty(value) || _validation_error("External node name must not be empty.")
        return new(value)
    end
end

struct LoopEndpoint <: AbstractLoopEndpoint
    component_id::String
    loop::Symbol
end

function pin(component::CircuitComponentInstance, name::Symbol)
    haskey(component.pins, name) ||
        _validation_error("Component '$(component.id)' does not expose pin '$(name)'.")
    return component.pins[name]
end

pin(component, name::Symbol) = PinEndpoint(_component_id_value(component), name)
pin(component_id::AbstractString, name::Symbol) = PinEndpoint(String(component_id), name)

function probe(component::CircuitComponentInstance, name::Symbol)
    haskey(component.probes, name) ||
        _validation_error("Component '$(component.id)' does not expose probe '$(name)'.")
    return component.probes[name]
end

probe(component, name::Symbol) = ProbeEndpoint(_component_id_value(component), name)
probe(component_id::AbstractString, name::Symbol) = ProbeEndpoint(String(component_id), name)

function anchor(component::CircuitComponentInstance, name::Symbol)
    haskey(component.anchors, name) ||
        _validation_error("Component '$(component.id)' does not expose anchor '$(name)'.")
    return component.anchors[name]
end

anchor(component, name::Symbol) = AnchorRef(_component_id_value(component), name)
anchor(component_id::AbstractString, name::Symbol) = AnchorRef(String(component_id), name)

function tap(component::CircuitComponentInstance, distance_from_head::Real)
    selected = _default_line_or_error(component, "tap")
    return line_tap(line_ref(component, selected); at_m=distance_from_head)
end

tap(component, distance_from_head::Real) = line_tap(component; at_m=distance_from_head)

function line_ref(component, line::Symbol)
    id = _component_id_value(component)
    if !(component isa AbstractString)
        lines = component_lines(component)
        line in lines || _validation_error("Component '$(id)' does not expose line '$(line)'.")
    end
    return LineRef(id, line)
end

line_ref(component_id::AbstractString, line::Symbol) = LineRef(String(component_id), line)

line_tap(ref::LineRef; at_m) = LineTapEndpoint(ref, at_m)

function line_tap(component; line=nothing, at_m)
    selected = isnothing(line) ? _default_line_or_error(component, "line_tap") : Symbol(line)
    return line_tap(line_ref(component, selected); at_m=at_m)
end

line_span(ref::LineRef; from_m, to_m) = LineSpanEndpoint(ref, from_m, to_m)

function line_span(component; line=nothing, from_m, to_m)
    selected = isnothing(line) ? _default_line_or_error(component, "line_span") : Symbol(line)
    return line_span(line_ref(component, selected); from_m=from_m, to_m=to_m)
end

ground() = GroundEndpoint()
external_node(name::AbstractString) = ExternalNodeEndpoint(name)
loop_endpoint(component, loop::Symbol) = LoopEndpoint(_component_id_value(component), loop)
loop_endpoint(component_id::AbstractString, loop::Symbol) = LoopEndpoint(String(component_id), loop)

function _default_line_or_error(component, caller::AbstractString)
    component isa AbstractString &&
        _validation_error("$(caller) shorthand requires a component object with an unambiguous default line.")
    selected = default_line(component)
    if isnothing(selected)
        id = _component_id_value(component)
        lines = component_lines(component)
        _validation_error(
            "$(caller) shorthand is ambiguous for component '$(id)'; use line=:name or line_ref(component, :name). Available lines: $(collect(lines)).",
        )
    end
    return selected
end
