struct NodeConnection <: AbstractCircuitRelation
    a::AbstractNodeEndpoint
    b::AbstractNodeEndpoint
end

struct CapacitiveCoupling <: AbstractCircuitRelation
    id::String
    from::AbstractNodeEndpoint
    to::AbstractNodeEndpoint
    capacitance::Any
    parameters::Vector{ParameterMetadata}
end

struct ShuntCapacitor <: AbstractCircuitRelation
    id::String
    at::AbstractNodeEndpoint
    capacitance::Any
    parameters::Vector{ParameterMetadata}
end

struct ShuntInductor <: AbstractCircuitRelation
    id::String
    at::AbstractNodeEndpoint
    inductance::Any
    parameters::Vector{ParameterMetadata}
end

struct SeriesInductor <: AbstractCircuitRelation
    id::String
    from::AbstractNodeEndpoint
    to::AbstractNodeEndpoint
    inductance::Any
    parameters::Vector{ParameterMetadata}
end

struct SeriesResistor <: AbstractCircuitRelation
    id::String
    from::AbstractNodeEndpoint
    to::AbstractNodeEndpoint
    resistance::Any
    parameters::Vector{ParameterMetadata}
end

struct InductiveCoupling <: AbstractCircuitRelation
    id::String
    from::AbstractCircuitEndpoint
    to::AbstractCircuitEndpoint
    mutual_inductance::Any
    parameters::Vector{ParameterMetadata}
end

struct MutualInductiveCoupling <: AbstractCircuitRelation
    id::String
    inductor_a::SeriesInductor
    inductor_b::SeriesInductor
    mutual_inductance::Any
    coupling_coefficient::Any
    parameters::Vector{ParameterMetadata}
end

struct CoupledWindowRelation <: AbstractCircuitRelation
    id::String
    line_a::LineSpanEndpoint
    line_b::LineSpanEndpoint
    spec::Any
    parameters::Vector{ParameterMetadata}
end

function _parameter_vector(parameters)
    return ParameterMetadata[meta for meta in parameters]
end

function _register_relation_parameters!(plan::CircuitPlan, parameters)
    for meta in parameters
        register_parameter!(plan, meta)
    end
end

function _engineering_label(label, default="")
    return isnothing(label) ? string(default) : string(label)
end

function _engineering_relation_parameters(value_name::Symbol, value, parameters; schematic_kind=nothing)
    result = Dict{Symbol,Any}(value_name => value)
    if !isempty(parameters)
        result[:parameters] = parameters
    end
    if !isnothing(schematic_kind)
        result[:schematic_kind] = schematic_kind
    end
    return result
end

function _recorded_external_port_node(plan::CircuitPlan, endpoint)
    return false
end

function _recorded_external_port_node(plan::CircuitPlan, endpoint::ExternalNodeEndpoint)
    return haskey(engineering_graph(plan).ports, Symbol(endpoint.name))
end

function _connect_engineering_relation_is_meaningful(plan::CircuitPlan, a::AbstractNodeEndpoint, b::AbstractNodeEndpoint)
    return !_recorded_external_port_node(plan, a) && !_recorded_external_port_node(plan, b)
end

function connect!(
    plan::CircuitPlan,
    a::AbstractNodeEndpoint,
    b::AbstractNodeEndpoint;
    role=:node_connection,
    label=nothing,
    schematic_kind=:node_connection,
    source_location=nothing,
)
    relation = NodeConnection(a, b)
    push!(plan.relations, relation)
    if _connect_engineering_relation_is_meaningful(plan, a, b)
        record_engineering_relation!(
            plan;
            relation_type=:connect,
            from=a,
            to=b,
            role=role,
            label=_engineering_label(label),
            parameters=Dict{Symbol,Any}(:schematic_kind => schematic_kind),
            source_location=source_location,
        )
    end
    return relation
end

function connect!(plan::CircuitPlan, a::AbstractCircuitEndpoint, b::AbstractCircuitEndpoint; kwargs...)
    _validation_error("connect! requires NodeEndpoint <-> NodeEndpoint.")
end

function couple_capacitive!(
    plan::CircuitPlan;
    id,
    from,
    to,
    capacitance,
    parameters=ParameterMetadata[],
    role=:capacitive_coupling,
    label=nothing,
    schematic_kind=:capacitive_coupling,
    source_location=nothing,
)
    from isa AbstractNodeEndpoint && to isa AbstractNodeEndpoint ||
        _validation_error("couple_capacitive! requires NodeEndpoint <-> NodeEndpoint.")
    params = _parameter_vector(parameters)
    relation = CapacitiveCoupling(String(id), from, to, capacitance, params)
    push!(plan.relations, relation)
    _register_relation_parameters!(plan, params)
    record_engineering_relation!(
        plan;
        id=relation.id,
        relation_type=:couple,
        from=from,
        to=to,
        through=Symbol(relation.id),
        role=role,
        label=_engineering_label(label),
        parameters=_engineering_relation_parameters(
            :capacitance,
            capacitance,
            params;
            schematic_kind=schematic_kind,
        ),
        source_location=source_location,
    )
    return relation
end

function shunt_capacitor!(
    plan::CircuitPlan;
    id,
    at,
    capacitance,
    parameters=ParameterMetadata[],
    role=:shunt_capacitor,
    label=nothing,
    schematic_kind=:capacitor,
    source_location=nothing,
)
    at isa AbstractNodeEndpoint || _validation_error("shunt_capacitor! requires a NodeEndpoint.")
    params = _parameter_vector(parameters)
    relation = ShuntCapacitor(String(id), at, capacitance, params)
    push!(plan.relations, relation)
    _register_relation_parameters!(plan, params)
    record_engineering_relation!(
        plan;
        id=relation.id,
        relation_type=:terminates,
        from=at,
        to=ground(),
        through=:capacitance,
        role=role,
        label=_engineering_label(label),
        parameters=_engineering_relation_parameters(
            :capacitance,
            capacitance,
            params;
            schematic_kind=schematic_kind,
        ),
        source_location=source_location,
    )
    return relation
end

function shunt_inductor!(
    plan::CircuitPlan;
    id,
    at,
    inductance,
    parameters=ParameterMetadata[],
    role=:shunt_inductor,
    label=nothing,
    schematic_kind=:inductor,
    source_location=nothing,
)
    at isa AbstractNodeEndpoint || _validation_error("shunt_inductor! requires a NodeEndpoint.")
    params = _parameter_vector(parameters)
    relation = ShuntInductor(String(id), at, inductance, params)
    push!(plan.relations, relation)
    _register_relation_parameters!(plan, params)
    record_engineering_relation!(
        plan;
        id=relation.id,
        relation_type=:terminates,
        from=at,
        to=ground(),
        through=:inductance,
        role=role,
        label=_engineering_label(label),
        parameters=_engineering_relation_parameters(
            :inductance,
            inductance,
            params;
            schematic_kind=schematic_kind,
        ),
        source_location=source_location,
    )
    return relation
end

function series_inductor!(
    plan::CircuitPlan;
    id,
    from,
    to,
    inductance,
    parameters=ParameterMetadata[],
    role=:series_inductor,
    label=nothing,
    schematic_kind=:inductor,
    source_location=nothing,
)
    from isa AbstractNodeEndpoint && to isa AbstractNodeEndpoint ||
        _validation_error("series_inductor! requires NodeEndpoint <-> NodeEndpoint.")
    params = _parameter_vector(parameters)
    relation = SeriesInductor(String(id), from, to, inductance, params)
    push!(plan.relations, relation)
    _register_relation_parameters!(plan, params)
    record_engineering_relation!(
        plan;
        id=relation.id,
        relation_type=:series,
        from=from,
        to=to,
        through=:inductance,
        role=role,
        label=_engineering_label(label),
        parameters=_engineering_relation_parameters(
            :inductance,
            inductance,
            params;
            schematic_kind=schematic_kind,
        ),
        source_location=source_location,
    )
    return relation
end

function series_resistor!(
    plan::CircuitPlan;
    id,
    from,
    to,
    resistance,
    parameters=ParameterMetadata[],
    role=:series_resistor,
    label=nothing,
    schematic_kind=:resistor,
    source_location=nothing,
)
    from isa AbstractNodeEndpoint && to isa AbstractNodeEndpoint ||
        _validation_error("series_resistor! requires NodeEndpoint <-> NodeEndpoint.")
    params = _parameter_vector(parameters)
    relation = SeriesResistor(String(id), from, to, resistance, params)
    push!(plan.relations, relation)
    _register_relation_parameters!(plan, params)
    record_engineering_relation!(
        plan;
        id=relation.id,
        relation_type=:series,
        from=from,
        to=to,
        through=:resistance,
        role=role,
        label=_engineering_label(label),
        parameters=_engineering_relation_parameters(
            :resistance,
            resistance,
            params;
            schematic_kind=schematic_kind,
        ),
        source_location=source_location,
    )
    return relation
end

function couple_inductive!(
    plan::CircuitPlan;
    id,
    from=nothing,
    to=nothing,
    inductor_a=nothing,
    inductor_b=nothing,
    mutual_inductance=nothing,
    coupling_coefficient=nothing,
    parameters=ParameterMetadata[],
    role=:inductive_coupling,
    label=nothing,
    schematic_kind=:inductive_coupling,
    source_location=nothing,
)
    if !isnothing(inductor_a) || !isnothing(inductor_b)
        isnothing(from) && isnothing(to) ||
            _validation_error("Branch mutual inductive coupling uses inductor_a/inductor_b, not from/to endpoints.")
        return _couple_branch_inductive!(
            plan;
            id=id,
            inductor_a=inductor_a,
            inductor_b=inductor_b,
            mutual_inductance=mutual_inductance,
            coupling_coefficient=coupling_coefficient,
            parameters=parameters,
            role=role,
            label=label,
            schematic_kind=schematic_kind,
            source_location=source_location,
        )
    end

    !isnothing(from) && !isnothing(to) ||
        _validation_error("couple_inductive! requires either from/to endpoints or inductor_a/inductor_b branches.")
    !isnothing(mutual_inductance) ||
        _validation_error("Endpoint inductive coupling requires mutual_inductance.")
    isnothing(coupling_coefficient) ||
        _validation_error("Endpoint inductive coupling currently accepts mutual_inductance, not coupling_coefficient.")

    line_like = Union{LineTapEndpoint,LineSpanEndpoint}
    source = from
    target = to
    if from isa AbstractLoopEndpoint && to isa line_like
        source = to
        target = from
    elseif !(from isa line_like && to isa AbstractLoopEndpoint)
        _validation_error("couple_inductive! requires LineTapEndpoint or LineSpanEndpoint <-> LoopEndpoint.")
    end

    params = _parameter_vector(parameters)
    relation = InductiveCoupling(String(id), source, target, mutual_inductance, params)
    push!(plan.relations, relation)
    _register_relation_parameters!(plan, params)
    record_engineering_relation!(
        plan;
        id=relation.id,
        relation_type=:couple,
        from=source,
        to=target,
        through=Symbol(relation.id),
        role=role,
        label=_engineering_label(label),
        parameters=_engineering_relation_parameters(
            :mutual_inductance,
            mutual_inductance,
            params;
            schematic_kind=schematic_kind,
        ),
        source_location=source_location,
    )
    return relation
end

function _numeric_series_inductance(inductor::SeriesInductor, label::AbstractString)
    value = inductor.inductance
    value isa Number ||
        _validation_error("$(label) inductance must be numeric to derive mutual coupling coefficient.")
    Float64(value) > 0 ||
        _validation_error("$(label) inductance must be positive to derive mutual coupling coefficient.")
    return Float64(value)
end

function _branch_mutual_values(inductor_a::SeriesInductor, inductor_b::SeriesInductor, mutual_inductance, coupling_coefficient)
    provided_m = !isnothing(mutual_inductance)
    provided_k = !isnothing(coupling_coefficient)
    xor(provided_m, provided_k) ||
        _validation_error("Branch mutual inductive coupling requires exactly one of mutual_inductance or coupling_coefficient.")

    l1 = _numeric_series_inductance(inductor_a, "inductor_a")
    l2 = _numeric_series_inductance(inductor_b, "inductor_b")
    limit = sqrt(l1 * l2)

    if provided_k
        k = Float64(coupling_coefficient)
        -1 < k < 1 ||
            _validation_error("coupling_coefficient must satisfy -1 < k < 1.")
        return (mutual_inductance=k * limit, coupling_coefficient=k)
    end

    m = Float64(mutual_inductance)
    abs(m) < limit ||
        _validation_error("abs(mutual_inductance) must be less than sqrt(L1 * L2).")
    return (mutual_inductance=m, coupling_coefficient=m / limit)
end

function _couple_branch_inductive!(
    plan::CircuitPlan;
    id,
    inductor_a,
    inductor_b,
    mutual_inductance,
    coupling_coefficient,
    parameters=ParameterMetadata[],
    role=:inductive_coupling,
    label=nothing,
    schematic_kind=:inductive_coupling,
    source_location=nothing,
)
    inductor_a isa SeriesInductor && inductor_b isa SeriesInductor ||
        _validation_error("Branch mutual inductive coupling requires SeriesInductor inductor_a and inductor_b.")
    values = _branch_mutual_values(inductor_a, inductor_b, mutual_inductance, coupling_coefficient)
    params = _parameter_vector(parameters)
    relation = MutualInductiveCoupling(
        String(id),
        inductor_a,
        inductor_b,
        values.mutual_inductance,
        values.coupling_coefficient,
        params,
    )
    push!(plan.relations, relation)
    _register_relation_parameters!(plan, params)
    graph_parameters = _engineering_relation_parameters(
        :mutual_inductance,
        values.mutual_inductance,
        params;
        schematic_kind=schematic_kind,
    )
    graph_parameters[:coupling_coefficient] = values.coupling_coefficient
    graph_parameters[:inductor_a] = inductor_a.id
    graph_parameters[:inductor_b] = inductor_b.id
    record_engineering_relation!(
        plan;
        id=relation.id,
        relation_type=:couple,
        from=Symbol(inductor_a.id),
        to=Symbol(inductor_b.id),
        through=Symbol(relation.id),
        role=role,
        label=_engineering_label(label),
        parameters=graph_parameters,
        source_location=source_location,
    )
    return relation
end

function couple_window!(
    plan::CircuitPlan;
    id,
    line_a,
    line_b,
    spec,
    parameters=ParameterMetadata[],
    role=:coupled_window,
    label=nothing,
    schematic_kind=:coupled_window,
    source_location=nothing,
)
    line_a isa LineSpanEndpoint && line_b isa LineSpanEndpoint ||
        _validation_error("couple_window! requires LineSpanEndpoint <-> LineSpanEndpoint.")
    params = _parameter_vector(parameters)
    relation = CoupledWindowRelation(String(id), line_a, line_b, spec, params)
    push!(plan.relations, relation)
    _register_relation_parameters!(plan, params)
    record_engineering_relation!(
        plan;
        id=relation.id,
        relation_type=:couple,
        from=line_a,
        to=line_b,
        through=:coupled_window,
        role=role,
        label=_engineering_label(label),
        parameters=_engineering_relation_parameters(
            :spec,
            spec,
            params;
            schematic_kind=schematic_kind,
        ),
        source_location=source_location,
    )
    return relation
end

function _relation_id(relation::AbstractCircuitRelation)
    return hasproperty(relation, :id) ? getproperty(relation, :id) : nothing
end

function relation_parameters(relation::AbstractCircuitRelation)
    return hasproperty(relation, :parameters) ? getproperty(relation, :parameters) : ParameterMetadata[]
end

function _relation_endpoints(relation::ShuntInductor)
    return AbstractCircuitEndpoint[relation.at, ground()]
end

function _relation_summary(relation::ShuntInductor)
    return (:shunt_inductor, relation.id, _endpoint_summary(relation.at))
end
