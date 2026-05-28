struct CircuitComponentDeclaration{T}
    component::T
    display_name::Symbol
    role::Symbol
end

function component(component_object; display_name=nothing, role=:component)
    display = isnothing(display_name) ? Symbol(component_id(component_object)) : Symbol(display_name)
    return CircuitComponentDeclaration(component_object, display, Symbol(role))
end

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
    block isa Expr && block.head == :block || error("port block must contain assignments.")
    values = Dict{Symbol,Any}()
    for stmt in block.args
        stmt isa LineNumberNode && continue
        if stmt isa Expr && stmt.head == :(=) && stmt.args[1] isa Symbol
            values[stmt.args[1]] = stmt.args[2]
        else
            error("Unsupported port block statement: $(stmt). Use simple assignments.")
        end
    end
    return values
end

function _required_port_value(values::Dict{Symbol,Any}, name::Symbol)
    haskey(values, name) || error("port block is missing required assignment '$(name)'.")
    return values[name]
end

function _component_expansion(plan_var, lhs::Symbol, rhs, source)
    rhs isa Expr && rhs.head == :call || error("@circuit component declaration must call component(...).")
    callee, args, kwargs = _split_call_kwargs(rhs)
    callee == :component || error("@circuit assignment must use component(...).")
    length(args) == 1 || error("component(...) expects exactly one component object expression.")

    component_expr = args[1]
    display_name = _keyword_or_default(kwargs, :display_name, QuoteNode(lhs))
    role = _keyword_or_default(kwargs, :role, QuoteNode(:component))
    source_location = QuoteNode(_macro_line_location(source))

    return quote
        $(esc(lhs)) = $(_macro_core_ref(:register_component!))($(plan_var), $(esc(component_expr)))
        $(_macro_core_ref(:record_engineering_component!))(
            $(plan_var);
            id=Symbol($(_macro_core_ref(:component_id))($(esc(lhs)))),
            display_name=$(esc(display_name)),
            component_type=Symbol(nameof(typeof($(esc(lhs))))),
            role=$(esc(role)),
            parameters=Dict(meta.name => meta for meta in $(_macro_core_ref(:component_parameters))($(esc(lhs)))),
            pins=Symbol[$(_macro_core_ref(:component_pins))($(esc(lhs)))...],
            source_location=$(source_location),
        )
        $(esc(lhs))
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
    block = body_expr.args[2]
    values = _port_block_assignments(block)
    port_id = call_expr.args[2]
    index = _required_port_value(values, :index)
    endpoint = _required_port_value(values, :endpoint)
    resistance = _required_port_value(values, :resistance)
    role = _required_port_value(values, :role)
    source_location = QuoteNode(_macro_line_location(source))

    return quote
        $(_macro_core_ref(:external_port!))(
            $(plan_var);
            id=$(esc(port_id)),
            index=$(esc(index)),
            endpoint=$(esc(endpoint)),
            resistance=$(esc(resistance)),
            role=$(esc(role)),
        )
        $(_macro_core_ref(:record_engineering_port!))(
            $(plan_var);
            id=$(esc(port_id)),
            port_index=$(esc(index)),
            endpoint=$(esc(endpoint)),
            resistance=$(esc(resistance)),
            role=$(esc(role)),
            source_location=$(source_location),
        )
    end
end

function _circuit_statement_expansion(plan_var, stmt, source)
    stmt isa LineNumberNode && return nothing
    if stmt isa Expr && stmt.head == :(=) && stmt.args[1] isa Symbol
        return _component_expansion(plan_var, stmt.args[1], stmt.args[2], source)
    elseif stmt isa Expr && stmt.head == :do
        return _port_expansion(plan_var, stmt, source)
    end
    error("Unsupported @circuit statement: $(stmt).")
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
