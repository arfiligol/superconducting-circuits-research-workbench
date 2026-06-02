function _macro_core_ref(name::Symbol)
    return Expr(:., :SuperconductingCircuitsCore, QuoteNode(name))
end

function _macro_line_location(source)
    return (
        file=String(source.file),
        line=source.line,
    )
end

function _split_call_kwargs(expr)
    expr isa Expr && expr.head == :call || error("Expected a function call expression.")
    args = Any[]
    kwargs = Dict{Symbol,Any}()
    for arg in expr.args[2:end]
        if arg isa Expr && arg.head == :parameters
            for kw in arg.args
                if kw isa Expr && kw.head == :kw
                    kwargs[kw.args[1]] = kw.args[2]
                else
                    error("Unsupported keyword expression in $(expr.args[1]).")
                end
            end
        elseif arg isa Expr && arg.head == :kw
            kwargs[arg.args[1]] = arg.args[2]
        else
            push!(args, arg)
        end
    end
    return expr.args[1], args, kwargs
end

function _keyword_or_default(kwargs::Dict{Symbol,Any}, name::Symbol, default)
    return haskey(kwargs, name) ? kwargs[name] : default
end

function _port_block_assignments(block)
    block isa Expr && block.head == :block || error("DSL block must contain assignments.")
    values = Dict{Symbol,Any}()
    for stmt in block.args
        stmt isa LineNumberNode && continue
        if stmt isa Expr && stmt.head == :(=) && stmt.args[1] isa Symbol
            values[stmt.args[1]] = stmt.args[2]
        else
            error("Unsupported block statement: $(stmt). Use simple assignments.")
        end
    end
    return values
end

function _required_block_value(values::Dict{Symbol,Any}, name::Symbol, block_name::AbstractString)
    haskey(values, name) || error("$(block_name) block is missing required assignment '$(name)'.")
    return values[name]
end

function _macro_call_name(callee)
    callee isa Symbol && return callee
    callee isa Expr && callee.head == :. && return callee.args[end] isa QuoteNode ? callee.args[end].value : callee.args[end]
    return nothing
end

const _CIRCUIT_AUTHORING_CALLS = Set{Symbol}([
    :connect!,
    :shunt_capacitor!,
    :shunt_inductor!,
    :series_inductor!,
    :series_resistor!,
    :josephson_junction!,
    :couple_capacitive!,
    :couple_inductive!,
    :couple_window!,
    :build_lc_ladder_line!,
    :transmission_line!,
    :quarter_wave_resonator!,
    :half_wave_resonator!,
    :couple_transmission_window!,
    :add_parallel_lc_resonator!,
    :add_reflective_jpa!,
    :add_half_wave_resonator!,
    :add_quarter_wave_resonator!,
    :add_readout_line_with_purcell_filter!,
    :add_readout_purcell_qwr_mtl!,
])

function _looks_like_authoring_call(name)
    isnothing(name) && return false
    text = String(name)
    return name in _CIRCUIT_AUTHORING_CALLS || (!isempty(text) && text[end] == '!')
end

function _unsupported_circuit_statement_message()
    return "Unsupported @circuit statement. Only endpoint bindings, canonical Core authoring calls, circuit component builders, port blocks, group blocks, and schematic layout blocks are allowed."
end

function _allowed_keyword_list(allowed_keywords)
    values = unique(Symbol[:id; Symbol.(allowed_keywords)])
    sort!(values; by=string)
    return join(string.(values), ", ")
end

function _validate_component_builder_keywords(template_id, kwargs::Dict{Symbol,Any}, allowed_keywords)
    allowed = Set(Symbol.(allowed_keywords))
    for key in keys(kwargs)
        key in allowed && continue
        _validation_error(
            "Unknown keyword '$(key)' for component template '$(template_id)'. Allowed keywords: $(_allowed_keyword_list(allowed_keywords)).",
        )
    end
    return nothing
end

function _missing_component_parameter_error(template_id, parameter_name, allowed_keywords)
    _validation_error(
        "Component template '$(template_id)' is missing required parameter '$(parameter_name)'. Allowed keywords: $(_allowed_keyword_list(allowed_keywords)).",
    )
end

function _invoke_circuit_authoring_call(plan, callee, callee_name::Symbol, args...; kwargs...)
    if callee_name in _CIRCUIT_AUTHORING_CALLS
        return callee(plan, args...; kwargs...)
    elseif callee isa CircuitComponentBuilder
        isempty(args) ||
            _validation_error("Circuit component builder '$(callee.template_id)' does not accept positional arguments inside @circuit.")
        return callee(plan; kwargs...)
    end
    _validation_error(_unsupported_circuit_statement_message())
end

function _literal_symbol(value)
    value isa QuoteNode && value.value isa Symbol && return value.value
    value isa Symbol && return value
    error("Expected a literal Symbol, got $(value).")
end

function _declaration_name_arg(stmt)
    if stmt isa Expr && stmt.head == :call && stmt.args[1] == :(:) && length(stmt.args) == 3
        return stmt.args[2], stmt.args[3]
    end
    if stmt isa Expr && stmt.head == :call
        name = _macro_call_name(stmt.args[1])
        !isnothing(name) && length(stmt.args) == 2 && return name, stmt.args[2]
    end
    return nothing, nothing
end

function _macro_dispatch_call(plan_var, expr; namespace_id=nothing)
    expr isa Expr && expr.head == :call || error("Expected call expression.")
    callee = expr.args[1]
    callee_name = _macro_call_name(callee)
    args = Any[]
    parameters = Any[]
    for arg in expr.args[2:end]
        if arg isa Expr && arg.head == :parameters
            for kw in arg.args
                if !isnothing(namespace_id) && kw isa Expr && kw.head == :kw && kw.args[1] == :id
                    push!(
                        parameters,
                        Expr(:kw, :id, :($(_macro_core_ref(:component_local_id))($(namespace_id), $(esc(kw.args[2]))))),
                    )
                else
                    push!(parameters, _component_body_expr(kw, namespace_id))
                end
            end
        elseif arg isa Expr && arg.head == :kw
            if !isnothing(namespace_id) && arg.args[1] == :id
                push!(
                    parameters,
                    Expr(:kw, :id, :($(_macro_core_ref(:component_local_id))($(namespace_id), $(esc(arg.args[2]))))),
                )
            else
                push!(parameters, _component_body_expr(arg, namespace_id))
            end
        else
            push!(args, _component_body_expr(arg, namespace_id))
        end
    end
    call_args = Any[
        _macro_core_ref(:_invoke_circuit_authoring_call),
    ]
    !isempty(parameters) && push!(call_args, Expr(:parameters, parameters...))
    push!(call_args, plan_var)
    push!(
        call_args,
        !isnothing(callee_name) && callee_name in _CIRCUIT_AUTHORING_CALLS ? _macro_core_ref(callee_name) : esc(callee),
    )
    push!(call_args, isnothing(callee_name) ? QuoteNode(Symbol("<anonymous>")) : QuoteNode(callee_name))
    append!(call_args, args)
    return Expr(:call, call_args...)
end

function _component_body_expr(expr, namespace_id)
    expr isa LineNumberNode && return expr
    expr isa Symbol && return esc(expr)
    !(expr isa Expr) && return expr
    if expr.head == :call
        name = _macro_call_name(expr.args[1])
        if name == :pin && length(expr.args) == 2
            return :(__component_pin__($(esc(expr.args[2]))))
        elseif name == :probe && length(expr.args) == 2
            return :(__component_probe__($(esc(expr.args[2]))))
        elseif name == :anchor && length(expr.args) == 2
            return :(__component_anchor__($(esc(expr.args[2]))))
        elseif name == :external_node && length(expr.args) == 2 && !isnothing(namespace_id)
            return :($(_macro_core_ref(:component_private_node))($(namespace_id), $(esc(expr.args[2]))))
        end
    end
    return Expr(expr.head, [_component_body_expr(arg, namespace_id) for arg in expr.args]...)
end

function _component_relation_statement(plan_var, stmt, namespace_id)
    if stmt isa Expr && stmt.head == :call
        name = _macro_call_name(stmt.args[1])
        if _looks_like_authoring_call(name)
            return _macro_dispatch_call(plan_var, stmt; namespace_id=namespace_id)
        end
    elseif stmt isa Expr && stmt.head == :(=)
        rhs = stmt.args[2]
        if rhs isa Expr && rhs.head == :call
            name = _macro_call_name(rhs.args[1])
            if _looks_like_authoring_call(name)
                return :($(esc(stmt.args[1])) = $(_macro_dispatch_call(plan_var, rhs; namespace_id=namespace_id)))
            end
        end
        return Expr(:(=), esc(stmt.args[1]), _component_body_expr(rhs, namespace_id))
    end
    return _component_body_expr(stmt, namespace_id)
end

function _parse_component_macro(block)
    pins = Symbol[]
    probes = Symbol[]
    anchors = Symbol[]
    lines = Symbol[]
    parameters = Vector{Tuple{Symbol,Any}}()
    body = Any[]
    for stmt in block.args
        stmt isa LineNumberNode && continue
        if stmt isa Expr && stmt.head == :call
            decl_name, decl_arg = _declaration_name_arg(stmt)
            if decl_name == :pin
                push!(pins, _literal_symbol(decl_arg))
                continue
            elseif decl_name == :probe
                push!(probes, _literal_symbol(decl_arg))
                continue
            elseif decl_name == :anchor
                push!(anchors, _literal_symbol(decl_arg))
                continue
            elseif decl_name == :line
                push!(lines, _literal_symbol(decl_arg))
                continue
            elseif decl_name == :tap
                error("@circuit_component line interfaces must be declared with line(...). tap(...) is reserved for distance-based endpoint access.")
            end
            name = _macro_call_name(stmt.args[1])
            if name == :parameter
                _, args, kwargs = _split_call_kwargs(stmt)
                length(args) == 1 || error("parameter(...) expects exactly one parameter name.")
                unit = _keyword_or_default(kwargs, :unit, "")
                push!(parameters, (_literal_symbol(args[1]), unit))
                continue
            end
        end
        push!(body, stmt)
    end
    return pins, probes, anchors, lines, parameters, body
end

macro var"circuit_component"(template_id, block)
    block isa Expr && block.head == :block || error("@circuit_component requires a begin ... end block.")
    pins, probes, anchors, lines, parameters, body = _parse_component_macro(block)
    plan_var = gensym(:component_plan)
    id_var = gensym(:component_id)
    kwargs_var = gensym(:component_kwargs)
    instance_var = gensym(:component_instance)

    pin_pairs = [:( $(QuoteNode(pin)) => get($(kwargs_var), $(QuoteNode(pin)), $(_macro_core_ref(:PinEndpoint))(String($(id_var)), $(QuoteNode(pin)))) ) for pin in pins]
    probe_pairs = [:( $(QuoteNode(probe)) => $(_macro_core_ref(:ProbeEndpoint))(String($(id_var)), $(QuoteNode(probe))) ) for probe in probes]
    anchor_pairs = [:( $(QuoteNode(anchor)) => $(_macro_core_ref(:AnchorRef))(String($(id_var)), $(QuoteNode(anchor))) ) for anchor in anchors]
    line_pairs = [:( $(QuoteNode(line)) => $(_macro_core_ref(:LineRef))(String($(id_var)), $(QuoteNode(line))) ) for line in lines]
    parameter_metadata = [
        :(
            $(_macro_core_ref(:ParameterMetadata))(
                name=$(QuoteNode(name)),
                role=$(_macro_core_ref(:NumericParameter))(),
                owner=String($(id_var)),
                targets=[$(QuoteNode(name))],
                sweep_name=$(QuoteNode(name)),
                units=String($(esc(unit))),
            )
        ) for (name, unit) in parameters
    ]
    parameter_assignments = Any[
        quote
            haskey($(kwargs_var), $(QuoteNode(name))) ||
                $(_macro_core_ref(:_missing_component_parameter_error))(
                    Symbol($(esc(template_id))),
                    $(QuoteNode(name)),
                    __allowed_component_keywords__,
                )
            local $(esc(name)) = $(kwargs_var)[$(QuoteNode(name))]
        end for (name, _) in parameters
    ]
    transformed_body = [_component_relation_statement(plan_var, stmt, id_var) for stmt in body]

    builder_var = gensym(:component_builder)
    allowed_keywords = unique(Symbol[pins...; first.(parameters)...])
    allowed_keyword_literals = [QuoteNode(key) for key in allowed_keywords]

    return quote
        function $(builder_var)($(plan_var)::$(_macro_core_ref(:CircuitPlan)); id, kwargs...)
            local $(id_var) = String(id)
            local $(kwargs_var) = Dict{Symbol,Any}(kwargs)
            local __allowed_component_keywords__ = Symbol[$(allowed_keyword_literals...)]
            $(_macro_core_ref(:_validate_component_builder_keywords))(
                Symbol($(esc(template_id))),
                $(kwargs_var),
                __allowed_component_keywords__,
            )
            $(parameter_assignments...)
            local __component_pins__ = Dict{Symbol,Any}($(pin_pairs...))
            local __component_probes__ = Dict{Symbol,Any}($(probe_pairs...))
            local __component_anchors__ = Dict{Symbol,Any}($(anchor_pairs...))
            local __component_lines__ = Dict{Symbol,Any}($(line_pairs...))
            local __component_parameters__ = $(_macro_core_ref(:ParameterMetadata))[$(parameter_metadata...)]
            local $(instance_var) = $(_macro_core_ref(:_component_instance))(
                $(id_var);
                template_id=$(esc(template_id)),
                pins=__component_pins__,
                lines=__component_lines__,
                probes=__component_probes__,
                anchors=__component_anchors__,
                parameters=__component_parameters__,
            )
            $(_macro_core_ref(:register_component!))(
                $(plan_var),
                $(instance_var);
                display_name=Symbol($(id_var)),
                role=:component,
                component_type=Symbol($(esc(template_id))),
            )
            local __component_pin__ = name -> begin
                haskey(__component_pins__, Symbol(name)) ||
                    $(_macro_core_ref(:_validation_error))("Component '$(id)' does not expose pin '$(name)'.")
                __component_pins__[Symbol(name)]
            end
            local __component_probe__ = name -> begin
                haskey(__component_probes__, Symbol(name)) ||
                    $(_macro_core_ref(:_validation_error))("Component '$(id)' does not expose probe '$(name)'.")
                __component_probes__[Symbol(name)]
            end
            local __component_anchor__ = name -> begin
                haskey(__component_anchors__, Symbol(name)) ||
                    $(_macro_core_ref(:_validation_error))("Component '$(id)' does not expose anchor '$(name)'.")
                __component_anchors__[Symbol(name)]
            end
            $(transformed_body...)
            $(instance_var)
        end
        $(_macro_core_ref(:CircuitComponentBuilder))(
            Symbol($(esc(template_id))),
            Symbol[$(allowed_keyword_literals...)],
            $(builder_var),
        )
    end
end

function _port_expansion(plan_var, expr, source)
    expr isa Expr && expr.head == :do || error("port declaration must use port(:id) do ... end.")
    call_expr = expr.args[1]
    body_expr = expr.args[2]
    call_expr isa Expr && call_expr.head == :call && call_expr.args[1] == :port ||
        error("port declaration must use port(:id) do ... end.")
    length(call_expr.args) == 2 || error("port(...) expects exactly one port id.")

    body_expr isa Expr && body_expr.head == :(->) || error("port declaration must use a do block.")
    values = _port_block_assignments(body_expr.args[2])
    source_location = QuoteNode(_macro_line_location(source))
    return quote
        $(_macro_core_ref(:external_port!))(
            $(plan_var);
            id=$(esc(call_expr.args[2])),
            index=$(esc(_required_block_value(values, :index, "port"))),
            endpoint=$(esc(_required_block_value(values, :endpoint, "port"))),
            resistance=$(esc(_required_block_value(values, :resistance, "port"))),
            role=$(esc(_required_block_value(values, :role, "port"))),
            source_location=$(source_location),
        )
    end
end

function _group_expansion(plan_var, expr)
    expr isa Expr && expr.head == :do || error("group declaration must use group(:id) do ... end.")
    call_expr = expr.args[1]
    body_expr = expr.args[2]
    call_expr isa Expr && call_expr.head == :call && call_expr.args[1] == :group ||
        error("group declaration must use group(:id) do ... end.")
    length(call_expr.args) == 2 || error("group(...) expects exactly one group id.")
    values = _port_block_assignments(body_expr.args[2])
    label = _keyword_or_default(values, :label, nothing)
    role = _keyword_or_default(values, :role, QuoteNode(:group))
    members = _keyword_or_default(values, :members, :([]))
    return quote
        $(_macro_core_ref(:record_engineering_group!))(
            $(plan_var);
            id=$(esc(call_expr.args[2])),
            label=$(esc(label)),
            role=$(esc(role)),
            members=$(esc(members)),
        )
    end
end

function _layout_block_expansion(plan_var, expr)
    expr isa Expr && expr.head == :do || error("schematic! declaration must use a do block.")
    call_expr = expr.args[1]
    body_expr = expr.args[2]
    call_expr isa Expr && call_expr.head == :call && call_expr.args[1] == :schematic! ||
        error("schematic! declaration must use schematic!(...) do ... end.")
    _, args, kwargs = _split_call_kwargs(call_expr)
    id_expr = isempty(args) ? _keyword_or_default(kwargs, :id, QuoteNode(:default)) : first(args)
    body_expr isa Expr && body_expr.head == :(->) || error("schematic! declaration must use a do block.")
    statements = Any[:($(_macro_core_ref(:schematic_layout_intent))($(plan_var)).id = Symbol($(esc(id_expr))))]
    for stmt in body_expr.args[2].args
        stmt isa LineNumberNode && continue
        push!(statements, _layout_statement_expansion(plan_var, stmt))
    end
    return quote
        $(statements...)
    end
end

function _layout_statement_expansion(plan_var, stmt)
    stmt isa Expr && stmt.head == :do || error("schematic! supports layout do-block declarations.")
    call_expr = stmt.args[1]
    body_expr = stmt.args[2]
    call_expr isa Expr && call_expr.head == :call || error("Invalid schematic layout declaration.")
    name = _macro_call_name(call_expr.args[1])
    length(call_expr.args) == 2 || error("$(name)(...) expects exactly one id.")
    values = _port_block_assignments(body_expr.args[2])
    fn = Dict(
        :track => :record_schematic_track!,
        :segment => :record_schematic_segment!,
        :coupled_span => :record_schematic_coupled_span!,
        :terminal => :record_schematic_terminal!,
        :node_label => :record_schematic_node_label!,
        :segment_label => :record_schematic_segment_label!,
        :anchor => :record_schematic_anchor!,
    )
    haskey(fn, name) || error("Unsupported schematic layout declaration '$(name)'.")
    parameters = Any[Expr(:kw, :id, esc(call_expr.args[2]))]
    for (key, value) in values
        push!(parameters, Expr(:kw, key, esc(value)))
    end
    return Expr(:call, _macro_core_ref(fn[name]), Expr(:parameters, parameters...), plan_var)
end

function _circuit_call_expansion(plan_var, expr)
    if expr isa Expr && expr.head == :call
        name = _macro_call_name(expr.args[1])
        if _looks_like_authoring_call(name)
            return _macro_dispatch_call(plan_var, expr)
        end
    end
    return esc(expr)
end

function _circuit_statement_expansion(plan_var, stmt, source)
    stmt isa LineNumberNode && return nothing
    if stmt isa Expr && stmt.head == :(=) && stmt.args[1] isa Symbol
        rhs = stmt.args[2]
        return :($(esc(stmt.args[1])) = $(_circuit_call_expansion(plan_var, rhs)))
    elseif stmt isa Expr && stmt.head == :call
        name = _macro_call_name(stmt.args[1])
        _looks_like_authoring_call(name) || error(_unsupported_circuit_statement_message())
        return _circuit_call_expansion(plan_var, stmt)
    elseif stmt isa Expr && stmt.head == :do
        call_expr = stmt.args[1]
        call_expr isa Expr && call_expr.head == :call || error("Unsupported @circuit do block.")
        name = _macro_call_name(call_expr.args[1])
        name == :port && return _port_expansion(plan_var, stmt, source)
        name == :group && return _group_expansion(plan_var, stmt)
        name == :schematic! && return _layout_block_expansion(plan_var, stmt)
    end
    error(_unsupported_circuit_statement_message())
end

macro circuit(id, block)
    block isa Expr && block.head == :block || error("@circuit requires a begin ... end block.")
    plan_var = gensym(:plan)
    statements = Any[]
    for stmt in block.args
        expanded = _circuit_statement_expansion(plan_var, stmt, __source__)
        isnothing(expanded) || push!(statements, expanded)
    end

    return quote
        local $(plan_var) = $(_macro_core_ref(:CircuitPlan))($(esc(id)))
        $(statements...)
        $(plan_var)
    end
end

function _hb_block_assignments(block, block_name)
    return _port_block_assignments(block)
end

function _hb_statement_expr(stmt)
    stmt isa Expr && stmt.head == :call || return nothing
    name = _macro_call_name(stmt.args[1])
    if name == :pump_axis
        _, args, kwargs = _split_call_kwargs(stmt)
        length(args) == 1 || error("pump_axis(...) expects one id.")
        return :($(_macro_core_ref(:PumpAxis))(id=$(esc(args[1])), frequency_parameter=$(esc(_required_block_value(kwargs, :frequency_parameter, "pump_axis")))))
    end
    return nothing
end

function _hb_do_statement_expr(stmt)
    stmt isa Expr && stmt.head == :do || return nothing
    call_expr = stmt.args[1]
    body_expr = stmt.args[2]
    call_expr isa Expr && call_expr.head == :call || return nothing
    name = _macro_call_name(call_expr.args[1])
    values = _hb_block_assignments(body_expr.args[2], string(name))
    if name == :source_slot
        length(call_expr.args) == 2 || error("source_slot(...) expects one id.")
        return :(
            $(_macro_core_ref(:HBSourceSlot))(
                id=$(esc(call_expr.args[2])),
                role=$(esc(_required_block_value(values, :role, "source_slot"))),
                port=$(esc(_required_block_value(values, :port, "source_slot"))),
                mode=$(esc(_required_block_value(values, :mode, "source_slot"))),
                current_parameter=$(esc(_required_block_value(values, :current_parameter, "source_slot"))),
            )
        )
    elseif name == :sparameter
        length(call_expr.args) == 2 || error("sparameter(...) expects one id.")
        return :(
            $(_macro_core_ref(:SParameterRequest))(
                id=$(esc(call_expr.args[2])),
                outputmode=$(esc(_required_block_value(values, :outputmode, "sparameter"))),
                outputport=$(esc(_required_block_value(values, :outputport, "sparameter"))),
                inputmode=$(esc(_required_block_value(values, :inputmode, "sparameter"))),
                inputport=$(esc(_required_block_value(values, :inputport, "sparameter"))),
            )
        )
    elseif name == :solver_controls
        length(call_expr.args) == 1 || error("solver_controls() do ... end does not accept positional arguments.")
        allowed = Set([
            :n_pump_harmonics,
            :n_modulation_harmonics,
            :dc,
            :threewavemixing,
            :fourwavemixing,
            :returnS,
            :returnZ,
            :returnQE,
            :returnCM,
            :sorting,
            :keyedarrays,
        ])
        unsupported = setdiff(Set(keys(values)), allowed)
        isempty(unsupported) ||
            error("Unsupported solver_controls assignment(s): $(join(string.(sort(collect(unsupported); by=string)), ", ")).")
        parameters = [Expr(:kw, key, esc(value)) for (key, value) in values]
        return Expr(:call, _macro_core_ref(:HBSolverControls), Expr(:parameters, parameters...))
    end
    return nothing
end

macro hbintent(plan, block)
    block isa Expr && block.head == :block || error("@hbintent requires a begin ... end block.")
    pump_axes = Any[]
    source_slots = Any[]
    observables = Any[]
    solver_controls = :($(_macro_core_ref(:HBSolverControls))())
    for stmt in block.args
        stmt isa LineNumberNode && continue
        if stmt isa Expr && stmt.head == :call
            expr = _hb_statement_expr(stmt)
            isnothing(expr) && error("Unsupported @hbintent statement: $(stmt).")
            push!(pump_axes, expr)
        elseif stmt isa Expr && stmt.head == :do
            expr = _hb_do_statement_expr(stmt)
            isnothing(expr) && error("Unsupported @hbintent do block: $(stmt).")
            name = _macro_call_name(stmt.args[1].args[1])
            if name == :source_slot
                push!(source_slots, expr)
            elseif name == :solver_controls
                solver_controls = expr
            else
                push!(observables, expr)
            end
        else
            error("Unsupported @hbintent statement: $(stmt).")
        end
    end
    return quote
        $(_macro_core_ref(:hb_intent!))(
            $(esc(plan));
            pump_axes=$(_macro_core_ref(:PumpAxis))[$(pump_axes...)],
            source_slots=$(_macro_core_ref(:HBSourceSlot))[$(source_slots...)],
            observables=Any[$(observables...)],
            default_solver_controls=$(solver_controls),
        )
    end
end
