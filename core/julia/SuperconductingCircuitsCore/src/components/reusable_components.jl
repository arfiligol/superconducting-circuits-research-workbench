# This file composes executable reusable components from Core primitives; it
# owns plan topology and inspectable component records, not reusable physics.
# Canonical ideal parallel-LC physics and observable layers:
# https://github.com/arfiligol/SCQ_Design/blob/main/docs/knowledge/network-modeling/ideal-parallel-lc-resonator.qmd
# MTL wrappers preserve the LC-only coupled-window contract owned by
# transmission_lines.jl. Canonical matrix physics and artifact eligibility:
# https://github.com/arfiligol/SCQ_Design/blob/main/docs/knowledge/transmission-lines/multiconductor-rlgc-matrix-semantics.qmd

struct ParallelLCResonator
    id::String
    node::AbstractNodeEndpoint
    capacitor::ShuntCapacitor
    inductor::ShuntInductor
end

# Canonical floating-qubit small-signal semantics:
# https://github.com/arfiligol/SCQ_Design/blob/main/docs/knowledge/readout/bare-vs-hybridized-readout-filter-modes.qmd
struct LinearizedFloatingQubit
    id::String
    island_1::AbstractNodeEndpoint
    island_2::AbstractNodeEndpoint
    readout_attachment::AbstractNodeEndpoint
    c01::ShuntCapacitor
    c02::ShuntCapacitor
    c12::CapacitiveCoupling
    cr1::CapacitiveCoupling
    cr2::CapacitiveCoupling
    lj1::SeriesInductor
    lj2::SeriesInductor
end

# Canonical localized-capacitor region ownership and positive branch view:
# https://github.com/arfiligol/SCQ_Design/blob/main/docs/knowledge/design-workflows/localized-electrostatic-component-modeling.qmd
struct InterdigitatedCapacitor
    id::String
    terminal_1::AbstractNodeEndpoint
    terminal_2::AbstractNodeEndpoint
    c1g::ShuntCapacitor
    c2g::ShuntCapacitor
    c12::CapacitiveCoupling
end

# ReflectiveJPA contains one nonlinear JosephsonJunction. It is not a dc SQUID
# and has no external-flux, asymmetry, or loop-inductance model.
# https://github.com/arfiligol/SCQ_Design/blob/main/docs/knowledge/josephson-physics/josephson-current-phase-energy-and-inductance.qmd
# https://github.com/arfiligol/SCQ_Design/blob/main/docs/knowledge/josephson-physics/josephson-cosine-and-quantum-anharmonicity.qmd
struct ReflectiveJPA
    id::String
    port_node::AbstractNodeEndpoint
    resonator_node::AbstractNodeEndpoint
    coupling_capacitor::CapacitiveCoupling
    shunt_capacitor::ShuntCapacitor
    junction::JosephsonJunction
end

struct HalfWaveResonator
    id::String
    line::TransmissionLineLadder
end

struct QuarterWaveResonator
    id::String
    line::TransmissionLineLadder
end

struct IntrinsicInterferometricPurcellFilter
    id::String
    readout_resonator::QuarterWaveResonator
    filter_resonator::QuarterWaveResonator
    window::CoupledTransmissionWindow
    feedline_capacitor::InterdigitatedCapacitor
    c0r::Union{Nothing,ShuntCapacitor}
    readout_attachment::AbstractNodeEndpoint
    feedline_attachment::AbstractNodeEndpoint
end

struct IntrinsicInterferometricPurcellFilterWithQubit
    id::String
    filter::IntrinsicInterferometricPurcellFilter
    qubit::LinearizedFloatingQubit
    c0r::Union{Nothing,ShuntCapacitor}
end

struct IntrinsicInterferometricPurcellFilterEquivalent
    id::String
    readout_resonator::ParallelLCResonator
    filter_resonator::ParallelLCResonator
    bridge_capacitor::CapacitiveCoupling
    bridge_inductor::SeriesInductor
    feedline_capacitor::InterdigitatedCapacitor
    c0r::Union{Nothing,ShuntCapacitor}
    readout_attachment::AbstractNodeEndpoint
    feedline_attachment::AbstractNodeEndpoint
end

struct IntrinsicInterferometricPurcellFilterEquivalentWithQubit
    id::String
    filter::IntrinsicInterferometricPurcellFilterEquivalent
    qubit::LinearizedFloatingQubit
    c0r::Union{Nothing,ShuntCapacitor}
end

struct ReadoutLineWithPurcellFilter
    id::String
    input_line::TransmissionLineLadder
    filter_line::TransmissionLineLadder
    output_line::TransmissionLineLadder
    input_coupling::CapacitiveCoupling
    output_coupling::CapacitiveCoupling
    input_node::AbstractNodeEndpoint
    output_node::AbstractNodeEndpoint
    filter_head::AbstractNodeEndpoint
    filter_tail::AbstractNodeEndpoint
end

struct ReadoutPurcellQWRMTL
    id::String
    readout_filter::ReadoutLineWithPurcellFilter
    qwr::QuarterWaveResonator
    window::CoupledTransmissionWindow
end

function _component_node(id, name)
    return external_node("$(id)_$(name)")
end

"""
    add_parallel_lc_resonator!(plan; id, node, capacitance, inductance,
        capacitor_label, inductor_label)

Insert an ideal capacitor and ideal inductor in parallel from `node` to ground
and record one inspectable resonator component. This function owns only that
Plan-level topology; ports, loading, solver intent, and observable conversion
belong to the enclosing circuit and simulation workflow.
"""
function add_parallel_lc_resonator!(
    plan::CircuitPlan;
    id,
    node,
    capacitance,
    inductance,
    capacitor_label=raw"$C_r$",
    inductor_label=raw"$L_r$",
)
    node isa AbstractNodeEndpoint || _validation_error("add_parallel_lc_resonator! requires node to be a NodeEndpoint.")
    capacitor = shunt_capacitor!(
        plan;
        id="$(id)_capacitance",
        at=node,
        capacitance=capacitance,
        role=:parallel_lc_capacitance,
        label=capacitor_label,
    )
    inductor = shunt_inductor!(
        plan;
        id="$(id)_inductance",
        at=node,
        inductance=inductance,
        role=:parallel_lc_inductance,
        label=inductor_label,
    )
    record_engineering_component!(
        plan;
        id=id,
        display_name=id,
        component_type=:GroundedLCResonator,
        role=:resonator,
        parameters=Dict(
            :capacitance_f => capacitance,
            :inductance_h => inductance,
            :inductive_branch_kind => :linear,
        ),
        pins=[:signal],
    )
    return ParallelLCResonator(string(id), node, capacitor, inductor)
end

"""
    add_intrinsic_interferometric_purcell_filter_equivalent!(plan; id,
        readout_attachment, feedline_attachment, readout_capacitance_f,
        readout_inductance_h, filter_capacitance_f, filter_inductance_h,
        bridge_capacitance_f, bridge_inductance_h,
        idc_filter_ground_capacitance_f, idc_feedline_ground_capacitance_f,
        idc_mutual_capacitance_f, c0r_f=0.0)

Insert the response-matched finite equivalent of the intrinsic filter. The
readout and filter are grounded parallel LC branches, their coupling is a
parallel `Cn`/`Ln` bridge, and the filter-to-feedline attachment is the
complete three-branch IDC. The component contains no feedline or port.
"""
function add_intrinsic_interferometric_purcell_filter_equivalent!(
    plan::CircuitPlan;
    id,
    readout_attachment,
    feedline_attachment,
    readout_capacitance_f,
    readout_inductance_h,
    filter_capacitance_f,
    filter_inductance_h,
    bridge_capacitance_f,
    bridge_inductance_h,
    idc_filter_ground_capacitance_f,
    idc_feedline_ground_capacitance_f,
    idc_mutual_capacitance_f,
    c0r_f=0.0,
)
    component_id = strip(string(id))
    isempty(component_id) &&
        _validation_error("IntrinsicInterferometricPurcellFilterEquivalent id must be nonempty.")
    readout_attachment isa AbstractNodeEndpoint &&
        feedline_attachment isa AbstractNodeEndpoint ||
        _validation_error("IntrinsicInterferometricPurcellFilterEquivalent attachments must be NodeEndpoints.")
    readout_attachment != feedline_attachment ||
        _validation_error("IntrinsicInterferometricPurcellFilterEquivalent attachments must be distinct.")
    numeric = Float64[
        readout_capacitance_f,
        readout_inductance_h,
        filter_capacitance_f,
        filter_inductance_h,
        bridge_capacitance_f,
        bridge_inductance_h,
        idc_filter_ground_capacitance_f,
        idc_feedline_ground_capacitance_f,
        idc_mutual_capacitance_f,
    ]
    all(value -> isfinite(value) && value > 0, numeric) ||
        _validation_error("IntrinsicInterferometricPurcellFilterEquivalent element values must be finite and positive.")
    c0r_value = Float64(c0r_f)
    isfinite(c0r_value) && c0r_value >= 0 ||
        _validation_error("IntrinsicInterferometricPurcellFilterEquivalent c0r_f must be finite and nonnegative.")

    filter_node = _component_node(component_id, "filter")
    readout_resonator = add_parallel_lc_resonator!(
        plan;
        id="$(component_id)_readout_resonator",
        node=readout_attachment,
        capacitance=numeric[1],
        inductance=numeric[2],
        capacitor_label=raw"$C_r$",
        inductor_label=raw"$L_r$",
    )
    filter_resonator = add_parallel_lc_resonator!(
        plan;
        id="$(component_id)_filter_resonator",
        node=filter_node,
        capacitance=numeric[3],
        inductance=numeric[4],
        capacitor_label=raw"$C_p$",
        inductor_label=raw"$L_p$",
    )
    bridge_capacitor = couple_capacitive!(
        plan;
        id="$(component_id)_bridge_capacitor",
        from=readout_attachment,
        to=filter_node,
        capacitance=numeric[5],
        role=:response_matched_bridge_capacitance,
        label=raw"$C_n$",
    )
    bridge_inductor = series_inductor!(
        plan;
        id="$(component_id)_bridge_inductor",
        from=readout_attachment,
        to=filter_node,
        inductance=numeric[6],
        role=:response_matched_bridge_inductance,
        label=raw"$L_n$",
    )
    feedline_capacitor = add_interdigitated_capacitor!(
        plan;
        id="$(component_id)_feedline_idc",
        terminal_1=filter_node,
        terminal_2=feedline_attachment,
        c1g_f=numeric[7],
        c2g_f=numeric[8],
        c12_f=numeric[9],
        c1g_label=raw"$C_{pG}^{\mathrm{IDC}}$",
        c2g_label=raw"$C_{f_cG}^{\mathrm{IDC}}$",
        c12_label=raw"$C_{pf_c}^{\mathrm{IDC}}$",
    )
    c0r = c0r_value == 0 ? nothing : shunt_capacitor!(
        plan;
        id="$(component_id)_c0r",
        at=readout_attachment,
        capacitance=c0r_value,
        role=:readout_attachment_ground_capacitance,
        label=raw"$C_{0r}$",
    )
    record_engineering_component!(
        plan;
        id=component_id,
        display_name=component_id,
        component_type=:IntrinsicInterferometricPurcellFilterEquivalent,
        role=:purcell_filter_equivalent,
        parameters=Dict(
            :model_family => :response_matched_parallel_lc_bridge,
            :c0r_f => c0r_value,
            :contains_feedline => false,
            :feedline_coupling_kind => :interdigitated_three_branch,
        ),
        pins=[:readout_attachment, :feedline_attachment],
    )
    return IntrinsicInterferometricPurcellFilterEquivalent(
        component_id,
        readout_resonator,
        filter_resonator,
        bridge_capacitor,
        bridge_inductor,
        feedline_capacitor,
        c0r,
        readout_attachment,
        feedline_attachment,
    )
end

"""
    add_linearized_floating_qubit!(plan; id, island_1, island_2,
        readout_attachment, c01_f, c02_f, c12_f, cr1_f, cr2_f,
        l_j_per_junction_h)

Insert the passive small-signal circuit for a symmetric floating qubit. The
component owns five capacitance branches and two identical parallel linearized
Josephson-inductance branches; parameter extraction and nonlinear junction
physics remain outside this component.
"""
function add_linearized_floating_qubit!(
    plan::CircuitPlan;
    id,
    island_1,
    island_2,
    readout_attachment,
    c01_f,
    c02_f,
    c12_f,
    cr1_f,
    cr2_f,
    l_j_per_junction_h,
)
    component_id = strip(string(id))
    isempty(component_id) && _validation_error("LinearizedFloatingQubit id must be nonempty.")
    endpoints = (island_1, island_2, readout_attachment)
    all(endpoint -> endpoint isa AbstractNodeEndpoint, endpoints) ||
        _validation_error("LinearizedFloatingQubit endpoints must be NodeEndpoints.")
    length(Set(endpoints)) == 3 ||
        _validation_error("LinearizedFloatingQubit endpoints must be distinct.")

    numeric = Float64[c01_f, c02_f, c12_f, cr1_f, cr2_f, l_j_per_junction_h]
    all(value -> isfinite(value) && value > 0, numeric) ||
        _validation_error("LinearizedFloatingQubit capacitances and per-junction inductance must be finite and positive.")
    c01_value, c02_value, c12_value, cr1_value, cr2_value, lj_value = numeric

    c01 = shunt_capacitor!(
        plan;
        id="$(component_id)_c01",
        at=island_1,
        capacitance=c01_value,
        role=:floating_qubit_island_ground_capacitance,
        label=raw"$C_{01}$",
    )
    c02 = shunt_capacitor!(
        plan;
        id="$(component_id)_c02",
        at=island_2,
        capacitance=c02_value,
        role=:floating_qubit_island_ground_capacitance,
        label=raw"$C_{02}$",
    )
    c12 = couple_capacitive!(
        plan;
        id="$(component_id)_c12",
        from=island_1,
        to=island_2,
        capacitance=c12_value,
        role=:floating_qubit_island_mutual_capacitance,
        label=raw"$C_{12}$",
    )
    cr1 = couple_capacitive!(
        plan;
        id="$(component_id)_cr1",
        from=readout_attachment,
        to=island_1,
        capacitance=cr1_value,
        role=:readout_to_floating_qubit_capacitance,
        label=raw"$C_{r1}$",
    )
    cr2 = couple_capacitive!(
        plan;
        id="$(component_id)_cr2",
        from=readout_attachment,
        to=island_2,
        capacitance=cr2_value,
        role=:readout_to_floating_qubit_capacitance,
        label=raw"$C_{r2}$",
    )
    lj1 = series_inductor!(
        plan;
        id="$(component_id)_lj1",
        from=island_1,
        to=island_2,
        inductance=lj_value,
        role=:floating_qubit_linearized_josephson_inductance,
        label=raw"$L_{J1}$",
    )
    lj2 = series_inductor!(
        plan;
        id="$(component_id)_lj2",
        from=island_1,
        to=island_2,
        inductance=lj_value,
        role=:floating_qubit_linearized_josephson_inductance,
        label=raw"$L_{J2}$",
    )
    record_engineering_component!(
        plan;
        id=component_id,
        display_name=component_id,
        component_type=:LinearizedFloatingQubit,
        role=:qubit,
        parameters=Dict(
            :c01_f => c01_value,
            :c02_f => c02_value,
            :c12_f => c12_value,
            :cr1_f => cr1_value,
            :cr2_f => cr2_value,
            :l_j_per_junction_h => lj_value,
            :inductive_branch_kind => :linearized_josephson,
        ),
        pins=[:island_1, :island_2, :readout_attachment],
    )
    return LinearizedFloatingQubit(
        component_id,
        island_1,
        island_2,
        readout_attachment,
        c01,
        c02,
        c12,
        cr1,
        cr2,
        lj1,
        lj2,
    )
end

function add_reflective_jpa!(
    plan::CircuitPlan;
    id,
    port_node,
    resonator_node,
    coupling_capacitance,
    resonator_capacitance,
    josephson_inductance,
)
    port_node isa AbstractNodeEndpoint ||
        _validation_error("add_reflective_jpa! requires port_node to be a NodeEndpoint.")
    resonator_node isa AbstractNodeEndpoint ||
        _validation_error("add_reflective_jpa! requires resonator_node to be a NodeEndpoint.")
    coupling = couple_capacitive!(
        plan;
        id="$(id)_coupling_capacitance",
        from=port_node,
        to=resonator_node,
        capacitance=coupling_capacitance,
        role=:jpa_coupling_capacitance,
        label=raw"$C_c$",
    )
    capacitance = shunt_capacitor!(
        plan;
        id="$(id)_shunt_capacitance",
        at=resonator_node,
        capacitance=resonator_capacitance,
        role=:jpa_resonator_capacitance,
        label=raw"$C_r$",
    )
    junction = josephson_junction!(
        plan;
        id="$(id)_junction",
        from=resonator_node,
        to=ground(),
        josephson_inductance=josephson_inductance,
        role=:jpa_josephson_junction,
        label=raw"$JJ$",
    )
    record_engineering_component!(
        plan;
        id=id,
        display_name=id,
        component_type=:CapacitivelyCoupledGroundedLCResonator,
        role=:resonator,
        parameters=Dict(
            :coupling_capacitance_f => coupling_capacitance,
            :capacitance_f => resonator_capacitance,
            :josephson_inductance_h => josephson_inductance,
            :inductive_branch_kind => :josephson,
        ),
        pins=[:port, :resonator],
    )
    return ReflectiveJPA(string(id), port_node, resonator_node, coupling, capacitance, junction)
end

function add_half_wave_resonator!(
    plan::CircuitPlan;
    id,
    head,
    tail,
    spec::RLGCSpec,
    breakpoints_m=nothing,
    section_overrides=nothing,
)
    line = build_lc_ladder_line!(
        plan;
        id=id,
        head=head,
        tail=tail,
        spec=spec,
        head_termination=:open,
        tail_termination=:open,
        breakpoints_m=breakpoints_m,
        section_overrides=section_overrides,
    )
    return HalfWaveResonator(string(id), line)
end

function half_wave_resonator!(plan::CircuitPlan; kwargs...)
    return add_half_wave_resonator!(plan; kwargs...)
end

function add_quarter_wave_resonator!(
    plan::CircuitPlan;
    id,
    grounded_head,
    open_tail,
    spec::RLGCSpec,
    breakpoints_m=nothing,
    section_overrides=nothing,
)
    grounded_head isa AbstractNodeEndpoint ||
        _validation_error("add_quarter_wave_resonator! requires grounded_head to be a NodeEndpoint.")
    open_tail isa AbstractNodeEndpoint ||
        _validation_error("add_quarter_wave_resonator! requires open_tail to be a NodeEndpoint.")
    line = build_lc_ladder_line!(
        plan;
        id=id,
        head=grounded_head,
        tail=open_tail,
        spec=spec,
        head_termination=:short,
        tail_termination=:open,
        breakpoints_m=breakpoints_m,
        section_overrides=section_overrides,
    )
    return QuarterWaveResonator(string(id), line)
end

function quarter_wave_resonator!(plan::CircuitPlan; kwargs...)
    return add_quarter_wave_resonator!(plan; kwargs...)
end

"""
    add_interdigitated_capacitor!(plan; id, terminal_1, terminal_2,
        c1g_f, c2g_f, c12_f, c1g_label, c2g_label, c12_label)

Insert the complete positive-branch π equivalent of one two-terminal
interdigitated capacitor. Terminal order is preserved: `c1g_f` belongs to
`terminal_1`, `c2g_f` to `terminal_2`, and `c12_f` joins the terminals.
"""
function add_interdigitated_capacitor!(
    plan::CircuitPlan;
    id,
    terminal_1,
    terminal_2,
    c1g_f,
    c2g_f,
    c12_f,
    c1g_label=raw"$C_{1G}$",
    c2g_label=raw"$C_{2G}$",
    c12_label=raw"$C_{12}$",
)
    component_id = strip(string(id))
    isempty(component_id) && _validation_error("InterdigitatedCapacitor id must be nonempty.")
    terminal_1 isa AbstractNodeEndpoint && terminal_2 isa AbstractNodeEndpoint ||
        _validation_error("InterdigitatedCapacitor terminals must be NodeEndpoints.")
    terminal_1 != terminal_2 ||
        _validation_error("InterdigitatedCapacitor terminals must be distinct.")
    numeric = Float64[c1g_f, c2g_f, c12_f]
    all(value -> isfinite(value) && value > 0, numeric) ||
        _validation_error("InterdigitatedCapacitor branch capacitances must be finite and positive.")
    c1g_value, c2g_value, c12_value = numeric

    c1g = shunt_capacitor!(
        plan;
        id="$(component_id)_c1g",
        at=terminal_1,
        capacitance=c1g_value,
        role=:interdigitated_capacitor_terminal_ground_capacitance,
        label=c1g_label,
    )
    c2g = shunt_capacitor!(
        plan;
        id="$(component_id)_c2g",
        at=terminal_2,
        capacitance=c2g_value,
        role=:interdigitated_capacitor_terminal_ground_capacitance,
        label=c2g_label,
    )
    c12 = couple_capacitive!(
        plan;
        id="$(component_id)_c12",
        from=terminal_1,
        to=terminal_2,
        capacitance=c12_value,
        role=:interdigitated_capacitor_mutual_capacitance,
        label=c12_label,
    )
    record_engineering_component!(
        plan;
        id=component_id,
        display_name=component_id,
        component_type=:InterdigitatedCapacitor,
        role=:localized_capacitive_coupler,
        parameters=Dict(
            :c1g_f => c1g_value,
            :c2g_f => c2g_value,
            :c12_f => c12_value,
            :terminal_order => [:terminal_1, :terminal_2],
        ),
        pins=[:terminal_1, :terminal_2],
    )
    return InterdigitatedCapacitor(
        component_id,
        terminal_1,
        terminal_2,
        c1g,
        c2g,
        c12,
    )
end

"""
    add_intrinsic_interferometric_purcell_filter!(plan; id,
        readout_attachment, feedline_attachment, readout_spec, filter_spec,
        mtl_model, c1g_f, c2g_f, c12_f, c0r_f=0.0,
        coupling_orientation=:same_direction)

Insert two grounded-head/open-tail quarter-wave resonators, their finite MTL
window, and the complete three-branch IDC from the filter open tail to an
exposed feedline attachment. `c0r_f` is owned at the readout attachment; an
exact zero records the parameter without emitting a physical branch. This
component contains no feedline or port.
"""
function add_intrinsic_interferometric_purcell_filter!(
    plan::CircuitPlan;
    id,
    readout_attachment,
    feedline_attachment,
    readout_spec::RLGCSpec,
    filter_spec::RLGCSpec,
    mtl_model::MTLCoupledRLGCSpec,
    c1g_f,
    c2g_f,
    c12_f,
    c0r_f=0.0,
    coupling_orientation=:same_direction,
)
    component_id = strip(string(id))
    isempty(component_id) &&
        _validation_error("IntrinsicInterferometricPurcellFilter id must be nonempty.")
    readout_attachment isa AbstractNodeEndpoint &&
        feedline_attachment isa AbstractNodeEndpoint ||
        _validation_error("IntrinsicInterferometricPurcellFilter attachments must be NodeEndpoints.")
    readout_attachment != feedline_attachment ||
        _validation_error("IntrinsicInterferometricPurcellFilter attachments must be distinct.")
    orientation = _normalize_coupling_orientation(coupling_orientation)
    orientation == :same_direction ||
        _validation_error("IntrinsicInterferometricPurcellFilter requires same-direction MTL coupling.")
    numeric = Float64[c1g_f, c2g_f, c12_f]
    all(value -> isfinite(value) && value > 0, numeric) ||
        _validation_error("IntrinsicInterferometricPurcellFilter IDC capacitances must be finite and positive.")
    c0r_value = Float64(c0r_f)
    isfinite(c0r_value) && c0r_value >= 0 ||
        _validation_error("IntrinsicInterferometricPurcellFilter c0r_f must be finite and nonnegative.")

    readout_grounded_head = _component_node(component_id, "readout_grounded_head")
    filter_grounded_head = _component_node(component_id, "filter_grounded_head")
    filter_open_tail = _component_node(component_id, "filter_open_tail")
    readout_breakpoints = [mtl_model.start1_m, mtl_model.start1_m + mtl_model.length_m]
    filter_breakpoints = [mtl_model.start2_m, mtl_model.start2_m + mtl_model.length_m]

    readout_resonator = add_quarter_wave_resonator!(
        plan;
        id="$(component_id)_readout_resonator",
        grounded_head=readout_grounded_head,
        open_tail=readout_attachment,
        spec=readout_spec,
        breakpoints_m=readout_breakpoints,
        section_overrides=[coupled_line_section_override(mtl_model, 1)],
    )
    filter_resonator = add_quarter_wave_resonator!(
        plan;
        id="$(component_id)_filter_resonator",
        grounded_head=filter_grounded_head,
        open_tail=filter_open_tail,
        spec=filter_spec,
        breakpoints_m=filter_breakpoints,
        section_overrides=[coupled_line_section_override(mtl_model, 2)],
    )
    window = couple_transmission_window!(
        plan;
        id="$(component_id)_mtl_window",
        line1=readout_resonator.line,
        line2=filter_resonator.line,
        start1=mtl_model.start1_m,
        start2=mtl_model.start2_m,
        length=mtl_model.length_m,
        model=mtl_model,
        coupling_orientation=orientation,
    )
    feedline_capacitor = add_interdigitated_capacitor!(
        plan;
        id="$(component_id)_feedline_idc",
        terminal_1=filter_open_tail,
        terminal_2=feedline_attachment,
        c1g_f=numeric[1],
        c2g_f=numeric[2],
        c12_f=numeric[3],
    )
    c0r = c0r_value == 0 ? nothing : shunt_capacitor!(
        plan;
        id="$(component_id)_c0r",
        at=readout_attachment,
        capacitance=c0r_value,
        role=:readout_attachment_ground_capacitance,
        label=raw"$C_{0r}$",
    )
    record_engineering_component!(
        plan;
        id=component_id,
        display_name=component_id,
        component_type=:IntrinsicInterferometricPurcellFilter,
        role=:purcell_filter,
        parameters=Dict(
            :coupling_orientation => orientation,
            :c0r_f => c0r_value,
            :contains_feedline => false,
            :feedline_coupling_kind => :interdigitated_three_branch,
        ),
        pins=[:readout_attachment, :feedline_attachment],
    )
    return IntrinsicInterferometricPurcellFilter(
        component_id,
        readout_resonator,
        filter_resonator,
        window,
        feedline_capacitor,
        c0r,
        readout_attachment,
        feedline_attachment,
    )
end

function _intrinsic_filter_belongs_to_plan(
    plan::CircuitPlan,
    filter::IntrinsicInterferometricPurcellFilter,
)
    ladders = get(plan.metadata, :transmission_line_ladders, nothing)
    ladders isa Dict || return false
    get(ladders, Symbol(filter.readout_resonator.line.id), nothing) ===
        filter.readout_resonator.line || return false
    get(ladders, Symbol(filter.filter_resonator.line.id), nothing) ===
        filter.filter_resonator.line || return false
    windows = get(plan.metadata, :coupled_transmission_windows, nothing)
    windows isa Dict || return false
    get(windows, Symbol(filter.window.id), nothing) === filter.window || return false
    filter.window.line1 === filter.readout_resonator.line || return false
    filter.window.line2 === filter.filter_resonator.line || return false
    filter.readout_resonator.line.tail == filter.readout_attachment || return false
    filter.filter_resonator.line.tail == filter.feedline_capacitor.terminal_1 ||
        return false
    filter.feedline_capacitor.terminal_2 == filter.feedline_attachment || return false
    if !isnothing(filter.c0r)
        filter.c0r.at == filter.readout_attachment || return false
        any(stored -> stored === filter.c0r, plan.relations) || return false
    end
    return all(
        relation -> any(stored -> stored === relation, plan.relations),
        (
            filter.feedline_capacitor.c1g,
            filter.feedline_capacitor.c2g,
            filter.feedline_capacitor.c12,
        ),
    )
end

"""
    add_intrinsic_interferometric_purcell_filter_with_qubit!(plan; id,
        filter, island_1, island_2, c0r_f=nothing, c01_f, c02_f, c12_f, cr1_f,
        cr2_f, l_j_per_junction_h)

Compose an already-built intrinsic filter in the same plan with the existing
linearized floating-qubit component at the filter readout attachment. The
filter owns the local readout-to-ground capacitance. The optional `c0r_f`
argument is a compatibility assertion and must exactly match the filter-owned
value when provided.
"""
function add_intrinsic_interferometric_purcell_filter_with_qubit!(
    plan::CircuitPlan;
    id,
    filter::IntrinsicInterferometricPurcellFilter,
    island_1,
    island_2,
    c0r_f=nothing,
    c01_f,
    c02_f,
    c12_f,
    cr1_f,
    cr2_f,
    l_j_per_junction_h,
)
    component_id = strip(string(id))
    isempty(component_id) &&
        _validation_error("IntrinsicInterferometricPurcellFilterWithQubit id must be nonempty.")
    _intrinsic_filter_belongs_to_plan(plan, filter) ||
        _validation_error("IntrinsicInterferometricPurcellFilter must belong to the supplied CircuitPlan.")
    island_1 isa AbstractNodeEndpoint && island_2 isa AbstractNodeEndpoint ||
        _validation_error("IntrinsicInterferometricPurcellFilterWithQubit islands must be NodeEndpoints.")
    length(Set((island_1, island_2, filter.readout_attachment))) == 3 ||
        _validation_error("Qubit islands and filter readout attachment must be distinct.")
    c0r_value = isnothing(filter.c0r) ? 0.0 : Float64(filter.c0r.capacitance)
    if !isnothing(c0r_f)
        asserted_c0r_value = Float64(c0r_f)
        isfinite(asserted_c0r_value) && asserted_c0r_value >= 0 ||
            _validation_error("c0r_f must be finite and nonnegative.")
        asserted_c0r_value == c0r_value ||
            _validation_error("c0r_f is owned by IntrinsicInterferometricPurcellFilter; pass it when constructing the filter, or omit this compatibility assertion.")
    end

    qubit = add_linearized_floating_qubit!(
        plan;
        id="$(component_id)_qubit",
        island_1=island_1,
        island_2=island_2,
        readout_attachment=filter.readout_attachment,
        c01_f=c01_f,
        c02_f=c02_f,
        c12_f=c12_f,
        cr1_f=cr1_f,
        cr2_f=cr2_f,
        l_j_per_junction_h=l_j_per_junction_h,
    )
    record_engineering_component!(
        plan;
        id=component_id,
        display_name=component_id,
        component_type=:IntrinsicInterferometricPurcellFilterWithQubit,
        role=:qubit_readout_filter_system,
        parameters=Dict(
            :c0r_f => c0r_value,
            :contains_feedline => false,
            :filter_id => filter.id,
            :qubit_id => qubit.id,
        ),
        pins=[:island_1, :island_2, :feedline_attachment],
    )
    return IntrinsicInterferometricPurcellFilterWithQubit(
        component_id,
        filter,
        qubit,
        filter.c0r,
    )
end

function _intrinsic_equivalent_belongs_to_plan(
    plan::CircuitPlan,
    filter::IntrinsicInterferometricPurcellFilterEquivalent,
)
    filter.readout_resonator.node == filter.readout_attachment || return false
    filter.feedline_capacitor.terminal_1 == filter.filter_resonator.node || return false
    filter.feedline_capacitor.terminal_2 == filter.feedline_attachment || return false
    relations = (
        filter.readout_resonator.capacitor,
        filter.readout_resonator.inductor,
        filter.filter_resonator.capacitor,
        filter.filter_resonator.inductor,
        filter.bridge_capacitor,
        filter.bridge_inductor,
        filter.feedline_capacitor.c1g,
        filter.feedline_capacitor.c2g,
        filter.feedline_capacitor.c12,
    )
    all(relation -> any(stored -> stored === relation, plan.relations), relations) ||
        return false
    isnothing(filter.c0r) && return true
    return filter.c0r.at == filter.readout_attachment &&
        any(stored -> stored === filter.c0r, plan.relations)
end

"""
    add_intrinsic_interferometric_purcell_filter_equivalent_with_qubit!(
        plan; id, filter, island_1, island_2, c0r_f=nothing, c01_f, c02_f,
        c12_f, cr1_f, cr2_f, l_j_per_junction_h)

Compose an equivalent intrinsic filter with the existing linearized
floating-qubit component. The equivalent filter owns `C0r`; the optional
`c0r_f` keyword is only a compatibility assertion.
"""
function add_intrinsic_interferometric_purcell_filter_equivalent_with_qubit!(
    plan::CircuitPlan;
    id,
    filter::IntrinsicInterferometricPurcellFilterEquivalent,
    island_1,
    island_2,
    c0r_f=nothing,
    c01_f,
    c02_f,
    c12_f,
    cr1_f,
    cr2_f,
    l_j_per_junction_h,
)
    component_id = strip(string(id))
    isempty(component_id) &&
        _validation_error("IntrinsicInterferometricPurcellFilterEquivalentWithQubit id must be nonempty.")
    _intrinsic_equivalent_belongs_to_plan(plan, filter) ||
        _validation_error("IntrinsicInterferometricPurcellFilterEquivalent must belong to the supplied CircuitPlan.")
    island_1 isa AbstractNodeEndpoint && island_2 isa AbstractNodeEndpoint ||
        _validation_error("IntrinsicInterferometricPurcellFilterEquivalentWithQubit islands must be NodeEndpoints.")
    length(Set((island_1, island_2, filter.readout_attachment))) == 3 ||
        _validation_error("Qubit islands and equivalent-filter readout attachment must be distinct.")
    c0r_value = isnothing(filter.c0r) ? 0.0 : Float64(filter.c0r.capacitance)
    if !isnothing(c0r_f)
        asserted_c0r_value = Float64(c0r_f)
        isfinite(asserted_c0r_value) && asserted_c0r_value >= 0 ||
            _validation_error("c0r_f must be finite and nonnegative.")
        asserted_c0r_value == c0r_value ||
            _validation_error("c0r_f is owned by IntrinsicInterferometricPurcellFilterEquivalent; pass it when constructing the filter, or omit this compatibility assertion.")
    end

    qubit = add_linearized_floating_qubit!(
        plan;
        id="$(component_id)_qubit",
        island_1=island_1,
        island_2=island_2,
        readout_attachment=filter.readout_attachment,
        c01_f=c01_f,
        c02_f=c02_f,
        c12_f=c12_f,
        cr1_f=cr1_f,
        cr2_f=cr2_f,
        l_j_per_junction_h=l_j_per_junction_h,
    )
    record_engineering_component!(
        plan;
        id=component_id,
        display_name=component_id,
        component_type=:IntrinsicInterferometricPurcellFilterEquivalentWithQubit,
        role=:qubit_readout_filter_equivalent_system,
        parameters=Dict(
            :c0r_f => c0r_value,
            :contains_feedline => false,
            :filter_id => filter.id,
            :qubit_id => qubit.id,
        ),
        pins=[:island_1, :island_2, :feedline_attachment],
    )
    return IntrinsicInterferometricPurcellFilterEquivalentWithQubit(
        component_id,
        filter,
        qubit,
        filter.c0r,
    )
end

function add_readout_line_with_purcell_filter!(
    plan::CircuitPlan;
    id,
    input,
    output,
    input_line_spec::RLGCSpec,
    filter_spec::RLGCSpec,
    output_line_spec::RLGCSpec,
    input_coupling_f,
    output_coupling_f,
    filter_breakpoints_m=nothing,
    filter_section_overrides=nothing,
)
    input isa AbstractNodeEndpoint ||
        _validation_error("add_readout_line_with_purcell_filter! requires input to be a NodeEndpoint.")
    output isa AbstractNodeEndpoint ||
        _validation_error("add_readout_line_with_purcell_filter! requires output to be a NodeEndpoint.")
    input_tail = _component_node(id, "input_tail")
    filter_head = _component_node(id, "filter_head")
    filter_tail = _component_node(id, "filter_tail")
    output_head = _component_node(id, "output_head")

    input_line = build_lc_ladder_line!(
        plan;
        id="$(id)_input_line",
        head=input,
        tail=input_tail,
        spec=input_line_spec,
        head_termination=:external,
        tail_termination=:open,
    )
    filter_line = build_lc_ladder_line!(
        plan;
        id="$(id)_purcell_filter",
        head=filter_head,
        tail=filter_tail,
        spec=filter_spec,
        head_termination=:open,
        tail_termination=:open,
        breakpoints_m=filter_breakpoints_m,
        section_overrides=filter_section_overrides,
    )
    output_line = build_lc_ladder_line!(
        plan;
        id="$(id)_output_line",
        head=output_head,
        tail=output,
        spec=output_line_spec,
        head_termination=:open,
        tail_termination=:external,
    )
    input_coupling = couple_capacitive!(
        plan;
        id="$(id)_input_point_coupling",
        from=input_tail,
        to=filter_head,
        capacitance=input_coupling_f,
        role=:purcell_filter_point_coupling,
        label="$(id) input Cc",
    )
    output_coupling = couple_capacitive!(
        plan;
        id="$(id)_output_point_coupling",
        from=filter_tail,
        to=output_head,
        capacitance=output_coupling_f,
        role=:purcell_filter_point_coupling,
        label="$(id) output Cc",
    )
    return ReadoutLineWithPurcellFilter(
        string(id),
        input_line,
        filter_line,
        output_line,
        input_coupling,
        output_coupling,
        input,
        output,
        filter_head,
        filter_tail,
    )
end

function add_readout_purcell_qwr_mtl!(
    plan::CircuitPlan;
    id,
    input,
    output,
    input_line_spec::RLGCSpec,
    filter_spec::RLGCSpec,
    output_line_spec::RLGCSpec,
    qwr_spec::RLGCSpec,
    input_coupling_f,
    output_coupling_f,
    qwr_grounded_head,
    qwr_open_tail,
    mtl_model::MTLCoupledRLGCSpec,
)
    filter_breakpoints = [mtl_model.start1_m, mtl_model.start1_m + mtl_model.length_m]
    qwr_breakpoints = [mtl_model.start2_m, mtl_model.start2_m + mtl_model.length_m]
    readout_filter = add_readout_line_with_purcell_filter!(
        plan;
        id="$(id)_readout_filter",
        input=input,
        output=output,
        input_line_spec=input_line_spec,
        filter_spec=filter_spec,
        output_line_spec=output_line_spec,
        input_coupling_f=input_coupling_f,
        output_coupling_f=output_coupling_f,
        filter_breakpoints_m=filter_breakpoints,
        filter_section_overrides=[coupled_line_section_override(mtl_model, 1)],
    )
    qwr = add_quarter_wave_resonator!(
        plan;
        id="$(id)_qwr",
        grounded_head=qwr_grounded_head,
        open_tail=qwr_open_tail,
        spec=qwr_spec,
        breakpoints_m=qwr_breakpoints,
        section_overrides=[coupled_line_section_override(mtl_model, 2)],
    )
    window = couple_transmission_window!(
        plan;
        id="$(id)_filter_qwr_mtl_window",
        line1=readout_filter.filter_line,
        line2=qwr.line,
        start1=mtl_model.start1_m,
        start2=mtl_model.start2_m,
        length=mtl_model.length_m,
        model=mtl_model,
    )
    return ReadoutPurcellQWRMTL(string(id), readout_filter, qwr, window)
end
