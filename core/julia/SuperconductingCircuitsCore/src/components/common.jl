Base.@kwdef struct RLGCSpec
    length_m::Float64
    n_sections::Int
    l_per_m_h::Float64
    c_per_m_f::Float64
    r_per_m_ohm::Float64 = 0.0
    g_per_m_s::Float64 = 0.0
end

function _validate_rlgc_spec(spec::RLGCSpec)
    spec.length_m > 0 || _validation_error("length_m must be positive.")
    spec.n_sections > 0 || _validation_error("n_sections must be positive.")
    spec.l_per_m_h > 0 || _validation_error("l_per_m_h must be positive.")
    spec.c_per_m_f > 0 || _validation_error("c_per_m_f must be positive.")
    spec.r_per_m_ohm >= 0 || _validation_error("r_per_m_ohm must be non-negative.")
    spec.g_per_m_s >= 0 || _validation_error("g_per_m_s must be non-negative.")
end

function section_values(spec::RLGCSpec)
    _validate_rlgc_spec(spec)
    dx = spec.length_m / spec.n_sections
    return (
        dx_m=dx,
        r_ohm=spec.r_per_m_ohm * dx,
        l_h=spec.l_per_m_h * dx,
        g_s=spec.g_per_m_s * dx,
        c_f=spec.c_per_m_f * dx,
    )
end

function phase_velocity(spec::RLGCSpec)
    _validate_rlgc_spec(spec)
    return 1 / sqrt(spec.l_per_m_h * spec.c_per_m_f)
end

"""
    add_distributed_segment!(
        circuit;
        prefix,
        start_node,
        spec,
        ground_node="0",
        final_node=nothing,
        add_shunt_at_last_node=true,
    )

Public wrapper around the reusable RLGC ladder generator.

This is the lowest-level building block for manually assembling longer
transmission-line structures section by section.
"""
function add_distributed_segment!(
    circuit;
    prefix::AbstractString,
    start_node,
    spec::RLGCSpec,
    ground_node::AbstractString="0",
    final_node=nothing,
    add_shunt_at_last_node::Bool=true,
)
    return _build_distributed_segment!(
        circuit;
        prefix=prefix,
        start_node=start_node,
        spec=spec,
        ground_node=ground_node,
        final_node=final_node,
        add_shunt_at_last_node=add_shunt_at_last_node,
    )
end

function _push_component!(circuit, name, node_a, node_b, value)
    push!(circuit, (name, string(node_a), string(node_b), value))
end

function _component_name(component_type::AbstractString, prefix::AbstractString, tag::AbstractString)
    return "$(component_type)_$(prefix)_$(tag)"
end

function _section_node(prefix::AbstractString, idx::Int)
    return "$(prefix)_n$(idx)"
end

function _series_mid_node(prefix::AbstractString, idx::Int)
    return "$(prefix)_sec$(idx)_mid"
end

function _add_series_section!(circuit, prefix, idx, left_node, right_node, values)
    current_left = string(left_node)

    # Superconducting / lossless case:
    # if R' = 0, skip the series resistor and keep a pure L section.
    if values.r_ohm > 0
        mid_node = _series_mid_node(prefix, idx)
        _push_component!(
            circuit,
            _component_name("R", prefix, "sec$(idx)"),
            current_left,
            mid_node,
            values.r_ohm,
        )
        current_left = mid_node
    end

    if values.l_h > 0
        _push_component!(
            circuit,
            _component_name("L", prefix, "sec$(idx)"),
            current_left,
            right_node,
            values.l_h,
        )
        return
    end

    _validation_error("Each distributed section must include positive series inductance.")
end

function _add_shunt_section!(circuit, prefix, idx, node, ground_node, values)
    if values.c_f > 0
        _push_component!(
            circuit,
            _component_name("C", prefix, "sec$(idx)"),
            node,
            ground_node,
            values.c_f,
        )
    end

    # JosephsonCircuits does not have a standalone G element.
    # When G' > 0, represent the shunt conductance as an equivalent resistor 1 / G.
    # In the lossless superconducting case G' = 0, omit this branch entirely.
    if values.g_s > 0
        _push_component!(
            circuit,
            _component_name("R", prefix, "gsec$(idx)"),
            node,
            ground_node,
            1 / values.g_s,
        )
    end
end

function _build_distributed_segment!(
    circuit;
    prefix::AbstractString,
    start_node,
    spec::RLGCSpec,
    ground_node::AbstractString="0",
    final_node=nothing,
    add_shunt_at_last_node::Bool=true,
)
    values = section_values(spec)
    current_node = string(start_node)
    internal_nodes = String[]

    for idx in 1:spec.n_sections
        next_node = if idx == spec.n_sections && !isnothing(final_node)
            string(final_node)
        else
            _section_node(prefix, idx)
        end

        _add_series_section!(circuit, prefix, idx, current_node, next_node, values)

        if idx < spec.n_sections || add_shunt_at_last_node
            _add_shunt_section!(circuit, prefix, idx, next_node, ground_node, values)
        end

        if idx < spec.n_sections
            push!(internal_nodes, next_node)
        end

        current_node = next_node
    end

    return (
        start_node=string(start_node),
        end_node=current_node,
        internal_nodes=internal_nodes,
        section_values=values,
    )
end
