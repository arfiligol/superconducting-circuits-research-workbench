struct JosephsonCompiledCircuit
    netlist::Vector{Any}
    component_values::Dict{Symbol,Any}
    node_map::Dict{Any,String}
    component_map::Dict{String,Vector{Int}}
    line_tap_map::Dict{Any,Any}
    port_map::Dict{Symbol,Any}
    hb_intent_summary::Any
    source_slot_map::Dict{Symbol,Any}
    observable_request_map::Dict{Symbol,Any}
    hb_validation_summary::Any
    warnings::Vector{String}
    provenance::Dict{Symbol,Any}
    metadata::Dict{Symbol,Any}
end

function JosephsonCompiledCircuit(;
    netlist=Any[],
    component_values=Dict{Symbol,Any}(),
    node_map=Dict{Any,String}(),
    component_map=Dict{String,Vector{Int}}(),
    line_tap_map=Dict{Any,Any}(),
    port_map=Dict{Symbol,Any}(),
    hb_intent_summary=nothing,
    source_slot_map=Dict{Symbol,Any}(),
    observable_request_map=Dict{Symbol,Any}(),
    hb_validation_summary=nothing,
    warnings=String[],
    provenance=Dict{Symbol,Any}(),
    metadata=Dict{Symbol,Any}(),
)
    return JosephsonCompiledCircuit(
        Vector{Any}(netlist),
        Dict{Symbol,Any}(component_values),
        Dict{Any,String}(node_map),
        Dict{String,Vector{Int}}(component_map),
        Dict{Any,Any}(line_tap_map),
        Dict{Symbol,Any}(port_map),
        hb_intent_summary,
        Dict{Symbol,Any}(source_slot_map),
        Dict{Symbol,Any}(observable_request_map),
        hb_validation_summary,
        Vector{String}(warnings),
        Dict{Symbol,Any}(provenance),
        Dict{Symbol,Any}(metadata),
    )
end
