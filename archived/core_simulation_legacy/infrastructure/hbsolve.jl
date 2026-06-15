#=
Julia Simulation Bridge for JosephsonCircuits.jl

This file provides wrapper functions that are called from Python via JuliaCall.
It simplifies the interface between Python domain models and Julia's hbsolve.
=#

using JosephsonCircuits

function is_zero_mode(mode)
    return all(v == 0 for v in mode)
end

function mode_token(mode)
    return join(string.(Int.(collect(mode))), ",")
end

function mode_trace_label(outputmode, outputport, inputmode, inputport)
    return "om=$(mode_token(outputmode))|op=$(Int(outputport))|im=$(mode_token(inputmode))|ip=$(Int(inputport))"
end

function cm_trace_label(outputmode, outputport)
    return "om=$(mode_token(outputmode))|op=$(Int(outputport))"
end

function flattened_mode_port_index(mode_index, port_index, mode_count)
    return mode_index + (port_index - 1) * mode_count
end

function collect_mode_parameter_traces(parameter_array, modes, portnumbers)
    traces_real = Dict{String, Vector{Float64}}()
    traces_imag = Dict{String, Vector{Float64}}()

    if isempty(parameter_array)
        return traces_real, traces_imag
    end

    mode_count = length(modes)
    for outputmode_index in eachindex(modes)
        outputmode = modes[outputmode_index]
        for outputport_index in eachindex(portnumbers)
            outputport = portnumbers[outputport_index]
            row_index = flattened_mode_port_index(outputmode_index, outputport_index, mode_count)
            for inputmode_index in eachindex(modes)
                inputmode = modes[inputmode_index]
                for inputport_index in eachindex(portnumbers)
                    inputport = portnumbers[inputport_index]
                    column_index = flattened_mode_port_index(
                        inputmode_index,
                        inputport_index,
                        mode_count
                    )
                    label = mode_trace_label(outputmode, outputport, inputmode, inputport)
                    trace = vec(parameter_array[row_index, column_index, :])
                    traces_real[label] = collect(real.(trace))
                    traces_imag[label] = collect(imag.(trace))
                end
            end
        end
    end

    return traces_real, traces_imag
end

function collect_mode_scalar_traces(parameter_array, modes, portnumbers)
    traces = Dict{String, Vector{Float64}}()

    if isempty(parameter_array)
        return traces
    end

    mode_count = length(modes)
    for outputmode_index in eachindex(modes)
        outputmode = modes[outputmode_index]
        for outputport_index in eachindex(portnumbers)
            outputport = portnumbers[outputport_index]
            row_index = flattened_mode_port_index(outputmode_index, outputport_index, mode_count)
            for inputmode_index in eachindex(modes)
                inputmode = modes[inputmode_index]
                for inputport_index in eachindex(portnumbers)
                    inputport = portnumbers[inputport_index]
                    column_index = flattened_mode_port_index(
                        inputmode_index,
                        inputport_index,
                        mode_count
                    )
                    label = mode_trace_label(outputmode, outputport, inputmode, inputport)
                    trace = vec(parameter_array[row_index, column_index, :])
                    traces[label] = collect(Float64.(trace))
                end
            end
        end
    end

    return traces
end

function collect_mode_cm_traces(parameter_array, modes, portnumbers)
    traces = Dict{String, Vector{Float64}}()

    if isempty(parameter_array)
        return traces
    end

    mode_count = length(modes)
    for outputmode_index in eachindex(modes)
        outputmode = modes[outputmode_index]
        for outputport_index in eachindex(portnumbers)
            outputport = portnumbers[outputport_index]
            row_index = flattened_mode_port_index(outputmode_index, outputport_index, mode_count)
            label = cm_trace_label(outputmode, outputport)
            trace = vec(parameter_array[row_index, :])
            traces[label] = collect(Float64.(trace))
        end
    end

    return traces
end

function collect_mode_admittance_traces(z_parameter_array, modes, portnumbers)
    y_traces_real = Dict{String, Vector{Float64}}()
    y_traces_imag = Dict{String, Vector{Float64}}()

    if isempty(z_parameter_array)
        return y_traces_real, y_traces_imag
    end

    frequency_count = size(z_parameter_array, 3)
    matrix_size = size(z_parameter_array, 1)
    nan_value = ComplexF64(NaN, NaN)
    y_parameter_array = Array{ComplexF64}(undef, matrix_size, matrix_size, frequency_count)

    for frequency_index in 1:frequency_count
        z_matrix = z_parameter_array[:, :, frequency_index]
        y_parameter_array[:, :, frequency_index] = try
            JosephsonCircuits.ZtoY(z_matrix)
        catch
            fill(nan_value, matrix_size, matrix_size)
        end
    end

    return collect_mode_parameter_traces(y_parameter_array, modes, portnumbers)
end

function collect_zero_mode_sparameters_from_raw(s_parameter_array, modes, portnumbers, requested_port_indices)
    s_traces_real = Dict{String, Vector{Float64}}()
    s_traces_imag = Dict{String, Vector{Float64}}()

    if isempty(s_parameter_array)
        return s_traces_real, s_traces_imag
    end

    zero_mode_index = findfirst(is_zero_mode, modes)
    if isnothing(zero_mode_index)
        return s_traces_real, s_traces_imag
    end

    mode_count = length(modes)
    port_lookup = Dict(Int(portnumbers[idx]) => idx for idx in eachindex(portnumbers))
    for output_port in sort(Int.(collect(requested_port_indices)))
        outputport_index = get(port_lookup, output_port, nothing)
        if isnothing(outputport_index)
            continue
        end
        row_index = flattened_mode_port_index(zero_mode_index, outputport_index, mode_count)
        for input_port in sort(Int.(collect(requested_port_indices)))
            inputport_index = get(port_lookup, input_port, nothing)
            if isnothing(inputport_index)
                continue
            end
            column_index = flattened_mode_port_index(zero_mode_index, inputport_index, mode_count)
            label = "S$(output_port)$(input_port)"
            trace = vec(s_parameter_array[row_index, column_index, :])
            s_traces_real[label] = collect(real.(trace))
            s_traces_imag[label] = collect(imag.(trace))
        end
    end

    return s_traces_real, s_traces_imag
end

function resolve_compatibility_trace(s_traces_real, s_traces_imag)
    if haskey(s_traces_real, "S11") && haskey(s_traces_imag, "S11")
        return s_traces_real["S11"], s_traces_imag["S11"]
    end

    if isempty(s_traces_real) || isempty(s_traces_imag)
        return Float64[], Float64[]
    end

    first_label = sort(collect(keys(s_traces_real)))[1]
    return s_traces_real[first_label], s_traces_imag[first_label]
end

"""
    run_lc_simulation(L_nH, C_pF, f_start_GHz, f_stop_GHz, n_points)

Simulate a simple LC resonator and return S11 data.

# Arguments
- `L_nH`: Inductance in nanohenries
- `C_pF`: Capacitance in picofarads
- `f_start_GHz`: Start frequency in GHz
- `f_stop_GHz`: Stop frequency in GHz
- `n_points`: Number of frequency points

# Returns
Dict with keys: :frequencies_ghz, :s11_real, :s11_imag
"""
function run_lc_simulation(L_nH::Float64, C_pF::Float64,
    f_start_GHz::Float64, f_stop_GHz::Float64,
    n_points::Int)
    # Unit conversions
    nH = 1e-9
    pF = 1e-12
    GHz = 1e9

    # Define circuit
    @variables L C R50

    circuit = [
        ("P1", "1", "0", 1),      # Port 1
        ("R50", "1", "0", R50),   # 50Ω impedance
        ("L", "1", "2", L),       # Inductor
        ("C", "2", "0", C),       # Capacitor
    ]

    circuitdefs = Dict(
        L => L_nH * nH,
        C => C_pF * pF,
        R50 => 50.0,
    )

    # Frequency range
    frequencies = range(f_start_GHz, f_stop_GHz, length=n_points) .* GHz
    ws = 2π .* frequencies

    # Pump configuration (for hbsolve)
    wp = (2π * 5.0GHz,)  # Default pump at 5 GHz
    sources = [(mode=(1,), port=1, current=0.0)]

    # Run simulation
    sol = hbsolve(
        ws,
        wp,
        sources,
        (10,),
        (20,),
        circuit,
        circuitdefs;
        returnZ=true,
        returnQE=true,
        returnCM=true,
        keyedarrays=Val(false)
    )

    port_indices = [1]
    mode_indices = [Int.(collect(mode)) for mode in sol.linearized.modes]
    s_traces_real, s_traces_imag = collect_zero_mode_sparameters_from_raw(
        sol.linearized.S,
        sol.linearized.modes,
        sol.linearized.portnumbers,
        port_indices
    )
    s_mode_real, s_mode_imag = collect_mode_parameter_traces(
        sol.linearized.S,
        sol.linearized.modes,
        sol.linearized.portnumbers
    )
    z_mode_real, z_mode_imag = collect_mode_parameter_traces(
        sol.linearized.Z,
        sol.linearized.modes,
        sol.linearized.portnumbers
    )
    y_mode_real, y_mode_imag = collect_mode_admittance_traces(
        sol.linearized.Z,
        sol.linearized.modes,
        sol.linearized.portnumbers
    )
    qe_mode = collect_mode_scalar_traces(
        sol.linearized.QE,
        sol.linearized.modes,
        sol.linearized.portnumbers
    )
    qe_ideal_mode = collect_mode_scalar_traces(
        sol.linearized.QEideal,
        sol.linearized.modes,
        sol.linearized.portnumbers
    )
    cm_mode = collect_mode_cm_traces(
        sol.linearized.CM,
        sol.linearized.modes,
        sol.linearized.portnumbers
    )
    s11_real, s11_imag = resolve_compatibility_trace(s_traces_real, s_traces_imag)

    return Dict(
        :frequencies_ghz => collect(frequencies ./ GHz),
        :s11_real => s11_real,
        :s11_imag => s11_imag,
        :port_indices => port_indices,
        :mode_indices => mode_indices,
        :s_parameter_real => s_traces_real,
        :s_parameter_imag => s_traces_imag,
        :s_parameter_mode_real => s_mode_real,
        :s_parameter_mode_imag => s_mode_imag,
        :z_parameter_mode_real => z_mode_real,
        :z_parameter_mode_imag => z_mode_imag,
        :y_parameter_mode_real => y_mode_real,
        :y_parameter_mode_imag => y_mode_imag,
        :qe_parameter_mode => qe_mode,
        :qe_ideal_parameter_mode => qe_ideal_mode,
        :cm_parameter_mode => cm_mode
    )
end


"""
    run_custom_simulation(topology, component_values, f_start_GHz, f_stop_GHz, n_points,
        pump_freqs_GHz, source_currents_A, source_ports, source_modes,
        n_modulation_harmonics, n_pump_harmonics,
        dc, threewavemixing, fourwavemixing,
        max_intermod_order, max_iterations, ftol, switchofflinesearchtol, alphamin,
        port_indices)

Simulate a custom circuit topology.

# Arguments
- `topology`: Vector of tuples (name, node1, node2, value_key)
- `component_values`: Dict mapping value keys to actual values (with units)
- `f_start_GHz`, `f_stop_GHz`, `n_points`: Signal frequency sweep parameters
- `pump_freqs_GHz`: Pump frequency list
- `source_currents_A`, `source_ports`, `source_modes`: Source list entries
- `n_modulation_harmonics`, `n_pump_harmonics`: Harmonic truncation settings
- `dc`, `threewavemixing`, `fourwavemixing`: hbsolve keyword toggles
- `max_intermod_order`, `max_iterations`, `ftol`, `switchofflinesearchtol`, `alphamin`: Solver controls

# Returns
Dict with keys: :frequencies_ghz, :s11_real, :s11_imag
"""
function run_custom_simulation(topology,
    component_values,
    f_start_GHz::Float64,
    f_stop_GHz::Float64,
    n_points::Int,
    pump_freqs_GHz,
    source_currents_A,
    source_ports,
    source_modes,
    n_modulation_harmonics::Int,
    n_pump_harmonics::Int,
    dc::Bool,
    threewavemixing::Bool,
    fourwavemixing::Bool,
    max_intermod_order::Int,
    max_iterations::Int,
    ftol::Float64,
    switchofflinesearchtol::Float64,
    alphamin::Float64,
    port_indices)
    GHz = 1e9

    # Convert Python types to native Julia types
    circuit = [(t[1], t[2], t[3], t[4]) for t in topology]
    cv_dict = Dict(component_values)

    # Frequency range
    frequencies = range(f_start_GHz, f_stop_GHz, length=n_points) .* GHz
    ws = 2π .* frequencies

    # Pump/source configuration
    pump_freqs = [Float64(v) for v in pump_freqs_GHz]
    currents = [Float64(v) for v in source_currents_A]
    ports = [Int(v) for v in source_ports]
    modes = [Tuple(Int(v) for v in mode_vec) for mode_vec in source_modes]
    if !(length(currents) == length(ports) == length(modes))
        error(
            "Source vector length mismatch: currents=$(length(currents)), "
            * "ports=$(length(ports)), modes=$(length(modes))."
        )
    end
    if isempty(currents)
        error("At least one source is required.")
    end
    if isempty(pump_freqs)
        error("At least one pump frequency is required.")
    end

    for (idx, mode) in enumerate(modes)
        if length(mode) != length(pump_freqs)
            error(
                "source_modes[$idx] length $(length(mode)) does not match "
                * "number of pump frequencies $(length(pump_freqs))."
            )
        end
    end

    wp = Tuple(2π * pump_freq * GHz for pump_freq in pump_freqs)
    sources = [
        (mode=modes[i], port=ports[i], current=ComplexF64(currents[i], 0.0))
        for i in eachindex(currents)
    ]
    Nmodulationharmonics = Tuple(fill(n_modulation_harmonics, length(wp)))
    Npumpharmonics = Tuple(fill(n_pump_harmonics, length(wp)))
    maxintermodorder = max_intermod_order < 0 ? Inf : float(max_intermod_order)

    # Run simulation
    sol = hbsolve(
        ws,
        wp,
        sources,
        Nmodulationharmonics,
        Npumpharmonics,
        circuit,
        cv_dict;
        dc=dc,
        threewavemixing=threewavemixing,
        fourwavemixing=fourwavemixing,
        maxintermodorder=maxintermodorder,
        iterations=max_iterations,
        ftol=ftol,
        switchofflinesearchtol=switchofflinesearchtol,
        alphamin=alphamin,
        returnZ=true,
        returnQE=true,
        returnCM=true,
        keyedarrays=Val(false)
    )

    sorted_port_indices = sort(Int.(collect(port_indices)))
    mode_indices = [Int.(collect(mode)) for mode in sol.linearized.modes]
    s_traces_real, s_traces_imag = collect_zero_mode_sparameters_from_raw(
        sol.linearized.S,
        sol.linearized.modes,
        sol.linearized.portnumbers,
        sorted_port_indices
    )
    s_mode_real, s_mode_imag = collect_mode_parameter_traces(
        sol.linearized.S,
        sol.linearized.modes,
        sol.linearized.portnumbers
    )
    z_mode_real, z_mode_imag = collect_mode_parameter_traces(
        sol.linearized.Z,
        sol.linearized.modes,
        sol.linearized.portnumbers
    )
    y_mode_real, y_mode_imag = collect_mode_admittance_traces(
        sol.linearized.Z,
        sol.linearized.modes,
        sol.linearized.portnumbers
    )
    qe_mode = collect_mode_scalar_traces(
        sol.linearized.QE,
        sol.linearized.modes,
        sol.linearized.portnumbers
    )
    qe_ideal_mode = collect_mode_scalar_traces(
        sol.linearized.QEideal,
        sol.linearized.modes,
        sol.linearized.portnumbers
    )
    cm_mode = collect_mode_cm_traces(
        sol.linearized.CM,
        sol.linearized.modes,
        sol.linearized.portnumbers
    )
    s11_real, s11_imag = resolve_compatibility_trace(s_traces_real, s_traces_imag)

    return Dict(
        :frequencies_ghz => collect(frequencies ./ GHz),
        :s11_real => s11_real,
        :s11_imag => s11_imag,
        :port_indices => sorted_port_indices,
        :mode_indices => mode_indices,
        :s_parameter_real => s_traces_real,
        :s_parameter_imag => s_traces_imag,
        :s_parameter_mode_real => s_mode_real,
        :s_parameter_mode_imag => s_mode_imag,
        :z_parameter_mode_real => z_mode_real,
        :z_parameter_mode_imag => z_mode_imag,
        :y_parameter_mode_real => y_mode_real,
        :y_parameter_mode_imag => y_mode_imag,
        :qe_parameter_mode => qe_mode,
        :qe_ideal_parameter_mode => qe_ideal_mode,
        :cm_parameter_mode => cm_mode
    )
end


"""
    run_lc_parameter_sweep(L_values_nH, C_values_pF, f_start_GHz, f_stop_GHz, n_points)

Run a 2D parameter sweep over L and C values entirely in Julia for performance.
Uses multithreading for parallel execution.

# Arguments
- `L_values_nH`: Vector of inductance values in nH
- `C_values_pF`: Vector of capacitance values in pF
- `f_start_GHz`, `f_stop_GHz`, `n_points`: Frequency sweep parameters

# Returns
Dict with:
- :frequencies_ghz: 1D vector of frequencies
- :L_values_nh: 1D vector of L values
- :C_values_pf: 1D vector of C values
- :s11_magnitude: 3D array [L_idx, C_idx, freq_idx]
- :resonance_freqs_ghz: 2D array [L_idx, C_idx] of found resonances
"""
function run_lc_parameter_sweep(L_values_nH::Vector{Float64},
    C_values_pF::Vector{Float64},
    f_start_GHz::Float64,
    f_stop_GHz::Float64,
    n_points::Int)
    nH = 1e-9
    pF = 1e-12
    GHz = 1e9

    n_L = length(L_values_nH)
    n_C = length(C_values_pF)

    # Preallocate result arrays
    frequencies = range(f_start_GHz, f_stop_GHz, length=n_points) .* GHz
    s11_magnitude = zeros(n_L, n_C, n_points)
    resonance_freqs = zeros(n_L, n_C)

    # Circuit template
    @variables L C R50
    circuit = [
        ("P1", "1", "0", 1),
        ("R50", "1", "0", R50),
        ("L", "1", "2", L),
        ("C", "2", "0", C),
    ]

    ws = 2π .* frequencies
    wp = (2π * 5.0GHz,)
    sources = [(mode=(1,), port=1, current=0.0)]

    # Sweep over all L, C combinations (fully in Julia with threading)
    Threads.@threads for i in 1:n_L
        for j in 1:n_C
            circuitdefs = Dict(
                L => L_values_nH[i] * nH,
                C => C_values_pF[j] * pF,
                R50 => 50.0,
            )

            sol = hbsolve(ws, wp, sources, (10,), (20,), circuit, circuitdefs)
            S11 = sol.linearized.S(outputmode=(0,), outputport=1, inputmode=(0,), inputport=1, freqindex=:)

            mag = abs.(S11)
            s11_magnitude[i, j, :] = mag

            # Find resonance (minimum S11)
            min_idx = argmin(mag)
            resonance_freqs[i, j] = frequencies[min_idx] / GHz
        end
    end

    return Dict(
        :frequencies_ghz => collect(frequencies ./ GHz),
        :L_values_nh => L_values_nH,
        :C_values_pf => C_values_pF,
        :s11_magnitude => s11_magnitude,
        :resonance_freqs_ghz => resonance_freqs
    )
end
