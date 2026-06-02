Base.@kwdef struct CoupledWindowSpec
    length_m::Float64
    n_sections::Int
    l11_per_m_h::Float64
    l22_per_m_h::Float64
    lm_per_m_h::Float64
    c1g_per_m_f::Float64
    c2g_per_m_f::Float64
    cm_per_m_f::Float64
    r1_per_m_ohm::Float64 = 0.0
    r2_per_m_ohm::Float64 = 0.0
    g1_per_m_s::Float64 = 0.0
    g2_per_m_s::Float64 = 0.0
end

function _validate_coupled_window_spec(spec::CoupledWindowSpec)
    spec.length_m > 0 || _validation_error("length_m must be positive.")
    spec.n_sections > 0 || _validation_error("n_sections must be positive.")
    spec.l11_per_m_h > 0 || _validation_error("l11_per_m_h must be positive.")
    spec.l22_per_m_h > 0 || _validation_error("l22_per_m_h must be positive.")
    spec.c1g_per_m_f > 0 || _validation_error("c1g_per_m_f must be positive.")
    spec.c2g_per_m_f > 0 || _validation_error("c2g_per_m_f must be positive.")
    spec.cm_per_m_f >= 0 || _validation_error("cm_per_m_f must be non-negative.")
    spec.r1_per_m_ohm >= 0 || _validation_error("r1_per_m_ohm must be non-negative.")
    spec.r2_per_m_ohm >= 0 || _validation_error("r2_per_m_ohm must be non-negative.")
    spec.g1_per_m_s >= 0 || _validation_error("g1_per_m_s must be non-negative.")
    spec.g2_per_m_s >= 0 || _validation_error("g2_per_m_s must be non-negative.")

    coupling_limit = sqrt(spec.l11_per_m_h * spec.l22_per_m_h)
    abs(spec.lm_per_m_h) <= coupling_limit ||
        _validation_error("abs(lm_per_m_h) must not exceed sqrt(l11_per_m_h * l22_per_m_h).")
end

function coupled_window_section_values(spec::CoupledWindowSpec)
    _validate_coupled_window_spec(spec)

    dx = spec.length_m / spec.n_sections
    l1_h = spec.l11_per_m_h * dx
    l2_h = spec.l22_per_m_h * dx
    lm_h = spec.lm_per_m_h * dx

    return (
        dx_m=dx,
        line_a=(
            r_ohm=spec.r1_per_m_ohm * dx,
            l_h=l1_h,
            g_s=spec.g1_per_m_s * dx,
            c_f=spec.c1g_per_m_f * dx,
        ),
        line_b=(
            r_ohm=spec.r2_per_m_ohm * dx,
            l_h=l2_h,
            g_s=spec.g2_per_m_s * dx,
            c_f=spec.c2g_per_m_f * dx,
        ),
        lm_h=lm_h,
        k=lm_h / sqrt(l1_h * l2_h),
        cm_f=spec.cm_per_m_f * dx,
    )
end

function _coupled_section_node(prefix::AbstractString, line_tag::AbstractString, idx::Int)
    return _section_node("$(prefix)_$(line_tag)", idx)
end

function _coupled_branch_prefix(prefix::AbstractString, line_tag::AbstractString)
    return "$(prefix)_$(line_tag)"
end

"""
    _emit_coupled_window!(
        circuit;
        prefix,
        left_node_a,
        right_node_a,
        left_node_b,
        right_node_b,
        spec,
        ground_node="0",
    )

Internal compiler helper for emitting a finite-length coupled window between
two distributed transmission-line paths.

`spec` is expressed in per-unit-length mutual form:
- line A self inductance `l11_per_m_h`
- line B self inductance `l22_per_m_h`
- mutual inductance `lm_per_m_h`
- shunt capacitances to ground `c1g_per_m_f`, `c2g_per_m_f`
- cross capacitance `cm_per_m_f`

Each discrete section emits:
- one series RL branch on line A
- one series RL branch on line B
- one JosephsonCircuits `K` element between the two section inductors
- two shunt CG branches to ground
- one cross capacitor between the two lines

The `K` element uses the coupling coefficient `k = M / sqrt(L1 * L2)`, which is
the convention JosephsonCircuits expects for mutual inductors.
"""
function _emit_coupled_window!(
    circuit;
    prefix::AbstractString,
    left_node_a,
    right_node_a,
    left_node_b,
    right_node_b,
    spec::CoupledWindowSpec,
    ground_node::AbstractString="0",
)
    values = coupled_window_section_values(spec)
    branch_prefix_a = _coupled_branch_prefix(prefix, "a")
    branch_prefix_b = _coupled_branch_prefix(prefix, "b")

    current_node_a = string(left_node_a)
    current_node_b = string(left_node_b)
    internal_nodes_a = String[]
    internal_nodes_b = String[]
    coupling_names = String[]

    for idx in 1:spec.n_sections
        next_node_a = idx == spec.n_sections ? string(right_node_a) :
            _coupled_section_node(prefix, "a", idx)
        next_node_b = idx == spec.n_sections ? string(right_node_b) :
            _coupled_section_node(prefix, "b", idx)

        _add_series_section!(circuit, branch_prefix_a, idx, current_node_a, next_node_a, values.line_a)
        _add_series_section!(circuit, branch_prefix_b, idx, current_node_b, next_node_b, values.line_b)

        inductor_name_a = _component_name("L", branch_prefix_a, "sec$(idx)")
        inductor_name_b = _component_name("L", branch_prefix_b, "sec$(idx)")
        coupling_name = _component_name("K", prefix, "sec$(idx)")
        _push_component!(circuit, coupling_name, inductor_name_a, inductor_name_b, values.k)
        push!(coupling_names, coupling_name)

        _add_shunt_section!(circuit, branch_prefix_a, idx, next_node_a, ground_node, values.line_a)
        _add_shunt_section!(circuit, branch_prefix_b, idx, next_node_b, ground_node, values.line_b)

        if values.cm_f > 0
            _push_component!(
                circuit,
                _component_name("C", prefix, "xsec$(idx)"),
                next_node_a,
                next_node_b,
                values.cm_f,
            )
        end

        if idx < spec.n_sections
            push!(internal_nodes_a, next_node_a)
            push!(internal_nodes_b, next_node_b)
        end

        current_node_a = next_node_a
        current_node_b = next_node_b
    end

    return (
        left_node_a=string(left_node_a),
        right_node_a=string(right_node_a),
        left_node_b=string(left_node_b),
        right_node_b=string(right_node_b),
        internal_nodes_a=internal_nodes_a,
        internal_nodes_b=internal_nodes_b,
        coupling_names=coupling_names,
        section_values=values,
    )
end
