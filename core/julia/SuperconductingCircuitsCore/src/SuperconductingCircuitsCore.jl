module SuperconductingCircuitsCore

using DataFrames
using JosephsonCircuits
using SHA
using Statistics

include("validation.jl")
include("authoring/parameters.jl")
include("authoring/components.jl")
include("authoring/endpoints.jl")
include("authoring/circuit_plan.jl")
include("authoring/relations.jl")
include("authoring/validation.jl")
include("compiler/compiled_circuit.jl")
include("compiler/topology_key.jl")
include("compiler/josephson_compiler.jl")
include("sweeps/executors.jl")
include("sweeps/sweep_spec.jl")
include("sweeps/execution_plan.jl")
include("sweeps/preflight.jl")
include("sweeps/sweep_result.jl")
include("inspection/inspection_helpers.jl")
include("diagnostics/diagnostics.jl")
include("components/common.jl")
include("components/coupled_window.jl")
include("simulation/result_extractors.jl")
include("simulation/hbsolve_runner.jl")
include("io/notebook_helpers.jl")

export FrameworkValidationError

export CircuitPlan
export AbstractCircuitComponent
export AbstractCircuitEndpoint
export AbstractNodeEndpoint
export AbstractLineSpanEndpoint
export AbstractLoopEndpoint
export PinEndpoint
export LineTapEndpoint
export LineSpanEndpoint
export GroundEndpoint
export ExternalNodeEndpoint
export LoopEndpoint
export LineRef
export pin
export line_tap
export line_span
export line_ref
export ground
export external_node
export loop_endpoint
export component_id
export component_pins
export component_lines
export default_line
export component_parameters
export register_component!
export register_parameter!

export AbstractParameterRole
export StructuralParameter
export NumericParameter
export DriveParameter
export AnalysisParameter
export ParameterMetadata
export ParameterBinding
export parameter_role
export parameter_owner
export is_structural
export is_numeric
export is_drive
export is_analysis
export strongest_parameter_role

export AbstractCircuitRelation
export NodeConnection
export CapacitiveCoupling
export ShuntCapacitor
export InductiveCoupling
export CoupledWindowRelation
export connect!
export couple_capacitive!
export shunt_capacitor!
export couple_inductive!
export couple_window!

export validate_authoring
export validate_compile_ready
export ValidationIssue
export ValidationReport
export has_errors
export errors
export warnings

export compile_to_josephson
export JosephsonCompiledCircuit
export TopologyKey
export topology_key

export AbstractSweepAxis
export SweepSpec
export StructuralAxis
export NumericAxis
export DriveAxis
export AnalysisAxis
export CompileEveryPoint
export CompileOnce
export CompileByTopologyKey
export StrictSweepClassification
export PermissiveSweepClassification
export DebugSweepClassification
export SerialExecutor
export ThreadedExecutor
export RunnerExecutor
export NoAcceleration
export SweepExecutionPlan
export SweepResult
export preflight_sweep
export run_parameter_sweep

export inspect_plan
export inspect_parameters
export inspect_endpoints
export inspect_topology_key
export inspect_sweep_preflight
export summarize_sweep_result

export DiagnosticIssue
export DiagnosticReport
export diagnostic_errors
export diagnostic_warnings
export has_diagnostic_errors
export diagnose_plan
export diagnose_compile
export diagnose_sweep
export explain_topology_key
export diff_topology_keys
export debug_bundle

export RLGCSpec
export CoupledWindowSpec

export phase_velocity
export section_values
export coupled_window_section_values

export run_hbsolve
export run_frequency_sweep

export HBSolveResult
export extract_linearized_traces
export extract_zero_mode_sparameters
export sweep_result_dataframe

end
