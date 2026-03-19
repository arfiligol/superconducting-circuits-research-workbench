"""
    add_readout_line!(
        circuit;
        prefix,
        left_node,
        right_node,
        line_spec,
        left_port_number=nothing,
        right_port_number=nothing,
        left_termination_ohm=50.0,
        right_termination_ohm=50.0,
        ground_node="0",
    )

Add a through readout line built from an RLGC ladder.

If `left_port_number` or `right_port_number` is provided, the helper will also add the
corresponding `Port + 50 Ohm` branch at that terminal node. To avoid the
`JosephsonCircuits` "Only one resistor allowed per port" restriction, this builder does
not place shunt conductance on the terminal port node.

This helper inserts numeric component values directly into `circuit`, so the caller
should usually allocate the netlist as `Tuple{String,String,String,Any}[]`.
"""
function add_readout_line!(
    circuit;
    prefix::AbstractString,
    left_node,
    right_node,
    line_spec::RLGCSpec,
    left_port_number=nothing,
    right_port_number=nothing,
    left_termination_ohm::Real=50.0,
    right_termination_ohm::Real=50.0,
    ground_node::AbstractString="0",
)
    if !isnothing(left_port_number)
        left_termination_ohm > 0 || error("left_termination_ohm must be positive.")
        _push_component!(circuit, "P$(left_port_number)", left_node, ground_node, left_port_number)
        _push_component!(
            circuit,
            _component_name("R", prefix, "port_left"),
            left_node,
            ground_node,
            Float64(left_termination_ohm),
        )
    end

    if !isnothing(right_port_number)
        right_termination_ohm > 0 || error("right_termination_ohm must be positive.")
        _push_component!(circuit, "P$(right_port_number)", right_node, ground_node, right_port_number)
        _push_component!(
            circuit,
            _component_name("R", prefix, "port_right"),
            right_node,
            ground_node,
            Float64(right_termination_ohm),
        )
    end

    segment = _build_distributed_segment!(
        circuit;
        prefix=prefix,
        start_node=left_node,
        spec=line_spec,
        ground_node=ground_node,
        final_node=right_node,
        add_shunt_at_last_node=false,
    )

    return (
        left_node=string(left_node),
        right_node=string(right_node),
        internal_nodes=segment.internal_nodes,
        section_values=segment.section_values,
    )
end
