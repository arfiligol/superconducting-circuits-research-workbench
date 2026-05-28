module SuperconductingCircuitsCore

using DataFrames
using JosephsonCircuits
using Statistics

include("validation.jl")
include("components/common.jl")
include("components/coupled_window.jl")
include("simulation/result_extractors.jl")
include("simulation/hbsolve_runner.jl")
include("simulation/sweep_runner.jl")
include("io/notebook_helpers.jl")

export FrameworkValidationError

export RLGCSpec
export CoupledWindowSpec

export phase_velocity
export section_values
export coupled_window_section_values

export add_distributed_segment!
export add_coupled_window!

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
