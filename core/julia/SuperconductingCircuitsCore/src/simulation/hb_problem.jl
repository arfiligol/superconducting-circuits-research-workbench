Base.@kwdef struct HBRunSpec
    frequency_sweep
    pump_frequencies::Dict{Symbol,Float64} = Dict{Symbol,Float64}()
    source_currents::Dict{Symbol,Float64} = Dict{Symbol,Float64}()
    dc_currents::Dict{Symbol,Float64} = Dict{Symbol,Float64}()
    optional_hb_kwargs::Dict{Symbol,Any} = Dict{Symbol,Any}()
end

struct HBProblemSpec
    ws::Vector{Float64}
    wp::Tuple
    sources::Vector{Any}
    Nmodulationharmonics::Tuple
    Npumpharmonics::Tuple
    controls::HBSolverControls
    observables::Vector{Any}
    optional_hb_kwargs::Dict{Symbol,Any}
end

struct OutputCapabilityReport
    S::Bool
    Z::Bool
    QE::Bool
    CM::Bool
end

function _tuple_harmonics(value)
    value isa Tuple && return Tuple(Int.(value))
    value isa AbstractVector && return Tuple(Int.(value))
    value isa AbstractDict && return Tuple(Int(value[key]) for key in sort(collect(keys(value)); by=string))
    return (Int(value),)
end

function _pump_harmonics_tuple(value, axes::Vector{PumpAxis})
    isempty(axes) && return ()
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

function build_hb_problem(compiled::JosephsonCompiledCircuit, run_spec::HBRunSpec)::HBProblemSpec
    intent = _hb_intent_from(compiled)
    isnothing(intent) && _validation_error("Compiled circuit does not contain HBIntent metadata.")

    frequencies = Float64.(collect(run_spec.frequency_sweep))
    !isempty(frequencies) || _validation_error("HBRunSpec frequency_sweep must contain at least one value.")
    all(>(0), frequencies) || _validation_error("HBRunSpec frequency_sweep values must be positive.")

    controls = intent.default_solver_controls
    port_map = _compiled_port_map(compiled)

    pump_values = Float64[]
    for axis in intent.pump_axes
        haskey(run_spec.pump_frequencies, axis.id) || _validation_error(
            "HBRunSpec is missing pump frequency binding for pump axis '$(axis.id)'.",
        )
        value = run_spec.pump_frequencies[axis.id]
        value > 0 || _validation_error("Pump frequency for axis '$(axis.id)' must be positive.")
        push!(pump_values, value)
    end

    sources = Any[]
    for slot in intent.source_slots
        haskey(run_spec.source_currents, slot.id) || _validation_error(
            "HBRunSpec is missing source current binding for source slot '$(slot.id)'.",
        )
        port_info = get(port_map, slot.port, nothing)
        isnothing(port_info) && _validation_error("Source slot '$(slot.id)' references unknown compiled port '$(slot.port)'.")
        port_index = hasproperty(port_info, :index) ? port_info.index : Int(port_info)
        push!(
            sources,
            (
                mode=slot.mode,
                port=port_index,
                current=Float64(run_spec.source_currents[slot.id]),
            ),
        )
    end

    ws = 2π .* frequencies
    wp = Tuple(2π .* pump_values)
    n_pump = _pump_harmonics_tuple(controls.n_pump_harmonics, intent.pump_axes)
    n_modulation = _tuple_harmonics(controls.n_modulation_harmonics)

    return HBProblemSpec(
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

function validate_output_capabilities(::JosephsonCompiledCircuit, hb_problem::HBProblemSpec)
    controls = hb_problem.controls
    return OutputCapabilityReport(
        controls.returnS,
        controls.returnZ,
        controls.returnQE,
        controls.returnCM,
    )
end

function run_hb_problem(::HBProblemSpec)
    _validation_error("run_hb_problem is not implemented for this HBProblemSpec yet. Refusing to generate substitute solver traces.")
end
