Base.@kwdef struct PumpAxis
    id::Symbol
    frequency_parameter::Symbol
end

Base.@kwdef struct HBSourceSlot
    id::Symbol
    role::Symbol
    port::Symbol
    mode::Tuple
    current_parameter::Symbol
end

Base.@kwdef struct SParameterRequest
    id::Symbol
    outputmode::Tuple
    outputport::Symbol
    inputmode::Tuple
    inputport::Symbol
end

Base.@kwdef struct HBSolverControls
    n_pump_harmonics::Any = ()
    n_modulation_harmonics::Any = 0
    dc::Bool = false
    threewavemixing::Bool = false
    fourwavemixing::Bool = true
    returnS::Bool = true
    returnZ::Bool = true
    returnQE::Bool = true
    returnCM::Bool = true
    sorting::Symbol = :name
    keyedarrays::Bool = false
end

Base.@kwdef struct HBIntent
    pump_axes::Vector{PumpAxis} = PumpAxis[]
    source_slots::Vector{HBSourceSlot} = HBSourceSlot[]
    observables::Vector{Any} = Any[]
    default_solver_controls::HBSolverControls = HBSolverControls()
end

function hb_intent!(
    plan::CircuitPlan;
    pump_axes=PumpAxis[],
    source_slots=HBSourceSlot[],
    observables=Any[],
    default_solver_controls=HBSolverControls(),
)
    intent = HBIntent(
        PumpAxis[pump_axes...],
        HBSourceSlot[source_slots...],
        Any[observables...],
        default_solver_controls,
    )
    plan.metadata[:hb_intent] = intent
    plan.engineering_graph.hb_overlay = (
        pump_axes=intent.pump_axes,
        source_slots=intent.source_slots,
        observables=intent.observables,
    )
    return intent
end

function _hb_intent_from(plan::CircuitPlan)
    return get(plan.metadata, :hb_intent, nothing)
end

function _hb_intent_from(compiled::JosephsonCompiledCircuit)
    return get(compiled.metadata, :hb_intent, nothing)
end

function _compiled_port_map(compiled::JosephsonCompiledCircuit)
    !isempty(compiled.port_map) && return compiled.port_map
    raw = get(compiled.metadata, :external_ports, Dict{String,Int}())
    return Dict(Symbol(name) => (index=index,) for (name, index) in raw)
end

function _validate_hb_intent_issues(intent, port_ids)
    issues = ValidationIssue[]
    isnothing(intent) && return issues

    axis_ids = Set(axis.id for axis in intent.pump_axes)
    length(axis_ids) == length(intent.pump_axes) || _issue!(
        issues,
        :error,
        :duplicate_pump_axis_id,
        "HBIntent pump axis IDs must be unique.",
        [:hb_intent, :pump_axes];
        stage=:compile_validation,
    )

    slot_ids = Set(slot.id for slot in intent.source_slots)
    length(slot_ids) == length(intent.source_slots) || _issue!(
        issues,
        :error,
        :duplicate_source_slot_id,
        "HBIntent source slot IDs must be unique.",
        [:hb_intent, :source_slots];
        stage=:compile_validation,
    )

    pump_axis_count = length(intent.pump_axes)
    for slot in intent.source_slots
        slot.port in port_ids || _issue!(
            issues,
            :error,
            :unknown_source_slot_port,
            "Source slot '$(slot.id)' references unknown port '$(slot.port)'.",
            [:hb_intent, :source_slots];
            stage=:compile_validation,
            object_id=string(slot.id),
            expected=collect(port_ids),
            actual=slot.port,
        )
        length(slot.mode) == pump_axis_count || _issue!(
            issues,
            :error,
            :source_mode_rank_mismatch,
            "Source slot '$(slot.id)' mode rank must match pump-axis count.",
            [:hb_intent, :source_slots];
            stage=:compile_validation,
            object_id=string(slot.id),
            expected=pump_axis_count,
            actual=length(slot.mode),
        )
    end

    observable_ids = Set{Symbol}()
    for observable in intent.observables
        if hasproperty(observable, :id)
            observable_id = getproperty(observable, :id)
            observable_id in observable_ids && _issue!(
                issues,
                :error,
                :duplicate_observable_id,
                "Observable ID '$(observable_id)' is declared more than once.",
                [:hb_intent, :observables];
                stage=:compile_validation,
                object_id=string(observable_id),
            )
            push!(observable_ids, observable_id)
        end
        if observable isa SParameterRequest
            observable.outputport in port_ids || _issue!(
                issues,
                :error,
                :unknown_observable_output_port,
                "Observable '$(observable.id)' references unknown output port '$(observable.outputport)'.",
                [:hb_intent, :observables];
                stage=:compile_validation,
                object_id=string(observable.id),
            )
            observable.inputport in port_ids || _issue!(
                issues,
                :error,
                :unknown_observable_input_port,
                "Observable '$(observable.id)' references unknown input port '$(observable.inputport)'.",
                [:hb_intent, :observables];
                stage=:compile_validation,
                object_id=string(observable.id),
            )
            length(observable.outputmode) == pump_axis_count || _issue!(
                issues,
                :error,
                :observable_output_mode_rank_mismatch,
                "Observable '$(observable.id)' output mode rank must match pump-axis count.",
                [:hb_intent, :observables];
                stage=:compile_validation,
                object_id=string(observable.id),
            )
            length(observable.inputmode) == pump_axis_count || _issue!(
                issues,
                :error,
                :observable_input_mode_rank_mismatch,
                "Observable '$(observable.id)' input mode rank must match pump-axis count.",
                [:hb_intent, :observables];
                stage=:compile_validation,
                object_id=string(observable.id),
            )
        end
    end

    return issues
end

function validate_hb_intent(plan::CircuitPlan)::ValidationReport
    intent = _hb_intent_from(plan)
    port_ids = Set(keys(plan.engineering_graph.ports))
    return ValidationReport(_validate_hb_intent_issues(intent, port_ids))
end

function validate_hb_intent(compiled::JosephsonCompiledCircuit)::ValidationReport
    intent = _hb_intent_from(compiled)
    port_ids = Set(keys(_compiled_port_map(compiled)))
    return ValidationReport(_validate_hb_intent_issues(intent, port_ids))
end
