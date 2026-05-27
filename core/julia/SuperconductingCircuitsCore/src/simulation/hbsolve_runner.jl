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
    pump_frequencies_hz=(8.001e9,),
    sources=[(mode=(1,), port=1, current=0.0)],
    n_modulation_harmonics=1,
    n_pump_harmonics=1,
    port_indices=nothing,
    dc::Bool=false,
    threewavemixing::Bool=false,
    fourwavemixing::Bool=true,
    returnS::Bool=true,
    returnZ::Bool=true,
    returnQE::Bool=false,
    returnCM::Bool=false,
    sorting=:name,
    keyedarrays::Bool=false,
    kwargs...,
)
    frequencies_hz = _frequency_vector_hz(frequency_range_hz)
    _require(!isempty(frequencies_hz), "frequency_range_hz must contain at least one frequency.")
    _require(all(f -> f > 0, frequencies_hz), "frequency_range_hz values must be positive.")
    _require(!isempty(pump_frequencies_hz), "pump_frequencies_hz must contain at least one frequency.")
    _require(!isempty(sources), "sources must contain at least one source.")

    ws = 2π .* frequencies_hz
    wp = Tuple(2π .* Float64.(collect(pump_frequencies_hz)))
    n_modulation = Tuple(fill(Int(n_modulation_harmonics), length(wp)))
    n_pump = Tuple(fill(Int(n_pump_harmonics), length(wp)))

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
