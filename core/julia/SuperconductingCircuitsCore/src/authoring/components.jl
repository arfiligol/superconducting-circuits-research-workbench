abstract type AbstractCircuitComponent end

function component_id(component)
    throw(MethodError(component_id, (component,)))
end

function component_pins(component)
    throw(MethodError(component_pins, (component,)))
end

function component_lines(component)
    throw(MethodError(component_lines, (component,)))
end

function default_line(component)
    throw(MethodError(default_line, (component,)))
end

function component_parameters(component)
    throw(MethodError(component_parameters, (component,)))
end

function _component_id_value(component)
    component isa AbstractString && return String(component)
    return String(component_id(component))
end

