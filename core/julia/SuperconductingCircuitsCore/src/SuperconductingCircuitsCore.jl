module SuperconductingCircuitsCore

using DataFrames
using JosephsonCircuits
using Statistics

include("validation.jl")
include("components/common.jl")
include("components/coupled_window.jl")
include("components/readout_line.jl")
include("components/quarter_wave_resonator.jl")
include("components/half_wave_purcell_filter.jl")
include("draft/circuit_draft.jl")
include("simulation/result_extractors.jl")
include("simulation/hbsolve_runner.jl")
include("simulation/sweep_runner.jl")
include("io/notebook_helpers.jl")

export FrameworkValidationError

export RLGCSpec
export CoupledWindowSpec

export CircuitDraft
export LineSpan
export TransmissionLineInstance
export ReadoutLineComponent
export HalfWavePurcellFilterComponent
export QuarterWaveResonatorComponent
export HangingQuarterWaveResonatorComponent
export CoupledWindowPlacement

export phase_velocity
export section_values
export coupled_window_section_values
export span_length

export add_component!
export add_port_with_termination!
export add_transmission_line!
export add_readout_line_component!
export add_half_wave_purcell_filter_component!
export add_quarter_wave_resonator_component!
export add_hanging_quarter_wave_resonator_component!

export pin_node
export connect!
export apply_series_chain!
export apply_coupled_window!
export add_distributed_segment!
export add_coupled_window!
export finalize_to_josephson_netlist
export add_readout_line!
export add_quarter_wave_resonator!
export add_half_wave_purcell_filter!

export run_hbsolve
export run_frequency_sweep
export run_design_sweep
export SweepAxis
export SweepSpec
export SweepPointResult
export SweepResult

export HBSolveResult
export extract_linearized_traces
export extract_zero_mode_sparameters
export sweep_result_dataframe

end
