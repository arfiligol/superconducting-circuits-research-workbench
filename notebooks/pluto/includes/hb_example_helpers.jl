module HBExampleHelpers

using LinearAlgebra
using SuperconductingCircuitsCore

import SuperconductingCircuitsCore:
    component_id,
    component_pins,
    component_lines,
    default_line,
    component_parameters

export GroundedResonator,
    ReadoutLine,
    HangingQuarterWaveResonator,
    db20,
    phase_deg,
    mode_label,
    zero_mode_s,
    zero_mode_z,
    zero_mode_z_matrix,
    zero_mode_y_matrix,
    mode_trace,
    build_grounded_lc_example,
    build_readout_line_hanging_qwr_example

Base.@kwdef struct GroundedResonator <: AbstractCircuitComponent
    id::String = "res"
    capacitance::Float64
    inductance::Float64
end

component_id(component::GroundedResonator) = component.id
component_pins(::GroundedResonator) = [:signal]
component_lines(::GroundedResonator) = Symbol[]
default_line(::GroundedResonator) = nothing

function component_parameters(component::GroundedResonator)
    return [
        ParameterMetadata(
            name=:capacitance,
            role=NumericParameter(),
            owner=component.id,
            targets=[:capacitance],
            sweep_name=:capacitance,
            units="F",
            assumptions=["changing capacitance does not change component topology"],
        ),
        ParameterMetadata(
            name=:inductance,
            role=NumericParameter(),
            owner=component.id,
            targets=[:inductance],
            sweep_name=:inductance,
            units="H",
            assumptions=["changing inductance does not change component topology"],
        ),
    ]
end

Base.@kwdef struct ReadoutLine <: AbstractCircuitComponent
    id::String = "readout_line"
    section_count::Int = 2
    series_inductance::Float64
    shunt_capacitance::Float64
end

component_id(component::ReadoutLine) = component.id
component_pins(::ReadoutLine) = [:input, :output]
component_lines(::ReadoutLine) = Symbol[]
default_line(::ReadoutLine) = nothing

function component_parameters(component::ReadoutLine)
    return [
        ParameterMetadata(
            name=:readout_series_inductance,
            role=NumericParameter(),
            owner=component.id,
            targets=[:series_inductance],
            sweep_name=:readout_series_inductance,
            units="H",
            assumptions=["changing section inductance does not change ladder topology"],
        ),
        ParameterMetadata(
            name=:readout_shunt_capacitance,
            role=NumericParameter(),
            owner=component.id,
            targets=[:shunt_capacitance],
            sweep_name=:readout_shunt_capacitance,
            units="F",
            assumptions=["changing shunt capacitance does not change ladder topology"],
        ),
    ]
end

Base.@kwdef struct HangingQuarterWaveResonator <: AbstractCircuitComponent
    id::String = "qwr"
    section_count::Int = 2
    series_inductance::Float64
    shunt_capacitance::Float64
end

component_id(component::HangingQuarterWaveResonator) = component.id
component_pins(::HangingQuarterWaveResonator) = [:coupling]
component_lines(::HangingQuarterWaveResonator) = Symbol[]
default_line(::HangingQuarterWaveResonator) = nothing

function component_parameters(component::HangingQuarterWaveResonator)
    return [
        ParameterMetadata(
            name=:resonator_series_inductance,
            role=NumericParameter(),
            owner=component.id,
            targets=[:series_inductance],
            sweep_name=:resonator_series_inductance,
            units="H",
            assumptions=["changing section inductance shifts the resonator frequency without changing ladder topology"],
        ),
        ParameterMetadata(
            name=:resonator_shunt_capacitance,
            role=NumericParameter(),
            owner=component.id,
            targets=[:shunt_capacitance],
            sweep_name=:resonator_shunt_capacitance,
            units="F",
            assumptions=["changing shunt capacitance shifts the resonator frequency without changing ladder topology"],
        ),
    ]
end

db20(values) = 20 .* log10.(abs.(values))
phase_deg(values) = rad2deg.(angle.(values))

function _mode_token(mode)
    return join(string.(Int.(collect(mode))), ",")
end

function mode_label(; outputmode=(0,), outputport::Integer, inputmode=(0,), inputport::Integer)
    output_token = _mode_token(outputmode)
    input_token = _mode_token(inputmode)
    return "om=$(output_token)|op=$(Int(outputport))|im=$(input_token)|ip=$(Int(inputport))"
end

mode_label(outputmode, outputport::Integer, inputmode, inputport::Integer) =
    mode_label(; outputmode=outputmode, outputport=outputport, inputmode=inputmode, inputport=inputport)

function _available_labels(traces)
    return join(sort(string.(collect(keys(traces)))), ", ")
end

function _trace_family(result, family::Symbol)
    traces = get(result.traces, family, nothing)
    traces isa AbstractDict || error("result.traces does not contain :$(family).")
    return traces
end

function _trace_value(result, family::Symbol, label::String)
    traces = _trace_family(result, family)
    haskey(traces, label) ||
        error(
            "result.traces[:$(family)] does not contain $(label). Available labels: $(_available_labels(traces))",
        )
    return traces[label]
end

function zero_mode_s(result, output_port::Integer, input_port::Integer)
    return _trace_value(result, :zero_mode_s, "S$(Int(output_port))$(Int(input_port))")
end

function mode_trace(
    result,
    family::Symbol;
    outputmode=(0,),
    outputport::Integer,
    inputmode=(0,),
    inputport::Integer,
)
    label = mode_label(
        outputmode=outputmode,
        outputport=outputport,
        inputmode=inputmode,
        inputport=inputport,
    )
    return _trace_value(result, family, label)
end

function zero_mode_z(result, output_port::Integer, input_port::Integer)
    return mode_trace(
        result,
        :z_parameter_mode;
        outputmode=(0,),
        outputport=output_port,
        inputmode=(0,),
        inputport=input_port,
    )
end

function _matrix_ports(result, ports)
    if isnothing(ports)
        trace_ports = get(result.traces, :portnumbers, nothing)
        isnothing(trace_ports) &&
            error("ports must be provided when result.traces does not contain :portnumbers.")
        return Int.(collect(trace_ports))
    end

    selected_ports = Int.(collect(ports))
    isempty(selected_ports) && error("ports must contain at least one port.")
    return selected_ports
end

function _trace_length(trace, label::String)
    try
        return length(trace)
    catch err
        error("Trace $(label) does not have a usable length: $(sprint(showerror, err))")
    end
end

function zero_mode_z_matrix(result; ports=nothing)
    selected_ports = _matrix_ports(result, ports)
    traces = _trace_family(result, :z_parameter_mode)
    frequencies_hz = collect(Float64.(result.frequencies_hz))
    point_count = length(frequencies_hz)
    matrices = fill(ComplexF64(NaN + NaN * im), length(selected_ports), length(selected_ports), point_count)

    for (output_index, output_port) in pairs(selected_ports)
        for (input_index, input_port) in pairs(selected_ports)
            label = mode_label(; outputport=output_port, inputport=input_port)
            trace = get(traces, label, nothing)
            isnothing(trace) &&
                error(
                    "result.traces[:z_parameter_mode] does not contain $(label). Available labels: $(_available_labels(traces))",
                )
            _trace_length(trace, label) == point_count ||
                error("Trace $(label) length does not match result.frequencies_hz length.")
            matrices[output_index, input_index, :] = ComplexF64.(trace)
        end
    end

    return (
        ports=selected_ports,
        frequencies_hz=frequencies_hz,
        values=matrices,
    )
end

function zero_mode_y_matrix(result; ports=nothing)
    z = zero_mode_z_matrix(result; ports=ports)
    port_count = length(z.ports)
    point_count = length(z.frequencies_hz)
    matrices = fill(ComplexF64(NaN + NaN * im), port_count, port_count, point_count)
    status = Vector{
        NamedTuple{(:index, :frequency_hz, :ok, :reason),Tuple{Int,Float64,Bool,String}}
    }(undef, point_count)
    failed_points = NamedTuple{(:index, :frequency_hz, :reason),Tuple{Int,Float64,String}}[]
    singular_points = NamedTuple{(:index, :frequency_hz, :reason),Tuple{Int,Float64,String}}[]

    for point_index in 1:point_count
        z_at_frequency = z.values[:, :, point_index]
        if !all(isfinite, z_at_frequency)
            reason = "Z matrix contains non-finite values."
            status[point_index] = (
                index=point_index,
                frequency_hz=z.frequencies_hz[point_index],
                ok=false,
                reason=reason,
            )
            push!(
                failed_points,
                (
                    index=point_index,
                    frequency_hz=z.frequencies_hz[point_index],
                    reason=reason,
                ),
            )
            continue
        end

        try
            matrices[:, :, point_index] = inv(z_at_frequency)
            status[point_index] = (
                index=point_index,
                frequency_hz=z.frequencies_hz[point_index],
                ok=true,
                reason="",
            )
        catch err
            if err isa SingularException
                reason = "Z matrix is singular."
                status[point_index] = (
                    index=point_index,
                    frequency_hz=z.frequencies_hz[point_index],
                    ok=false,
                    reason=reason,
                )
                push!(
                    singular_points,
                    (
                        index=point_index,
                        frequency_hz=z.frequencies_hz[point_index],
                        reason=reason,
                    ),
                )
                push!(
                    failed_points,
                    (
                        index=point_index,
                        frequency_hz=z.frequencies_hz[point_index],
                        reason=reason,
                    ),
                )
            else
                rethrow()
            end
        end
    end

    return (
        ports=z.ports,
        frequencies_hz=z.frequencies_hz,
        values=matrices,
        status=status,
        failed_points=failed_points,
        singular_points=singular_points,
    )
end

function _frequency_sweep(start_frequency, stop_frequency, point_count)
    point_count > 0 || error("point_count must be positive.")
    point_count == 1 && return [Float64(start_frequency)]
    return range(start_frequency, stop_frequency; length=point_count)
end

function build_grounded_lc_example(;
    id="grounded-lc",
    capacitance=80e-15,
    inductance=10e-9,
    resistance=50.0,
    start_frequency=4.0e9,
    stop_frequency=6.0e9,
    point_count=41,
    pump_frequency=8.0e9,
    pump_current=0.0,
    n_pump_harmonics=16,
    n_modulation_harmonics=8,
    returnS=true,
    returnZ=true,
    returnQE=true,
    returnCM=true,
    optional_hb_kwargs=Dict{Symbol,Any}(
        :iterations => 200,
        :ftol => 1e-8,
        :alphamin => 1e-4,
        :switchofflinesearchtol => 1e-5,
        :nbatches => max(1, Threads.nthreads()),
        :maxintermodorder => 16,
    ),
)
    pump_frequency > 0 || error("pump_frequency must be positive, even for pump-off execution.")

    plan = @circuit id begin
        resonator = component(
            GroundedResonator(
                capacitance=capacitance,
                inductance=inductance,
            );
            display_name=:resonator,
            role=:resonator,
        )

        port(:signal_port) do
            index = 1
            endpoint = pin(resonator, :signal)
            resistance = resistance
            role = :mixed
        end
    end

    shunt_capacitor!(
        plan;
        id="resonator_capacitance",
        at=pin(resonator, :signal),
        capacitance=capacitance,
        role=:resonator_capacitance,
        label="C to ground",
    )
    shunt_inductor!(
        plan;
        id="resonator_inductance",
        at=pin(resonator, :signal),
        inductance=inductance,
        role=:resonator_inductance,
        label="L to ground",
    )

    hb_intent!(
        plan;
        pump_axes=[
            PumpAxis(
                id=:pump,
                frequency_parameter=:pump_frequency,
            ),
        ],
        source_slots=[
            HBSourceSlot(
                id=:pump_in,
                role=:pump,
                port=:signal_port,
                mode=(1,),
                current_parameter=:pump_current,
            ),
        ],
        observables=[
            SParameterRequest(
                id=:s11_signal,
                outputmode=(0,),
                outputport=:signal_port,
                inputmode=(0,),
                inputport=:signal_port,
            ),
        ],
        default_solver_controls=HBSolverControls(
            n_pump_harmonics=n_pump_harmonics,
            n_modulation_harmonics=n_modulation_harmonics,
            dc=false,
            threewavemixing=false,
            fourwavemixing=true,
            returnS=returnS,
            returnZ=returnZ,
            returnQE=returnQE,
            returnCM=returnCM,
            sorting=:name,
            keyedarrays=false,
        ),
    )

    run_spec = HBRunSpec(
        frequency_sweep=_frequency_sweep(start_frequency, stop_frequency, point_count),
        pump_frequencies=Dict(:pump => pump_frequency),
        source_currents=Dict(:pump_in => pump_current),
        optional_hb_kwargs=optional_hb_kwargs,
    )

    compiled = compile_to_josephson(plan)
    hb_problem = build_hb_problem(compiled, run_spec)

    return (
        plan=plan,
        graph=engineering_graph(plan),
        compiled=compiled,
        hb_problem=hb_problem,
        output_request_report=validate_output_request_configuration(compiled, hb_problem),
        result=run_hb_problem(hb_problem),
    )
end

function build_readout_line_hanging_qwr_example(;
    id="readout-line-hanging-qwr",
    line_sections=2,
    resonator_sections=2,
    readout_series_inductance=0.6e-9,
    readout_shunt_capacitance=35e-15,
    resonator_series_inductance=3.5e-9,
    resonator_shunt_capacitance=45e-15,
    coupling_capacitance=2.0e-15,
    port_resistance=50.0,
    start_frequency=3.0e9,
    stop_frequency=8.0e9,
    point_count=31,
    pump_frequency=10.0e9,
    pump_current=0.0,
    n_pump_harmonics=1,
    n_modulation_harmonics=1,
    returnS=true,
    returnZ=true,
    returnQE=true,
    returnCM=true,
    optional_hb_kwargs=Dict{Symbol,Any}(
        :iterations => 120,
        :ftol => 1e-8,
        :nbatches => 1,
    ),
)
    line_sections >= 1 || error("line_sections must be at least 1.")
    resonator_sections >= 1 || error("resonator_sections must be at least 1.")
    pump_frequency > 0 || error("pump_frequency must be positive, even for pump-off execution.")

    plan = @circuit id begin
        readout_line = component(
            ReadoutLine(
                section_count=line_sections,
                series_inductance=readout_series_inductance,
                shunt_capacitance=readout_shunt_capacitance,
            );
            display_name=:readout_line,
            role=:readout_line,
        )

        quarter_wave_resonator = component(
            HangingQuarterWaveResonator(
                section_count=resonator_sections,
                series_inductance=resonator_series_inductance,
                shunt_capacitance=resonator_shunt_capacitance,
            );
            display_name=:quarter_wave_resonator,
            role=:hanging_quarter_wave_resonator,
        )

        port(:input_port) do
            index = 1
            endpoint = pin(readout_line, :input)
            resistance = port_resistance
            role = :signal
        end

        port(:output_port) do
            index = 2
            endpoint = pin(readout_line, :output)
            resistance = port_resistance
            role = :readout
        end
    end

    readout_nodes = AbstractNodeEndpoint[
        pin(readout_line, :input),
        [external_node("readout_n$(idx)") for idx in 1:(line_sections - 1)]...,
        pin(readout_line, :output),
    ]
    coupling_index = max(1, cld(line_sections, 2))
    coupling_node = readout_nodes[coupling_index + 1]

    for section in 1:line_sections
        series_inductor!(
            plan;
            id="readout_l_$(section)",
            from=readout_nodes[section],
            to=readout_nodes[section + 1],
            inductance=readout_series_inductance,
            role=:readout_line_inductance,
            label="readout L$(section)",
        )
        shunt_capacitor!(
            plan;
            id="readout_c_$(section)",
            at=readout_nodes[section + 1],
            capacitance=readout_shunt_capacitance,
            role=:readout_line_capacitance,
            label="readout C$(section)",
        )
    end

    resonator_nodes = AbstractNodeEndpoint[
        pin(quarter_wave_resonator, :coupling),
        [external_node("qwr_n$(idx)") for idx in 1:(resonator_sections - 1)]...,
        ground(),
    ]
    for section in 1:resonator_sections
        series_inductor!(
            plan;
            id="qwr_l_$(section)",
            from=resonator_nodes[section],
            to=resonator_nodes[section + 1],
            inductance=resonator_series_inductance,
            role=:quarter_wave_resonator_inductance,
            label="qwr L$(section)",
        )
        shunt_capacitor!(
            plan;
            id="qwr_c_$(section)",
            at=resonator_nodes[section],
            capacitance=resonator_shunt_capacitance,
            role=:quarter_wave_resonator_capacitance,
            label="qwr C$(section)",
        )
    end

    couple_capacitive!(
        plan;
        id="readout_qwr_coupling",
        from=coupling_node,
        to=pin(quarter_wave_resonator, :coupling),
        capacitance=coupling_capacitance,
        role=:readout_resonator_coupling,
        label="Cc",
    )

    hb_intent!(
        plan;
        pump_axes=[
            PumpAxis(
                id=:pump,
                frequency_parameter=:pump_frequency,
            ),
        ],
        source_slots=[
            HBSourceSlot(
                id=:pump_in,
                role=:pump,
                port=:input_port,
                mode=(1,),
                current_parameter=:pump_current,
            ),
        ],
        observables=[
            SParameterRequest(
                id=:s11_input,
                outputmode=(0,),
                outputport=:input_port,
                inputmode=(0,),
                inputport=:input_port,
            ),
            SParameterRequest(
                id=:s21_through,
                outputmode=(0,),
                outputport=:output_port,
                inputmode=(0,),
                inputport=:input_port,
            ),
        ],
        default_solver_controls=HBSolverControls(
            n_pump_harmonics=n_pump_harmonics,
            n_modulation_harmonics=n_modulation_harmonics,
            dc=false,
            threewavemixing=false,
            fourwavemixing=true,
            returnS=returnS,
            returnZ=returnZ,
            returnQE=returnQE,
            returnCM=returnCM,
            sorting=:name,
            keyedarrays=false,
        ),
    )

    run_spec = HBRunSpec(
        frequency_sweep=_frequency_sweep(start_frequency, stop_frequency, point_count),
        pump_frequencies=Dict(:pump => pump_frequency),
        source_currents=Dict(:pump_in => pump_current),
        optional_hb_kwargs=optional_hb_kwargs,
    )

    compiled = compile_to_josephson(plan)
    hb_problem = build_hb_problem(compiled, run_spec)

    return (
        plan=plan,
        graph=engineering_graph(plan),
        compiled=compiled,
        hb_problem=hb_problem,
        output_request_report=validate_output_request_configuration(compiled, hb_problem),
        result=run_hb_problem(hb_problem),
        readout_nodes=readout_nodes,
        resonator_nodes=resonator_nodes,
        coupling_node=coupling_node,
    )
end

end
