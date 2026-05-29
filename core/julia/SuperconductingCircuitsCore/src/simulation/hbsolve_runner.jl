struct HBSolveResult
    frequencies_hz::Vector{Float64}
    raw_solution::Any
    traces::Dict{Symbol,Any}
end

function _frequency_vector_hz(frequency_range_hz)
    if frequency_range_hz isa Tuple && length(frequency_range_hz) == 3
        start_hz, stop_hz, points = frequency_range_hz
        return collect(range(Float64(start_hz), Float64(stop_hz), length=Int(points)))
    end

    return collect(Float64.(frequency_range_hz))
end

function _call_josephson_hbsolve(ws, wp, sources, n_modulation, n_pump, netlist, component_values; kwargs...)
    return JosephsonCircuits.hbsolve(
        ws,
        wp,
        sources,
        n_modulation,
        n_pump,
        netlist,
        component_values;
        kwargs...,
    )
end

function run_hb_problem(problem::HBProblemSpec)
    compiled = problem.compiled
    isempty(compiled.netlist) && _validation_error(
        "HBProblemSpec compiled circuit has an empty netlist. Refusing to execute HB solve without a real compiled circuit.",
    )
    validate_output_request_configuration(compiled, problem)
    _validate_optional_hb_kwargs(problem.optional_hb_kwargs)

    controls = problem.controls
    solution = try
        _call_josephson_hbsolve(
            problem.ws,
            problem.wp,
            problem.sources,
            problem.Nmodulationharmonics,
            problem.Npumpharmonics,
            compiled.netlist,
            Dict(compiled.component_values);
            returnS=controls.returnS,
            returnZ=controls.returnZ,
            returnQE=controls.returnQE,
            returnCM=controls.returnCM,
            dc=controls.dc,
            threewavemixing=controls.threewavemixing,
            fourwavemixing=controls.fourwavemixing,
            sorting=controls.sorting,
            keyedarrays=controls.keyedarrays,
            problem.optional_hb_kwargs...,
        )
    catch err
        err isa FrameworkValidationError && rethrow()
        _validation_error("JosephsonCircuits.hbsolve failed for HBProblemSpec: $(sprint(showerror, err))")
    end

    return HBSolveResult(
        problem.frequencies_hz,
        solution,
        extract_linearized_traces(
            solution;
            requested_families=_requested_output_families(controls),
        ),
    )
end

"""
    run_hbsolve(netlist, component_values, frequency_range_hz; kwargs...)

Run JosephsonCircuits.jl `hbsolve` from the Julia Core.

`frequency_range_hz` is always interpreted in Hz. Pass either a numeric
collection/range or `(start_hz, stop_hz, point_count)`.
"""
function run_hbsolve(
    netlist,
    component_values,
    frequency_range_hz;
    pump_frequencies_hz=(),
    sources=Any[],
    n_modulation_harmonics=1,
    n_pump_harmonics=1,
    port_indices=nothing,
    dc::Bool=false,
    threewavemixing::Bool=false,
    fourwavemixing::Bool=true,
    returnS::Bool=true,
    returnZ::Bool=true,
    returnQE::Bool=true,
    returnCM::Bool=true,
    sorting=:name,
    keyedarrays::Bool=false,
    kwargs...,
)
    frequencies_hz = _frequency_vector_hz(frequency_range_hz)
    _require(!isempty(frequencies_hz), "frequency_range_hz must contain at least one frequency.")
    _require(
        all(f -> isfinite(f) && f > 0, frequencies_hz),
        "frequency_range_hz values must be finite positive frequencies in Hz.",
    )

    ws = 2π .* frequencies_hz
    wp = Tuple(2π .* Float64.(collect(pump_frequencies_hz)))
    _require(!isempty(wp), "pump_frequencies_hz must contain at least one pump frequency; use a source current of 0.0 for pump-off HB execution.")
    _require(!isempty(sources), "sources must contain at least one source entry; use current=0.0 for pump-off HB execution.")
    _require(
        all(f -> isfinite(f) && f > 0, wp),
        "pump_frequencies_hz values must be finite and positive when provided.",
    )
    n_modulation = _tuple_harmonics(n_modulation_harmonics)
    n_pump = if n_pump_harmonics isa Tuple || n_pump_harmonics isa AbstractVector
        result = Tuple(Int.(n_pump_harmonics))
        _require(length(result) == length(wp), "n_pump_harmonics length must match pump_frequencies_hz length.")
        result
    else
        Tuple(fill(Int(n_pump_harmonics), length(wp)))
    end

    keyedarrays && _validation_error(
        "HB output extraction currently requires keyedarrays=false; keyed-array extraction is not supported yet.",
    )

    optional_hb_kwargs = Dict{Symbol,Any}(Symbol(key) => value for (key, value) in pairs(kwargs))
    _validate_optional_hb_kwargs(optional_hb_kwargs)

    solution = _call_josephson_hbsolve(
        ws,
        wp,
        sources,
        n_modulation,
        n_pump,
        netlist,
        Dict(component_values);
        returnS=returnS,
        returnZ=returnZ,
        returnQE=returnQE,
        returnCM=returnCM,
        dc=dc,
        threewavemixing=threewavemixing,
        fourwavemixing=fourwavemixing,
        sorting=sorting,
        keyedarrays=keyedarrays,
        optional_hb_kwargs...,
    )

    return HBSolveResult(
        frequencies_hz,
        solution,
        extract_linearized_traces(
            solution;
            port_indices=port_indices,
            requested_families=_requested_output_families(
                returnS=returnS,
                returnZ=returnZ,
                returnQE=returnQE,
                returnCM=returnCM,
            ),
        ),
    )
end

"""
    run_frequency_sweep(args...; kwargs...)

Semantic alias for frequency-domain JosephsonCircuits sweeps through
`run_hbsolve`. This is a first-class public API name for notebook use.
"""
run_frequency_sweep(args...; kwargs...) = run_hbsolve(args...; kwargs...)
