"""
    add_quarter_wave_resonator!(
        circuit;
        prefix,
        external_node,
        coupling_cap_f,
        line_spec,
        boundary=:short,
        ground_node="0",
    )

Add a quarter-wave resonator built from an RLGC ladder.

- `boundary=:short` means the far end is tied to ground through the last series section.
- `boundary=:open` means the far end is left floating.

This helper inserts numeric component values directly into `circuit`, so the caller
should usually allocate the netlist as `Tuple{String,String,String,Any}[]`.
"""
function add_quarter_wave_resonator!(
    circuit;
    prefix::AbstractString,
    external_node,
    coupling_cap_f::Real,
    line_spec::RLGCSpec,
    boundary::Symbol=:short,
    ground_node::AbstractString="0",
)
    coupling_cap_f > 0 || _validation_error("coupling_cap_f must be positive.")
    boundary in (:open, :short) || _validation_error("boundary must be :open or :short.")

    resonator_input_node = "$(prefix)_in"
    _push_component!(
        circuit,
        _component_name("C", prefix, "coupling"),
        external_node,
        resonator_input_node,
        Float64(coupling_cap_f),
    )

    segment = if boundary == :short
        _build_distributed_segment!(
            circuit;
            prefix=prefix,
            start_node=resonator_input_node,
            spec=line_spec,
            ground_node=ground_node,
            final_node=ground_node,
            add_shunt_at_last_node=false,
        )
    else
        _build_distributed_segment!(
            circuit;
            prefix=prefix,
            start_node=resonator_input_node,
            spec=line_spec,
            ground_node=ground_node,
        )
    end

    return (
        coupling_node=string(external_node),
        input_node=resonator_input_node,
        end_node=segment.end_node,
        internal_nodes=segment.internal_nodes,
        section_values=segment.section_values,
    )
end
