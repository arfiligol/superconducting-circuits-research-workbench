"""
    add_half_wave_purcell_filter!(
        circuit;
        prefix,
        left_external_node,
        right_external_node,
        left_coupling_cap_f,
        right_coupling_cap_f,
        line_spec,
        ground_node="0",
    )

Add a half-wave Purcell filter built from an RLGC ladder, with an input and output
coupling capacitor that may have different values.

This helper inserts numeric component values directly into `circuit`, so the caller
should usually allocate the netlist as `Tuple{String,String,String,Any}[]`.
"""
function add_half_wave_purcell_filter!(
    circuit;
    prefix::AbstractString,
    left_external_node,
    right_external_node,
    left_coupling_cap_f::Real,
    right_coupling_cap_f::Real,
    line_spec::RLGCSpec,
    ground_node::AbstractString="0",
)
    left_coupling_cap_f > 0 || error("left_coupling_cap_f must be positive.")
    right_coupling_cap_f > 0 || error("right_coupling_cap_f must be positive.")

    filter_left_node = "$(prefix)_left"
    filter_right_node = "$(prefix)_right"

    _push_component!(
        circuit,
        _component_name("C", prefix, "in"),
        left_external_node,
        filter_left_node,
        Float64(left_coupling_cap_f),
    )

    segment = _build_distributed_segment!(
        circuit;
        prefix=prefix,
        start_node=filter_left_node,
        spec=line_spec,
        ground_node=ground_node,
        final_node=filter_right_node,
    )

    _push_component!(
        circuit,
        _component_name("C", prefix, "out"),
        filter_right_node,
        right_external_node,
        Float64(right_coupling_cap_f),
    )

    return (
        left_node=filter_left_node,
        right_node=filter_right_node,
        internal_nodes=segment.internal_nodes,
        section_values=segment.section_values,
    )
end
