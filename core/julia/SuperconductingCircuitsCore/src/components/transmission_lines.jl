struct TransmissionLineSpec
    length_m::Float64
    section_length_m::Float64
    n_sections::Int
    l_per_m_h::Float64
    c_per_m_f::Float64
    r_per_m_ohm::Float64
    g_per_m_s::Float64
end

struct TransmissionLineLadder
    id::String
    spec::TransmissionLineSpec
    nodes::Vector{AbstractNodeEndpoint}
    series_inductors::Vector{SeriesInductor}
    series_resistors::Vector{SeriesResistor}
    shunt_capacitors::Vector{ShuntCapacitor}
    shunt_conductance_resistors::Vector{SeriesResistor}
    head::AbstractNodeEndpoint
    tail::AbstractNodeEndpoint
    section_length_m::Float64
    head_termination::Symbol
    tail_termination::Symbol
    termination_relations::Vector{AbstractCircuitRelation}
end

struct MTLCoupledWindowSpec
    start1_m::Float64
    start2_m::Float64
    length_m::Float64
    section_length_m::Float64
    c12_per_m_f::Float64
    lm_per_m_h::Float64
    l1_per_m_h::Float64
    l2_per_m_h::Float64
    c1g_per_m_f::Float64
    c2g_per_m_f::Float64
end

struct CoupledTransmissionWindow
    id::String
    line1::TransmissionLineLadder
    line2::TransmissionLineLadder
    section_range1::UnitRange{Int}
    section_range2::UnitRange{Int}
    capacitive_couplings::Vector{CapacitiveCoupling}
    inductive_couplings::Vector{MutualInductiveCoupling}
    model::MTLCoupledWindowSpec
end

const _LADDER_GROUNDED_TERMINATIONS = Set([:short, :ground, :grounded])
const _LADDER_OPEN_TERMINATIONS = Set([:open, :external])

function _selected_keyword(primary, alias, name::AbstractString)
    if !isnothing(primary) && !isnothing(alias)
        Float64(primary) ≈ Float64(alias) ||
            _validation_error("TransmissionLineSpec received conflicting $(name) keyword aliases.")
    end
    return isnothing(primary) ? alias : primary
end

function _section_count_from_length(length_m::Real, section_length_m::Real)
    length = Float64(length_m)
    section_length = Float64(section_length_m)
    section_length > 0 || _validation_error("section_length_m must be positive.")
    raw = length / section_length
    count = round(Int, raw)
    count > 0 || _validation_error("Transmission line must contain at least one section.")
    isapprox(raw, count; atol=1e-9, rtol=1e-9) ||
        _validation_error("Transmission line length must align to section_length_m; partial sections are not rounded.")
    return count
end

function TransmissionLineSpec(;
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
    isnothing(selected_length) && _validation_error("TransmissionLineSpec requires length_m or length.")
    selected_l = _selected_keyword(l_per_m_h, l_per_m, "l_per_m")
    selected_c = _selected_keyword(c_per_m_f, c_per_m, "c_per_m")
    isnothing(selected_l) && _validation_error("TransmissionLineSpec requires l_per_m_h or l_per_m.")
    isnothing(selected_c) && _validation_error("TransmissionLineSpec requires c_per_m_f or c_per_m.")
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

    section_length_value = _selected_keyword(section_length_m, section_length, "section_length")
    if isnothing(section_length_value) && isnothing(n_sections)
        _validation_error("TransmissionLineSpec requires section_length_m/section_length or n_sections.")
    elseif isnothing(section_length_value)
        count = Int(n_sections)
        count > 0 || _validation_error("n_sections must be positive.")
        section_length_value = length_value / count
    elseif isnothing(n_sections)
        count = _section_count_from_length(length_value, section_length_value)
    else
        count = Int(n_sections)
        count > 0 || _validation_error("n_sections must be positive.")
        inferred = length_value / count
        isapprox(Float64(section_length_value), inferred; atol=1e-12, rtol=1e-9) ||
            _validation_error("section_length_m must equal length_m / n_sections when both are provided.")
    end

    return TransmissionLineSpec(
        length_value,
        Float64(section_length_value),
        count,
        l_value,
        c_value,
        r_value,
        g_value,
    )
end

function TransmissionLineSpec(length, section_length, l_per_m, c_per_m; r_per_m=0.0, g_per_m=0.0)
    return TransmissionLineSpec(
        length=length,
        section_length=section_length,
        l_per_m=l_per_m,
        c_per_m=c_per_m,
        r_per_m=r_per_m,
        g_per_m=g_per_m,
    )
end

TransmissionLineSpec(spec::RLGCSpec) = TransmissionLineSpec(
    length_m=spec.length_m,
    n_sections=spec.n_sections,
    l_per_m_h=spec.l_per_m_h,
    c_per_m_f=spec.c_per_m_f,
    r_per_m_ohm=spec.r_per_m_ohm,
    g_per_m_s=spec.g_per_m_s,
)

function section_values(spec::TransmissionLineSpec)
    return (
        dx_m=spec.section_length_m,
        r_ohm=spec.r_per_m_ohm * spec.section_length_m,
        l_h=spec.l_per_m_h * spec.section_length_m,
        g_s=spec.g_per_m_s * spec.section_length_m,
        c_f=spec.c_per_m_f * spec.section_length_m,
    )
end

phase_velocity(spec::TransmissionLineSpec) = 1 / sqrt(spec.l_per_m_h * spec.c_per_m_f)

function _validate_ladder_termination(value)
    termination = Symbol(value)
    termination in _LADDER_OPEN_TERMINATIONS || termination in _LADDER_GROUNDED_TERMINATIONS ||
        _validation_error("Unsupported transmission-line termination '$(value)'. Use :external, :open, :short, or :grounded.")
    return termination
end

function _ladder_internal_node(id::AbstractString, index::Int)
    return external_node("$(id)_node_$(index)")
end

function _ladder_nodes(id::AbstractString, head::AbstractNodeEndpoint, tail::AbstractNodeEndpoint, n_sections::Int)
    nodes = AbstractNodeEndpoint[head]
    for index in 1:(n_sections - 1)
        push!(nodes, _ladder_internal_node(id, index))
    end
    push!(nodes, tail)
    return nodes
end

function _record_transmission_line_ladder!(plan::CircuitPlan, ladder::TransmissionLineLadder)
    record_engineering_relation!(
        plan;
        id="$(ladder.id)_ladder",
        relation_type=:transmission_line_ladder,
        from=ladder.head,
        to=ladder.tail,
        through=Symbol(ladder.id),
        role=:transmission_line_ladder,
        label=ladder.id,
        parameters=Dict{Symbol,Any}(
            :length_m => ladder.spec.length_m,
            :section_length_m => ladder.section_length_m,
            :n_sections => ladder.spec.n_sections,
            :l_per_m_h => ladder.spec.l_per_m_h,
            :c_per_m_f => ladder.spec.c_per_m_f,
            :r_per_m_ohm => ladder.spec.r_per_m_ohm,
            :g_per_m_s => ladder.spec.g_per_m_s,
            :head_termination => ladder.head_termination,
            :tail_termination => ladder.tail_termination,
        ),
    )
end

function _store_ladder!(plan::CircuitPlan, ladder::TransmissionLineLadder)
    ladders = get!(plan.metadata, :transmission_line_ladders) do
        Dict{Symbol,TransmissionLineLadder}()
    end
    ladders isa Dict{Symbol,TransmissionLineLadder} ||
        _validation_error("CircuitPlan metadata[:transmission_line_ladders] is reserved for TransmissionLineLadder records.")
    key = Symbol(ladder.id)
    haskey(ladders, key) && _validation_error("Duplicate transmission-line ladder id '$(ladder.id)'.")
    ladders[key] = ladder
    return ladder
end

function _grounded_termination_relation!(plan::CircuitPlan, id, endpoint, side::Symbol, termination::Symbol)
    termination in _LADDER_GROUNDED_TERMINATIONS || return nothing
    return connect!(
        plan,
        endpoint,
        ground();
        role=Symbol(side, :_termination),
        label="$(id) $(side) $(termination)",
        schematic_kind=:short_to_ground,
    )
end

function build_lc_ladder_line!(
    plan::CircuitPlan;
    id,
    head,
    tail,
    spec::TransmissionLineSpec,
    head_termination=:external,
    tail_termination=:open,
)
    head isa AbstractNodeEndpoint && tail isa AbstractNodeEndpoint ||
        _validation_error("build_lc_ladder_line! requires node-resolving head and tail endpoints.")
    head_term = _validate_ladder_termination(head_termination)
    tail_term = _validate_ladder_termination(tail_termination)
    values = section_values(spec)
    nodes = _ladder_nodes(string(id), head, tail, spec.n_sections)
    series_inductors = SeriesInductor[]
    series_resistors = SeriesResistor[]
    shunt_capacitors = ShuntCapacitor[]
    shunt_conductance_resistors = SeriesResistor[]
    termination_relations = AbstractCircuitRelation[]

    head_short = _grounded_termination_relation!(plan, id, head, :head, head_term)
    !isnothing(head_short) && push!(termination_relations, head_short)

    for section in 1:spec.n_sections
        from_node = nodes[section]
        to_node = nodes[section + 1]
        if values.r_ohm > 0
            mid_node = external_node("$(id)_section_$(section)_series_mid")
            resistor = series_resistor!(
                plan;
                id="$(id)_r_$(section)",
                from=from_node,
                to=mid_node,
                resistance=values.r_ohm,
                role=:transmission_line_series_resistance,
                label="$(id) R$(section)",
            )
            push!(series_resistors, resistor)
            from_node = mid_node
        end

        inductor = series_inductor!(
            plan;
            id="$(id)_l_$(section)",
            from=from_node,
            to=to_node,
            inductance=values.l_h,
            role=:transmission_line_series_inductance,
            label="$(id) L$(section)",
        )
        push!(series_inductors, inductor)

        terminal_is_grounded_tail = section == spec.n_sections && tail_term in _LADDER_GROUNDED_TERMINATIONS
        if !terminal_is_grounded_tail
            capacitor = shunt_capacitor!(
                plan;
                id="$(id)_c_$(section)",
                at=to_node,
                capacitance=values.c_f,
                role=:transmission_line_shunt_capacitance,
                label="$(id) C$(section)",
            )
            push!(shunt_capacitors, capacitor)
        end

        if values.g_s > 0 && !terminal_is_grounded_tail
            conductance = series_resistor!(
                plan;
                id="$(id)_g_$(section)",
                from=to_node,
                to=ground(),
                resistance=1 / values.g_s,
                role=:transmission_line_shunt_conductance,
                label="$(id) G$(section)",
            )
            push!(shunt_conductance_resistors, conductance)
        end
    end

    tail_short = _grounded_termination_relation!(plan, id, tail, :tail, tail_term)
    !isnothing(tail_short) && push!(termination_relations, tail_short)

    ladder = TransmissionLineLadder(
        string(id),
        spec,
        nodes,
        series_inductors,
        series_resistors,
        shunt_capacitors,
        shunt_conductance_resistors,
        head,
        tail,
        spec.section_length_m,
        head_term,
        tail_term,
        termination_relations,
    )
    _record_transmission_line_ladder!(plan, ladder)
    return _store_ladder!(plan, ladder)
end

function _aligned_index(distance_m::Real, section_length_m::Real, label::AbstractString)
    distance = Float64(distance_m)
    distance >= 0 || _validation_error("$(label) must be non-negative.")
    raw = distance / Float64(section_length_m)
    index = round(Int, raw)
    isapprox(raw, index; atol=1e-9, rtol=1e-9) ||
        _validation_error("$(label) must align to section boundaries; partial sections are not supported.")
    return index
end

function node_at_distance(ladder::TransmissionLineLadder, distance_m::Real)
    node_index = _aligned_index(distance_m, ladder.section_length_m, "distance from head")
    0 <= node_index <= ladder.spec.n_sections ||
        _validation_error("distance from head is outside transmission line '$(ladder.id)'.")
    return ladder.nodes[node_index + 1]
end

function section_index_at_distance(ladder::TransmissionLineLadder, distance_m::Real)
    section_start_index = _aligned_index(distance_m, ladder.section_length_m, "distance from head")
    0 <= section_start_index < ladder.spec.n_sections ||
        _validation_error("distance from head must identify a section start inside transmission line '$(ladder.id)'.")
    return section_start_index + 1
end

function section_range_from_window(ladder::TransmissionLineLadder, start_m::Real, length_m::Real)
    length = Float64(length_m)
    length > 0 || _validation_error("coupling window length must be positive.")
    start_section = section_index_at_distance(ladder, start_m)
    section_count = _aligned_index(length, ladder.section_length_m, "coupling window length")
    section_count > 0 || _validation_error("coupling window must cover at least one section.")
    stop_section = start_section + section_count - 1
    stop_section <= ladder.spec.n_sections ||
        _validation_error("coupling window extends past transmission line '$(ladder.id)'.")
    return start_section:stop_section
end

function MTLCoupledWindowSpec(;
    start1=nothing,
    start1_m=nothing,
    start2=nothing,
    start2_m=nothing,
    length=nothing,
    length_m=nothing,
    section_length=nothing,
    section_length_m=nothing,
    c12_per_m=nothing,
    c12_per_m_f=nothing,
    lm_per_m=nothing,
    lm_per_m_h=nothing,
    l1_per_m=nothing,
    l1_per_m_h=nothing,
    l2_per_m=nothing,
    l2_per_m_h=nothing,
    c1g_per_m=nothing,
    c1g_per_m_f=nothing,
    c2g_per_m=nothing,
    c2g_per_m_f=nothing,
)
    selected_start1 = something(_selected_keyword(start1_m, start1, "start1"), 0.0)
    selected_start2 = something(_selected_keyword(start2_m, start2, "start2"), 0.0)
    selected_length = _selected_keyword(length_m, length, "length")
    selected_section_length = _selected_keyword(section_length_m, section_length, "section_length")
    selected_c12 = _selected_keyword(c12_per_m_f, c12_per_m, "c12_per_m")
    selected_lm = _selected_keyword(lm_per_m_h, lm_per_m, "lm_per_m")
    selected_l1 = _selected_keyword(l1_per_m_h, l1_per_m, "l1_per_m")
    selected_l2 = _selected_keyword(l2_per_m_h, l2_per_m, "l2_per_m")
    selected_c1g = _selected_keyword(c1g_per_m_f, c1g_per_m, "c1g_per_m")
    selected_c2g = _selected_keyword(c2g_per_m_f, c2g_per_m, "c2g_per_m")

    any(isnothing, (selected_length, selected_section_length, selected_c12, selected_lm, selected_l1, selected_l2, selected_c1g, selected_c2g)) &&
        _validation_error("MTLCoupledWindowSpec requires length, section_length, c12_per_m, lm_per_m, l1_per_m, l2_per_m, c1g_per_m, and c2g_per_m.")

    spec = MTLCoupledWindowSpec(
        Float64(selected_start1),
        Float64(selected_start2),
        Float64(selected_length),
        Float64(selected_section_length),
        Float64(selected_c12),
        Float64(selected_lm),
        Float64(selected_l1),
        Float64(selected_l2),
        Float64(selected_c1g),
        Float64(selected_c2g),
    )
    _validate_mtl_coupled_window_spec(spec)
    return spec
end

function _validate_mtl_coupled_window_spec(spec::MTLCoupledWindowSpec)
    spec.start1_m >= 0 || _validation_error("start1_m must be non-negative.")
    spec.start2_m >= 0 || _validation_error("start2_m must be non-negative.")
    spec.length_m > 0 || _validation_error("length_m must be positive.")
    spec.section_length_m > 0 || _validation_error("section_length_m must be positive.")
    spec.c12_per_m_f >= 0 || _validation_error("c12_per_m_f must be non-negative.")
    spec.l1_per_m_h > 0 || _validation_error("l1_per_m_h must be positive.")
    spec.l2_per_m_h > 0 || _validation_error("l2_per_m_h must be positive.")
    spec.c1g_per_m_f > 0 || _validation_error("c1g_per_m_f must be positive.")
    spec.c2g_per_m_f > 0 || _validation_error("c2g_per_m_f must be positive.")
    abs(spec.lm_per_m_h) < sqrt(spec.l1_per_m_h * spec.l2_per_m_h) ||
        _validation_error("abs(lm_per_m_h) must be less than sqrt(l1_per_m_h * l2_per_m_h).")
    _aligned_index(spec.length_m, spec.section_length_m, "coupled window length")
    return nothing
end

function _select_window_value(argument_value, model_value, name::AbstractString)
    if isnothing(argument_value)
        return model_value
    end
    selected = Float64(argument_value)
    isapprox(selected, model_value; atol=1e-12, rtol=1e-9) ||
        _validation_error("couple_transmission_window! $(name) conflicts with MTLCoupledWindowSpec.")
    return selected
end

function _validate_window_line_model(line1::TransmissionLineLadder, line2::TransmissionLineLadder, model::MTLCoupledWindowSpec)
    isapprox(line1.section_length_m, line2.section_length_m; atol=1e-12, rtol=1e-9) ||
        _validation_error("Coupled transmission lines must use compatible section_length_m.")
    isapprox(line1.section_length_m, model.section_length_m; atol=1e-12, rtol=1e-9) ||
        _validation_error("MTLCoupledWindowSpec section_length_m must match line section_length_m.")
    isapprox(line1.spec.l_per_m_h, model.l1_per_m_h; atol=0.0, rtol=1e-9) ||
        _validation_error("MTLCoupledWindowSpec l1_per_m_h must match line1 l_per_m_h.")
    isapprox(line2.spec.l_per_m_h, model.l2_per_m_h; atol=0.0, rtol=1e-9) ||
        _validation_error("MTLCoupledWindowSpec l2_per_m_h must match line2 l_per_m_h.")
    isapprox(line1.spec.c_per_m_f, model.c1g_per_m_f; atol=0.0, rtol=1e-9) ||
        _validation_error("MTLCoupledWindowSpec c1g_per_m_f must match line1 c_per_m_f.")
    isapprox(line2.spec.c_per_m_f, model.c2g_per_m_f; atol=0.0, rtol=1e-9) ||
        _validation_error("MTLCoupledWindowSpec c2g_per_m_f must match line2 c_per_m_f.")
end

function couple_transmission_window!(
    plan::CircuitPlan;
    id,
    line1,
    line2,
    start1=nothing,
    start2=nothing,
    length=nothing,
    model::MTLCoupledWindowSpec,
)
    line1 isa TransmissionLineLadder && line2 isa TransmissionLineLadder ||
        _validation_error("couple_transmission_window! requires TransmissionLineLadder line1 and line2.")
    _validate_mtl_coupled_window_spec(model)
    _validate_window_line_model(line1, line2, model)

    start1_m = _select_window_value(start1, model.start1_m, "start1")
    start2_m = _select_window_value(start2, model.start2_m, "start2")
    length_m = _select_window_value(length, model.length_m, "length")
    range1 = section_range_from_window(line1, start1_m, length_m)
    range2 = section_range_from_window(line2, start2_m, length_m)
    Base.length(range1) == Base.length(range2) ||
        _validation_error("Coupled section ranges must have the same section count.")

    c12 = model.c12_per_m_f * line1.section_length_m
    lm = model.lm_per_m_h * line1.section_length_m
    capacitive_couplings = CapacitiveCoupling[]
    inductive_couplings = MutualInductiveCoupling[]

    for (offset, (section1, section2)) in enumerate(zip(range1, range2))
        if c12 > 0
            push!(
                capacitive_couplings,
                couple_capacitive!(
                    plan;
                    id="$(id)_c12_$(offset)",
                    from=line1.nodes[section1 + 1],
                    to=line2.nodes[section2 + 1],
                    capacitance=c12,
                    role=:coupled_window_mutual_capacitance,
                    label="$(id) C12 $(offset)",
                ),
            )
        end
        push!(
            inductive_couplings,
            couple_inductive!(
                plan;
                id="$(id)_m12_$(offset)",
                inductor_a=line1.series_inductors[section1],
                inductor_b=line2.series_inductors[section2],
                mutual_inductance=lm,
                role=:coupled_window_mutual_inductance,
                label="$(id) M12 $(offset)",
            ),
        )
    end

    window = CoupledTransmissionWindow(
        string(id),
        line1,
        line2,
        range1,
        range2,
        capacitive_couplings,
        inductive_couplings,
        model,
    )

    record_engineering_relation!(
        plan;
        id=id,
        relation_type=:coupled_window,
        from=(line=line1.id, sections=range1),
        to=(line=line2.id, sections=range2),
        through=model,
        role=:coupled_window,
        label=string(id),
        parameters=Dict{Symbol,Any}(
            :start1_m => start1_m,
            :start2_m => start2_m,
            :length_m => length_m,
            :section_count => Base.length(range1),
            :section_length_m => model.section_length_m,
            :c12_per_m_f => model.c12_per_m_f,
            :lm_per_m_h => model.lm_per_m_h,
            :l1_per_m_h => model.l1_per_m_h,
            :l2_per_m_h => model.l2_per_m_h,
            :c1g_per_m_f => model.c1g_per_m_f,
            :c2g_per_m_f => model.c2g_per_m_f,
        ),
    )

    windows = get!(plan.metadata, :coupled_transmission_windows) do
        Dict{Symbol,CoupledTransmissionWindow}()
    end
    windows isa Dict{Symbol,CoupledTransmissionWindow} ||
        _validation_error("CircuitPlan metadata[:coupled_transmission_windows] is reserved for CoupledTransmissionWindow records.")
    key = Symbol(window.id)
    haskey(windows, key) && _validation_error("Duplicate coupled transmission window id '$(window.id)'.")
    windows[key] = window
    return window
end
