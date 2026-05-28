function _validation_message(report::ValidationReport)
    return join([string(issue.code, ": ", issue.message) for issue in errors(report)], "; ")
end

mutable struct _JosephsonCompileContext
    plan::CircuitPlan
    parent::Dict{Any,Any}
    endpoints::Vector{AbstractCircuitEndpoint}
    node_map::Dict{Any,String}
    component_map::Dict{String,Vector{Int}}
    relation_map::Dict{String,Vector{Int}}
    line_tap_map::Dict{Any,Any}
    netlist::Vector{Any}
    component_values::Dict{Symbol,Any}
    warnings::Vector{String}
end

function _compile_context(plan::CircuitPlan)
    return _JosephsonCompileContext(
        plan,
        Dict{Any,Any}(),
        AbstractCircuitEndpoint[],
        Dict{Any,String}(),
        Dict{String,Vector{Int}}(),
        Dict{String,Vector{Int}}(),
        Dict{Any,Any}(),
        Any[],
        Dict{Symbol,Any}(),
        String[],
    )
end

function _sanitize_node_part(value)
    text = replace(string(value), r"[^A-Za-z0-9_]" => "_")
    isempty(text) && return "unnamed"
    return text
end

function _endpoint_key(endpoint::AbstractCircuitEndpoint)
    return _endpoint_summary(endpoint)
end

function _ensure_endpoint!(ctx::_JosephsonCompileContext, endpoint::AbstractCircuitEndpoint)
    key = _endpoint_key(endpoint)
    if !haskey(ctx.parent, key)
        ctx.parent[key] = key
        push!(ctx.endpoints, endpoint)
    end
    return key
end

function _find_endpoint_root!(ctx::_JosephsonCompileContext, key)
    parent = ctx.parent[key]
    if parent != key
        ctx.parent[key] = _find_endpoint_root!(ctx, parent)
    end
    return ctx.parent[key]
end

function _union_endpoints!(ctx::_JosephsonCompileContext, a::AbstractCircuitEndpoint, b::AbstractCircuitEndpoint)
    key_a = _ensure_endpoint!(ctx, a)
    key_b = _ensure_endpoint!(ctx, b)
    root_a = _find_endpoint_root!(ctx, key_a)
    root_b = _find_endpoint_root!(ctx, key_b)
    root_a == root_b && return root_a

    preferred = _preferred_endpoint_root(root_a, root_b)
    other = preferred == root_a ? root_b : root_a
    ctx.parent[other] = preferred
    return preferred
end

function _preferred_endpoint_root(a, b)
    _endpoint_root_rank(a) < _endpoint_root_rank(b) && return a
    _endpoint_root_rank(b) < _endpoint_root_rank(a) && return b
    return repr(a) <= repr(b) ? a : b
end

function _endpoint_root_rank(key)
    kind = key[1]
    kind == :ground && return 1
    kind == :external_node && return 2
    kind == :pin && return 3
    kind == :line_tap && return 4
    return 9
end

function _raw_node_name(endpoint::GroundEndpoint)
    return "0"
end

function _raw_node_name(endpoint::ExternalNodeEndpoint)
    return "ext_$(_sanitize_node_part(endpoint.name))"
end

function _raw_node_name(endpoint::PinEndpoint)
    return "n_$(_sanitize_node_part(endpoint.component_id))_$(_sanitize_node_part(endpoint.pin))"
end

function _raw_node_name(endpoint::LineTapEndpoint)
    at_tag = replace(string(endpoint.at_m), "." => "p", "-" => "m")
    return "tap_$(_sanitize_node_part(endpoint.line_ref.component_id))_$(_sanitize_node_part(endpoint.line_ref.line))_$(at_tag)"
end

function _raw_node_name(endpoint::AbstractCircuitEndpoint)
    _validation_error("Unsupported endpoint for Josephson lowering: $(typeof(endpoint)).")
end

function _node_name_for_root(root, endpoints_by_key)
    endpoint = endpoints_by_key[root]
    return _raw_node_name(endpoint)
end

function _validate_endpoint_for_lumped_lowering(plan::CircuitPlan, endpoint::AbstractCircuitEndpoint)
    if endpoint isa PinEndpoint
        component = get(plan.components, endpoint.component_id, nothing)
        isnothing(component) && _validation_error(
            "Cannot lower pin endpoint for missing component '$(endpoint.component_id)'.",
        )
        endpoint.pin in component_pins(component) || _validation_error(
            "Component '$(endpoint.component_id)' does not expose pin '$(endpoint.pin)'.",
        )
    elseif endpoint isa LineTapEndpoint
        component = get(plan.components, endpoint.line_ref.component_id, nothing)
        isnothing(component) && _validation_error(
            "Cannot lower line tap for missing component '$(endpoint.line_ref.component_id)'.",
        )
        endpoint.line_ref.line in component_lines(component) || _validation_error(
            "Component '$(endpoint.line_ref.component_id)' does not expose line '$(endpoint.line_ref.line)'.",
        )
    elseif endpoint isa Union{GroundEndpoint,ExternalNodeEndpoint}
        return
    else
        _validation_error("Unsupported node endpoint for lumped Josephson lowering: $(typeof(endpoint)).")
    end
end

function _prepare_node_resolution!(ctx::_JosephsonCompileContext)
    for relation in ctx.plan.relations
        if relation isa NodeConnection
            _validate_endpoint_for_lumped_lowering(ctx.plan, relation.a)
            _validate_endpoint_for_lumped_lowering(ctx.plan, relation.b)
            _union_endpoints!(ctx, relation.a, relation.b)
        elseif relation isa CapacitiveCoupling
            _validate_endpoint_for_lumped_lowering(ctx.plan, relation.from)
            _validate_endpoint_for_lumped_lowering(ctx.plan, relation.to)
            _ensure_endpoint!(ctx, relation.from)
            _ensure_endpoint!(ctx, relation.to)
        elseif relation isa ShuntCapacitor
            _validate_endpoint_for_lumped_lowering(ctx.plan, relation.at)
            _ensure_endpoint!(ctx, relation.at)
            _ensure_endpoint!(ctx, ground())
        elseif relation isa ShuntInductor
            _validate_endpoint_for_lumped_lowering(ctx.plan, relation.at)
            _ensure_endpoint!(ctx, relation.at)
            _ensure_endpoint!(ctx, ground())
        elseif relation isa InductiveCoupling
            _validation_error("InductiveCoupling '$(relation.id)' is not supported by the lumped Josephson compiler MVP yet.")
        elseif relation isa CoupledWindowRelation
            _validation_error("CoupledWindowRelation '$(relation.id)' is not supported by the lumped Josephson compiler MVP yet.")
        else
            _validation_error("Unsupported relation for Josephson lowering: $(typeof(relation)).")
        end
    end

    for port in _external_port_declarations(ctx.plan)
        _validate_endpoint_for_lumped_lowering(ctx.plan, port.endpoint)
        _ensure_endpoint!(ctx, port.endpoint)
    end

    endpoints_by_key = Dict{Any,AbstractCircuitEndpoint}(_endpoint_key(endpoint) => endpoint for endpoint in ctx.endpoints)
    root_names = Dict{Any,String}()
    for endpoint in ctx.endpoints
        key = _endpoint_key(endpoint)
        root = _find_endpoint_root!(ctx, key)
        root_names[root] = get(root_names, root, _node_name_for_root(root, endpoints_by_key))
        node_name = root_names[root]
        ctx.node_map[endpoint] = node_name
        ctx.node_map[key] = node_name
        if endpoint isa LineTapEndpoint
            ctx.line_tap_map[endpoint] = (
                component_id=endpoint.line_ref.component_id,
                line=endpoint.line_ref.line,
                at_m=endpoint.at_m,
                node=node_name,
            )
            ctx.line_tap_map[key] = ctx.line_tap_map[endpoint]
        end
    end
end

function _resolved_node(ctx::_JosephsonCompileContext, endpoint::AbstractCircuitEndpoint)
    key = _endpoint_key(endpoint)
    haskey(ctx.node_map, key) || _validation_error("Endpoint was not resolved before lowering: $(repr(key)).")
    return ctx.node_map[key]
end

function _relation_component_ids(relation::AbstractCircuitRelation)
    ids = String[]
    for endpoint in _relation_endpoints(relation)
        append!(ids, _endpoint_component_ids(endpoint))
    end
    return unique(ids)
end

function _record_row_provenance!(ctx::_JosephsonCompileContext, relation::AbstractCircuitRelation, row_index::Int)
    relation_id = _relation_id(relation)
    if !isnothing(relation_id)
        push!(get!(ctx.relation_map, relation_id, Int[]), row_index)
    end

    for component_id in _relation_component_ids(relation)
        push!(get!(ctx.component_map, component_id, Int[]), row_index)
    end
end

function _component_value_ref!(ctx::_JosephsonCompileContext, row_name::AbstractString, value)
    if value isa ParameterBinding
        ctx.component_values[value.name] = value.value
        return value.name
    elseif value isa Pair && first(value) isa Symbol
        ctx.component_values[first(value)] = last(value)
        return first(value)
    elseif value isa Symbol
        return value
    elseif value isa AbstractString
        return Symbol(value)
    elseif value isa Number
        ref = Symbol(row_name)
        ctx.component_values[ref] = value
        return ref
    end
    _validation_error("Component value for '$(row_name)' must be numeric, a Symbol, a String, or a ParameterBinding.")
end

function _emit_capacitor_relation!(
    ctx::_JosephsonCompileContext;
    relation::AbstractCircuitRelation,
    row_name::AbstractString,
    node_a::AbstractString,
    node_b::AbstractString,
    capacitance,
)
    value = capacitance
    _require(value isa Number || value isa ParameterBinding || value isa Symbol || value isa AbstractString,
        "Capacitor relation '$(row_name)' must use a numeric value or parameter binding.")

    value_ref = _component_value_ref!(ctx, row_name, value)
    _push_component!(ctx.netlist, row_name, node_a, node_b, value_ref)
    row_index = length(ctx.netlist)
    _record_row_provenance!(ctx, relation, row_index)
    return row_index
end

function _emit_inductor_relation!(
    ctx::_JosephsonCompileContext;
    relation::AbstractCircuitRelation,
    row_name::AbstractString,
    node_a::AbstractString,
    node_b::AbstractString,
    inductance,
)
    value = inductance
    _require(value isa Number || value isa ParameterBinding || value isa Symbol || value isa AbstractString,
        "Inductor relation '$(row_name)' must use a numeric value or parameter binding.")

    value_ref = _component_value_ref!(ctx, row_name, value)
    _push_component!(ctx.netlist, row_name, node_a, node_b, value_ref)
    row_index = length(ctx.netlist)
    _record_row_provenance!(ctx, relation, row_index)
    return row_index
end

function _lower_relation!(ctx::_JosephsonCompileContext, relation::NodeConnection)
    return nothing
end

function _lower_relation!(ctx::_JosephsonCompileContext, relation::CapacitiveCoupling)
    return _emit_capacitor_relation!(
        ctx;
        relation=relation,
        row_name="C_$(_sanitize_node_part(relation.id))",
        node_a=_resolved_node(ctx, relation.from),
        node_b=_resolved_node(ctx, relation.to),
        capacitance=relation.capacitance,
    )
end

function _lower_relation!(ctx::_JosephsonCompileContext, relation::ShuntCapacitor)
    return _emit_capacitor_relation!(
        ctx;
        relation=relation,
        row_name="C_$(_sanitize_node_part(relation.id))",
        node_a=_resolved_node(ctx, relation.at),
        node_b="0",
        capacitance=relation.capacitance,
    )
end

function _lower_relation!(ctx::_JosephsonCompileContext, relation::ShuntInductor)
    return _emit_inductor_relation!(
        ctx;
        relation=relation,
        row_name="L_$(_sanitize_node_part(relation.id))",
        node_a=_resolved_node(ctx, relation.at),
        node_b="0",
        inductance=relation.inductance,
    )
end

function _lower_relation!(::_JosephsonCompileContext, relation::InductiveCoupling)
    _validation_error("InductiveCoupling '$(relation.id)' is not supported by the lumped Josephson compiler MVP yet.")
end

function _lower_relation!(::_JosephsonCompileContext, relation::CoupledWindowRelation)
    _validation_error("CoupledWindowRelation '$(relation.id)' is not supported by the lumped Josephson compiler MVP yet.")
end

function _lower_relation!(::_JosephsonCompileContext, relation::AbstractCircuitRelation)
    _validation_error("Unsupported relation for Josephson lowering: $(typeof(relation)).")
end

function _collect_external_port_declarations(raw_ports)
    declarations = ExternalPort[]
    if raw_ports isa AbstractDict
        for (key, value) in pairs(raw_ports)
            value isa ExternalPort ||
                _validation_error("CircuitPlan metadata[:external_ports] accepts ExternalPort declarations only.")
            Symbol(key) == value.id ||
                _validation_error("ExternalPort dictionary key '$(key)' does not match declaration id '$(value.id)'.")
            push!(declarations, value)
        end
    elseif raw_ports isa AbstractVector
        for value in raw_ports
            value isa ExternalPort ||
                _validation_error("CircuitPlan metadata[:external_ports] accepts ExternalPort declarations only.")
            push!(declarations, value)
        end
    else
        _validation_error("CircuitPlan metadata[:external_ports] must be a dictionary or vector of ExternalPort declarations when present.")
    end
    return declarations
end

function _external_port_declarations(plan::CircuitPlan)
    raw_ports = get(plan.metadata, :external_ports, ExternalPort[])
    declarations = _collect_external_port_declarations(raw_ports)

    seen_ids = Set{Symbol}()
    seen_indices = Set{Int}()
    for port in declarations
        port.id in seen_ids && _validation_error("Duplicate external port id '$(port.id)'.")
        port.index in seen_indices && _validation_error("Duplicate external port index '$(port.index)'.")
        port.index > 0 || _validation_error("ExternalPort '$(port.id)' must have a positive index.")
        port.resistance > 0 || _validation_error("ExternalPort '$(port.id)' must have positive resistance.")
        port.endpoint isa AbstractNodeEndpoint ||
            _validation_error("ExternalPort '$(port.id)' endpoint must resolve to one circuit node.")
        push!(seen_ids, port.id)
        push!(seen_indices, port.index)
    end

    return sort(declarations; by=port -> port.index)
end

function _emit_external_ports!(ctx::_JosephsonCompileContext)
    ports = _external_port_declarations(ctx.plan)
    isempty(ports) && return Dict{String,Int}()

    external_port_map = Dict{String,Int}()
    for port in ports
        node_name = _resolved_node(ctx, port.endpoint)
        push!(ctx.netlist, ("P$(port.index)", node_name, "0", port.index))
        resistor_name = "R_port_$(port.index)"
        value_ref = _component_value_ref!(ctx, resistor_name, port.resistance)
        _push_component!(ctx.netlist, resistor_name, node_name, "0", value_ref)
        external_port_map[string(port.id)] = port.index
    end

    return external_port_map
end

function compile_to_josephson(plan::CircuitPlan)::JosephsonCompiledCircuit
    report = validate_compile_ready(plan)
    if has_errors(report)
        _validation_error("CircuitPlan '$(plan.id)' is not compile-ready: $(_validation_message(report))")
    end
    hb_report = validate_hb_intent(plan)
    if has_errors(hb_report)
        _validation_error("CircuitPlan '$(plan.id)' has invalid HB intent: $(_validation_message(hb_report))")
    end

    key = topology_key(plan)
    ctx = _compile_context(plan)
    _prepare_node_resolution!(ctx)
    external_port_map = _emit_external_ports!(ctx)
    for relation in plan.relations
        _lower_relation!(ctx, relation)
    end

    if isempty(ctx.netlist)
        if isempty(plan.components) && isempty(plan.relations)
            push!(ctx.warnings, "CircuitPlan '$(plan.id)' contains no lowerable circuit elements.")
        else
            push!(ctx.warnings, "CircuitPlan '$(plan.id)' lowered no target rows; add supported lumped element relations before simulation.")
        end
    end
    hb_intent = get(plan.metadata, :hb_intent, nothing)
    port_map = Dict(Symbol(name) => (index=index,) for (name, index) in external_port_map)
    source_slot_map = isnothing(hb_intent) ? Dict{Symbol,Any}() :
        Dict(slot.id => (port=slot.port, mode=slot.mode, role=slot.role) for slot in hb_intent.source_slots)
    observable_request_map = isnothing(hb_intent) ? Dict{Symbol,Any}() :
        Dict(getproperty(obs, :id) => obs for obs in hb_intent.observables if hasproperty(obs, :id))

    return JosephsonCompiledCircuit(
        netlist=ctx.netlist,
        component_values=ctx.component_values,
        node_map=ctx.node_map,
        component_map=ctx.component_map,
        line_tap_map=ctx.line_tap_map,
        port_map=port_map,
        hb_intent_summary=hb_intent,
        source_slot_map=source_slot_map,
        observable_request_map=observable_request_map,
        hb_validation_summary=(
            issue_count=length(hb_report.issues),
            has_errors=has_errors(hb_report),
        ),
        warnings=ctx.warnings,
        provenance=Dict{Symbol,Any}(
            :plan_id => plan.id,
            :compiler => :josephson_lumped_mvp,
            :topology_key => key.digest,
            :relation_map => ctx.relation_map,
            :external_ports => external_port_map,
            :engineering_graph_component_ids => sort(collect(keys(plan.engineering_graph.components)); by=string),
        ),
        metadata=Dict{Symbol,Any}(
            :topology_key => key,
            :validation_issue_count => length(report.issues),
            :compiler_stage => :lumped_mvp,
            :netlist_row_count => length(ctx.netlist),
            :external_ports => external_port_map,
            :hb_intent => hb_intent,
            :hb_validation_report => hb_report,
        ),
    )
end
