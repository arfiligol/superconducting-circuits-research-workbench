abstract type AbstractTransmissionLineModel end

struct RLGCSpec <: AbstractTransmissionLineModel
    length_m::Float64
    reference_section_length_m::Float64
    section_length_m::Float64
    n_sections::Int
    l_per_m_h::Float64
    c_per_m_f::Float64
    r_per_m_ohm::Float64
    g_per_m_s::Float64
end

function _selected_keyword(primary, alias, name::AbstractString)
    if !isnothing(primary) && !isnothing(alias)
        Float64(primary) ≈ Float64(alias) ||
            _validation_error("RLGCSpec received conflicting $(name) keyword aliases.")
    end
    return isnothing(primary) ? alias : primary
end

function _derived_section_count(length_m::Real, reference_section_length_m::Real)
    length = Float64(length_m)
    reference = Float64(reference_section_length_m)
    reference > 0 || _validation_error("section_length_m must be positive.")
    raw = length / reference
    nearest = round(Int, raw)
    count = isapprox(raw, nearest; atol=1e-12, rtol=1e-9) ? nearest : ceil(Int, raw)
    count > 0 || _validation_error("transmission-line model must contain at least one section.")
    return count
end

function RLGCSpec(;
    length=nothing,
    length_m=nothing,
    section_length=nothing,
    section_length_m=nothing,
    n_sections=nothing,
    l_per_m=nothing,
    l_per_m_h=nothing,
    c_per_m=nothing,
    c_per_m_f=nothing,
    r_per_m=0.0,
    r_per_m_ohm=nothing,
    g_per_m=0.0,
    g_per_m_s=nothing,
)
    selected_length = _selected_keyword(length_m, length, "length")
    isnothing(selected_length) && _validation_error("RLGCSpec requires length_m or length.")
    selected_l = _selected_keyword(l_per_m_h, l_per_m, "l_per_m")
    selected_c = _selected_keyword(c_per_m_f, c_per_m, "c_per_m")
    isnothing(selected_l) && _validation_error("RLGCSpec requires l_per_m_h or l_per_m.")
    isnothing(selected_c) && _validation_error("RLGCSpec requires c_per_m_f or c_per_m.")
    selected_r = isnothing(r_per_m_ohm) ? r_per_m : r_per_m_ohm
    selected_g = isnothing(g_per_m_s) ? g_per_m : g_per_m_s

    length_value = Float64(selected_length)
    length_value > 0 || _validation_error("length_m must be positive.")
    l_value = Float64(selected_l)
    c_value = Float64(selected_c)
    r_value = Float64(selected_r)
    g_value = Float64(selected_g)
    l_value > 0 || _validation_error("l_per_m_h must be positive.")
    c_value > 0 || _validation_error("c_per_m_f must be positive.")
    r_value >= 0 || _validation_error("r_per_m_ohm must be non-negative.")
    g_value >= 0 || _validation_error("g_per_m_s must be non-negative.")

    reference_value = _selected_keyword(section_length_m, section_length, "section_length")
    if isnothing(reference_value) && isnothing(n_sections)
        _validation_error("RLGCSpec requires section_length_m/section_length or n_sections.")
    elseif isnothing(reference_value)
        count = Int(n_sections)
        count > 0 || _validation_error("n_sections must be positive.")
        actual_section_length = length_value / count
        reference_section_length = actual_section_length
    elseif isnothing(n_sections)
        reference_section_length = Float64(reference_value)
        count = _derived_section_count(length_value, reference_section_length)
        actual_section_length = length_value / count
    else
        reference_section_length = Float64(reference_value)
        reference_section_length > 0 || _validation_error("section_length_m must be positive.")
        count = Int(n_sections)
        count > 0 || _validation_error("n_sections must be positive.")
        actual_section_length = length_value / count
        actual_section_length <= reference_section_length * (1 + 1e-9) ||
            _validation_error("n_sections yields section length larger than section_length_m reference.")
    end

    return RLGCSpec(
        length_value,
        reference_section_length,
        actual_section_length,
        count,
        l_value,
        c_value,
        r_value,
        g_value,
    )
end

function _validate_rlgc_spec(spec::RLGCSpec)
    spec.length_m > 0 || _validation_error("length_m must be positive.")
    spec.reference_section_length_m > 0 || _validation_error("reference_section_length_m must be positive.")
    spec.section_length_m > 0 || _validation_error("section_length_m must be positive.")
    spec.n_sections > 0 || _validation_error("n_sections must be positive.")
    spec.l_per_m_h > 0 || _validation_error("l_per_m_h must be positive.")
    spec.c_per_m_f > 0 || _validation_error("c_per_m_f must be positive.")
    spec.r_per_m_ohm >= 0 || _validation_error("r_per_m_ohm must be non-negative.")
    spec.g_per_m_s >= 0 || _validation_error("g_per_m_s must be non-negative.")
    isapprox(spec.section_length_m * spec.n_sections, spec.length_m; atol=1e-12, rtol=1e-9) ||
        _validation_error("RLGCSpec section length and count must reproduce length_m.")
end

function section_values(spec::RLGCSpec)
    _validate_rlgc_spec(spec)
    dx = spec.section_length_m
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
    _emit_distributed_segment!(
        circuit;
        prefix,
        start_node,
        spec,
        ground_node="0",
        final_node=nothing,
        add_shunt_at_last_node=true,
    )

Internal compiler helper for emitting a discretized RLGC ladder into a
target tuple netlist.
"""
function _emit_distributed_segment!(
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
