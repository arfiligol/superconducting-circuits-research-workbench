module HBExampleHelpers

using SuperconductingCircuitsCore

import SuperconductingCircuitsCore:
    component_id,
    component_pins,
    component_lines,
    default_line,
    component_parameters

export GroundedResonator,
    db20,
    phase_deg,
    zero_mode_s,
    zero_mode_z,
    mode_trace,
    build_grounded_lc_example

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

db20(values) = 20 .* log10.(abs.(values))
phase_deg(values) = rad2deg.(angle.(values))

function _mode_token(mode)
    return join(string.(Int.(collect(mode))), ",")
end

function _mode_trace_label(; outputmode, outputport, inputmode, inputport)
    return "om=$(_mode_token(outputmode))|op=$(Int(outputport))|im=$(_mode_token(inputmode))|ip=$(Int(inputport))"
end

function zero_mode_s(result, output_port::Integer, input_port::Integer)
    return result.traces[:zero_mode_s]["S$(Int(output_port))$(Int(input_port))"]
end

function mode_trace(
    result,
    family::Symbol;
    outputmode=(0,),
    outputport::Integer,
    inputmode=(0,),
    inputport::Integer,
)
    label = _mode_trace_label(
        outputmode=outputmode,
        outputport=outputport,
        inputmode=inputmode,
        inputport=inputport,
    )
    return result.traces[family][label]
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
        frequency_sweep=range(start_frequency, stop_frequency; length=point_count),
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

end
