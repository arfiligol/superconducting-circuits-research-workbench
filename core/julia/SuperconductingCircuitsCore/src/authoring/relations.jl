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

struct InductiveCoupling <: AbstractCircuitRelation
    id::String
    from::AbstractCircuitEndpoint
    to::AbstractCircuitEndpoint
    mutual_inductance::Any
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

function connect!(plan::CircuitPlan, a::AbstractNodeEndpoint, b::AbstractNodeEndpoint)
    relation = NodeConnection(a, b)
    push!(plan.relations, relation)
    return relation
end

function connect!(plan::CircuitPlan, a::AbstractCircuitEndpoint, b::AbstractCircuitEndpoint)
    _validation_error("connect! requires NodeEndpoint <-> NodeEndpoint.")
end

function couple_capacitive!(
    plan::CircuitPlan;
    id,
    from,
    to,
    capacitance,
    parameters=ParameterMetadata[],
)
    from isa AbstractNodeEndpoint && to isa AbstractNodeEndpoint ||
        _validation_error("couple_capacitive! requires NodeEndpoint <-> NodeEndpoint.")
    params = _parameter_vector(parameters)
    relation = CapacitiveCoupling(String(id), from, to, capacitance, params)
    push!(plan.relations, relation)
    _register_relation_parameters!(plan, params)
    return relation
end

function shunt_capacitor!(
    plan::CircuitPlan;
    id,
    at,
    capacitance,
    parameters=ParameterMetadata[],
)
    at isa AbstractNodeEndpoint || _validation_error("shunt_capacitor! requires a NodeEndpoint.")
    params = _parameter_vector(parameters)
    relation = ShuntCapacitor(String(id), at, capacitance, params)
    push!(plan.relations, relation)
    _register_relation_parameters!(plan, params)
    return relation
end

function shunt_inductor!(
    plan::CircuitPlan;
    id,
    at,
    inductance,
    parameters=ParameterMetadata[],
)
    at isa AbstractNodeEndpoint || _validation_error("shunt_inductor! requires a NodeEndpoint.")
    params = _parameter_vector(parameters)
    relation = ShuntInductor(String(id), at, inductance, params)
    push!(plan.relations, relation)
    _register_relation_parameters!(plan, params)
    return relation
end

function couple_inductive!(
    plan::CircuitPlan;
    id,
    from,
    to,
    mutual_inductance,
    parameters=ParameterMetadata[],
)
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
    return relation
end

function couple_window!(
    plan::CircuitPlan;
    id,
    line_a,
    line_b,
    spec,
    parameters=ParameterMetadata[],
)
    line_a isa LineSpanEndpoint && line_b isa LineSpanEndpoint ||
        _validation_error("couple_window! requires LineSpanEndpoint <-> LineSpanEndpoint.")
    params = _parameter_vector(parameters)
    relation = CoupledWindowRelation(String(id), line_a, line_b, spec, params)
    push!(plan.relations, relation)
    _register_relation_parameters!(plan, params)
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
