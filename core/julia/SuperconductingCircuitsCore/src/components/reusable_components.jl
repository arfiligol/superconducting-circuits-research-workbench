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
    add_parallel_lc_resonator!(plan; id, node, capacitance, inductance)

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
)
    node isa AbstractNodeEndpoint || _validation_error("add_parallel_lc_resonator! requires node to be a NodeEndpoint.")
    capacitor = shunt_capacitor!(
        plan;
        id="$(id)_capacitance",
        at=node,
        capacitance=capacitance,
        role=:parallel_lc_capacitance,
        label=raw"$C_r$",
    )
    inductor = shunt_inductor!(
        plan;
        id="$(id)_inductance",
        at=node,
        inductance=inductance,
        role=:parallel_lc_inductance,
        label=raw"$L_r$",
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
