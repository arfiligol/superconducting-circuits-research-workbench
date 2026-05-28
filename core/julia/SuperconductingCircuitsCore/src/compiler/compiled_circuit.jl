struct JosephsonCompiledCircuit
    netlist::Vector{Any}
    component_values::Dict{Symbol,Any}
    node_map::Dict{Any,String}
    component_map::Dict{String,Vector{Int}}
    line_tap_map::Dict{Any,Any}
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
        Vector{String}(warnings),
        Dict{Symbol,Any}(provenance),
        Dict{Symbol,Any}(metadata),
    )
end

