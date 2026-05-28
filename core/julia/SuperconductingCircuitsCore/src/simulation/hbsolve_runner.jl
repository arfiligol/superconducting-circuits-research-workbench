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
    _require(all(f -> f > 0, frequencies_hz), "frequency_range_hz values must be positive.")

    ws = 2π .* frequencies_hz
    wp = Tuple(2π .* Float64.(collect(pump_frequencies_hz)))
    _require(all(>(0), wp), "pump_frequencies_hz values must be positive when provided.")
    n_modulation = _tuple_harmonics(n_modulation_harmonics)
    n_pump = if n_pump_harmonics isa Tuple || n_pump_harmonics isa AbstractVector
        result = Tuple(Int.(n_pump_harmonics))
        _require(length(result) == length(wp), "n_pump_harmonics length must match pump_frequencies_hz length.")
        result
    else
        Tuple(fill(Int(n_pump_harmonics), length(wp)))
    end

    solution = JosephsonCircuits.hbsolve(
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
        kwargs...,
    )

    return HBSolveResult(
        frequencies_hz,
        solution,
        extract_linearized_traces(solution; port_indices=port_indices),
    )
end

"""
    run_frequency_sweep(args...; kwargs...)

Semantic alias for frequency-domain JosephsonCircuits sweeps through
`run_hbsolve`. This is a first-class public API name for notebook use.
"""
run_frequency_sweep(args...; kwargs...) = run_hbsolve(args...; kwargs...)
