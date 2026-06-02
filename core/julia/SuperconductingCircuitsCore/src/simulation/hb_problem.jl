Base.@kwdef struct HBRunSpec
    frequency_sweep
    pump_frequencies::Dict{Symbol,Float64} = Dict{Symbol,Float64}()
    source_currents::Dict{Symbol,Float64} = Dict{Symbol,Float64}()
    optional_hb_kwargs::Dict{Symbol,Any} = Dict{Symbol,Any}()
end

const _OPTIONAL_HB_KWARG_WHITELIST = Set{Symbol}([
    :switchofflinesearchtol,
    :alphamin,
    :iterations,
    :ftol,
    :nbatches,
    :maxintermodorder,
])

const _RESERVED_HBSOLVE_KWARGS = Set{Symbol}([
    :returnS,
    :returnZ,
    :returnQE,
    :returnCM,
    :dc,
    :threewavemixing,
    :fourwavemixing,
    :sorting,
    :keyedarrays,
])

const _KNOWN_HB_OUTPUT_FAMILIES = Set{Symbol}([
    :S,
    :Z,
    :QE,
    :QEideal,
    :CM,
])

struct HBProblemSpec
    compiled::JosephsonCompiledCircuit
    frequencies_hz::Vector{Float64}
    ws::Vector{Float64}
    wp::Tuple
    sources::Vector{Any}
    Nmodulationharmonics::Tuple
    Npumpharmonics::Tuple
    controls::HBSolverControls
    observables::Vector{Any}
    optional_hb_kwargs::Dict{Symbol,Any}
end

struct OutputRequestConfigurationReport
    S::Bool
    Z::Bool
    QE::Bool
    QEideal::Bool
    CM::Bool
end

function _requested_output_families(; returnS::Bool, returnZ::Bool, returnQE::Bool, returnCM::Bool)
    families = Symbol[]
    returnS && push!(families, :S)
    returnZ && push!(families, :Z)
    if returnQE
        push!(families, :QE)
        push!(families, :QEideal)
    end
    returnCM && push!(families, :CM)
    return families
end

function _requested_output_families(controls::HBSolverControls)
    return _requested_output_families(
        returnS=controls.returnS,
        returnZ=controls.returnZ,
        returnQE=controls.returnQE,
        returnCM=controls.returnCM,
    )
end

function _canonical_output_family(family)
    family_symbol = Symbol(family)
    family_symbol in (:S, :s) && return :S
    family_symbol in (:Z, :z) && return :Z
    family_symbol in (:QE, :qe) && return :QE
    family_symbol in (:QEideal, :qeideal, :QEIdeal, :qe_ideal) && return :QEideal
    family_symbol in (:CM, :cm) && return :CM
    return family_symbol
end

function _request_family_enabled(report::OutputRequestConfigurationReport, family)::Bool
    canonical = _canonical_output_family(family)
    canonical == :S && return report.S
    canonical == :Z && return report.Z
    canonical == :QE && return report.QE
    canonical == :QEideal && return report.QEideal
    canonical == :CM && return report.CM
    return false
end

function _validate_known_output_family(family; context::AbstractString="HB output request")
    canonical = _canonical_output_family(family)
    canonical in _KNOWN_HB_OUTPUT_FAMILIES || _validation_error(
        "$(context) uses unknown HB output family '$(family)'. Known output families are $(join(string.(sort(collect(_KNOWN_HB_OUTPUT_FAMILIES); by=string)), ", ")).",
    )
    return canonical
end

function _observable_id_label(observable)
    if hasproperty(observable, :id)
        return string(getproperty(observable, :id))
    elseif observable isa AbstractDict && (haskey(observable, :id) || haskey(observable, "id"))
        return string(get(observable, :id, get(observable, "id", "unknown")))
    end
    return "unknown"
end

function _observable_family(observable)
    observable isa SParameterRequest && return :S
    if hasproperty(observable, :family)
        return _canonical_output_family(getproperty(observable, :family))
    elseif observable isa AbstractDict
        family = get(observable, :family, get(observable, "family", nothing))
        !isnothing(family) && return _canonical_output_family(family)
    end
    return nothing
end

function _tuple_harmonics(value)
    value isa Tuple && return Tuple(Int.(value))
    value isa AbstractVector && return Tuple(Int.(value))
    value isa AbstractDict && return Tuple(Int(value[key]) for key in sort(collect(keys(value)); by=string))
    return (Int(value),)
end

function _pump_harmonics_tuple(value, axes::Vector{PumpAxis})
    if value isa AbstractDict
        return Tuple(Int(value[axis.id]) for axis in axes)
    elseif value isa Tuple || value isa AbstractVector
        result = Tuple(Int.(value))
        length(result) == length(axes) || _validation_error(
            "n_pump_harmonics length must match pump-axis count: expected $(length(axes)), got $(length(result)).",
        )
        return result
    end
    return Tuple(fill(Int(value), length(axes)))
end

function validate_pump_frequency_safety(::JosephsonCompiledCircuit, axis::PumpAxis, value)
    isfinite(value) || _validation_error("Pump frequency for axis '$(axis.id)' must be finite.")
    value > 0 || _validation_error("Pump frequency for axis '$(axis.id)' must be positive.")
    return true
end

function _validate_optional_hb_kwargs_supported(optional_hb_kwargs::AbstractDict)
    keys_as_symbols = Set(Symbol.(keys(optional_hb_kwargs)))
    unsupported = setdiff(keys_as_symbols, _OPTIONAL_HB_KWARG_WHITELIST)
    isempty(unsupported) || _validation_error(
        "Unsupported optional_hb_kwargs key(s): $(join(string.(sort(collect(unsupported); by=string)), ", ")). Supported keys are $(join(string.(sort(collect(_OPTIONAL_HB_KWARG_WHITELIST); by=string)), ", ")).",
    )
    return nothing
end

function _validate_optional_hb_kwargs(optional_hb_kwargs::AbstractDict)
    reserved = intersect(Set(Symbol.(keys(optional_hb_kwargs))), _RESERVED_HBSOLVE_KWARGS)
    isempty(reserved) || _validation_error(
        "optional_hb_kwargs must not override HB solver controls: $(join(string.(sort(collect(reserved); by=string)), ", ")).",
    )
    _validate_optional_hb_kwargs_supported(optional_hb_kwargs)
    return nothing
end

function build_hb_problem(compiled::JosephsonCompiledCircuit, run_spec::HBRunSpec)::HBProblemSpec
    intent = _hb_intent_from(compiled)
    isnothing(intent) && _validation_error("Compiled circuit does not contain HBIntent metadata.")

    frequencies = Float64.(collect(run_spec.frequency_sweep))
    !isempty(frequencies) || _validation_error("HBRunSpec frequency_sweep must contain at least one value.")
    all(frequency -> isfinite(frequency) && frequency > 0, frequencies) ||
        _validation_error("HBRunSpec frequency_sweep values must be finite positive frequencies in Hz.")
    _validate_optional_hb_kwargs(run_spec.optional_hb_kwargs)

    controls = intent.default_solver_controls
    port_map = _compiled_port_map(compiled)

    pump_source_slots = [slot for slot in intent.source_slots if slot.role == :pump]
    !isempty(intent.pump_axes) || _validation_error(
        "HBProblemSpec execution requires at least one PumpAxis. Use pump current 0.0 for pump-off HB execution.",
    )
    !isempty(pump_source_slots) || _validation_error(
        "HBProblemSpec execution requires a pump source slot. Use source current 0.0 for pump-off HB execution.",
    )
    for slot in pump_source_slots
        haskey(run_spec.source_currents, slot.id) || _validation_error(
            "HBRunSpec is missing pump source current binding for source slot '$(slot.id)'. Use 0.0 for pump-off execution.",
        )
    end

    pump_values = Float64[]
    for axis in intent.pump_axes
        haskey(run_spec.pump_frequencies, axis.id) || _validation_error(
            "HBRunSpec is missing pump frequency binding for pump axis '$(axis.id)'.",
        )
        value = run_spec.pump_frequencies[axis.id]
        validate_pump_frequency_safety(compiled, axis, value)
        push!(pump_values, value)
    end

    sources = Any[]
    for slot in intent.source_slots
        mode = Tuple(Int.(slot.mode))
        length(mode) == length(intent.pump_axes) || _validation_error(
            "Source slot '$(slot.id)' mode rank must match pump-axis count.",
        )
        if slot.role == :dc_bias
            _is_dc_mode(mode) || _validation_error(
                "DC bias source slot '$(slot.id)' must use mode (0,).",
            )
            controls.dc || _validation_error(
                "DC bias source slot '$(slot.id)' requires HBSolverControls(dc=true).",
            )
        end
        haskey(run_spec.source_currents, slot.id) || _validation_error(
            "HBRunSpec is missing source current binding for source slot '$(slot.id)'.",
        )
        current = Float64(run_spec.source_currents[slot.id])
        isfinite(current) || _validation_error(
            "Source current binding for source slot '$(slot.id)' must be finite.",
        )
        port_info = get(port_map, slot.port, nothing)
        isnothing(port_info) && _validation_error("Source slot '$(slot.id)' references unknown compiled port '$(slot.port)'.")
        port_index = hasproperty(port_info, :index) ? port_info.index : Int(port_info)
        push!(
            sources,
            (
                mode=mode,
                port=port_index,
                current=current,
            ),
        )
    end

    ws = 2π .* frequencies
    wp = Tuple(2π .* pump_values)
    n_pump = _pump_harmonics_tuple(controls.n_pump_harmonics, intent.pump_axes)
    n_modulation = _tuple_harmonics(controls.n_modulation_harmonics)

    return HBProblemSpec(
        compiled,
        frequencies,
        collect(ws),
        wp,
        sources,
        n_modulation,
        n_pump,
        controls,
        copy(intent.observables),
        copy(run_spec.optional_hb_kwargs),
    )
end

function validate_output_request_configuration(compiled::JosephsonCompiledCircuit, hb_problem::HBProblemSpec)
    compiled === hb_problem.compiled || _validation_error(
        "validate_output_request_configuration must receive the compiled circuit carried by HBProblemSpec.",
    )
    controls = hb_problem.controls
    controls.keyedarrays && _validation_error(
        "HB output extraction currently requires HBSolverControls(keyedarrays=false).",
    )
    report = OutputRequestConfigurationReport(
        controls.returnS,
        controls.returnZ,
        controls.returnQE,
        controls.returnQE,
        controls.returnCM,
    )

    for observable in hb_problem.observables
        family = _observable_family(observable)
        if !isnothing(family)
            family = _validate_known_output_family(
                family;
                context="Observable '$(_observable_id_label(observable))'",
            )
            _request_family_enabled(report, family) || _validation_error(
                "Observable '$(_observable_id_label(observable))' requests output family '$(family)', but HBSolverControls disables that family.",
            )
        end
    end

    return report
end
