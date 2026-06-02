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
include("simulation/hb_intent.jl")
include("simulation/hb_problem.jl")
include("compiler/topology_key.jl")
include("compiler/josephson_compiler.jl")
include("authoring/macro_dsl.jl")
include("sweeps/executors.jl")
include("sweeps/sweep_spec.jl")
include("sweeps/execution_plan.jl")
include("sweeps/preflight.jl")
include("sweeps/sweep_result.jl")
include("inspection/inspection_helpers.jl")
include("diagnostics/diagnostics.jl")
include("components/common.jl")
include("components/coupled_window.jl")
include("components/transmission_lines.jl")
include("components/reusable_components.jl")
include("examples/pluto_examples.jl")
include("simulation/result_extractors.jl")
include("simulation/hbsolve_runner.jl")
include("io/notebook_helpers.jl")

export FrameworkValidationError

export CircuitPlan
export AbstractCircuitComponent
export CircuitComponentInstance
export CircuitComponentBuilder
export component_builder_allowed_keywords
export AbstractCircuitEndpoint
export AbstractNodeEndpoint
export AbstractLineSpanEndpoint
export AbstractLoopEndpoint
export PinEndpoint
export ProbeEndpoint
export AnchorRef
export LineTapEndpoint
export LineSpanEndpoint
export GroundEndpoint
export ExternalNodeEndpoint
export LoopEndpoint
export LineRef
export pin
export tap
export probe
export anchor
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
export external_port!
export EngineeringComponent
export EngineeringRelation
export EngineeringPort
export EngineeringGroup
export ExternalPort
export EngineeringGraph
export SchematicLayoutGroup
export SchematicTrack
export SchematicSegment
export SchematicCoupledSpan
export SchematicTerminal
export SchematicNodeLabel
export SchematicSegmentLabel
export SchematicAnchor
export SchematicLayoutIntent
export SchematicExportSpec
export engineering_graph
export schematic_layout_intent
export record_engineering_component!
export record_engineering_relation!
export record_engineering_port!
export record_engineering_group!
export record_schematic_group!
export record_schematic_track!
export record_schematic_segment!
export record_schematic_coupled_span!
export record_schematic_terminal!
export record_schematic_node_label!
export record_schematic_segment_label!
export record_schematic_anchor!
export schematic!
export to_dot
export to_schematic_export_spec
export @circuit
export @circuit_component
export @hbintent

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
export ShuntInductor
export SeriesInductor
export SeriesResistor
export JosephsonJunction
export InductiveCoupling
export MutualInductiveCoupling
export CoupledWindowRelation
export connect!
export couple_capacitive!
export shunt_capacitor!
export shunt_inductor!
export series_inductor!
export series_resistor!
export josephson_junction!
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

export PumpAxis
export HBSourceSlot
export SParameterRequest
export HBSolverControls
export HBIntent
export HBRunSpec
export HBProblemSpec
export OutputRequestConfigurationReport
export hb_intent!
export validate_hb_intent
export build_hb_problem
export validate_output_request_configuration
export run_hb_problem

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
export AbstractTransmissionLineModel
export CoupledWindowSpec
export TransmissionLineLadder
export TransmissionLineSectionOverride
export MTLCoupledRLGCSpec
export CoupledTransmissionWindow
export ParallelLCResonator
export ReflectiveJPA
export HalfWaveResonator
export QuarterWaveResonator
export ReadoutLineWithPurcellFilter
export ReadoutPurcellQWRMTL

export phase_velocity
export section_values
export coupled_window_section_values
export mutual_capacitance_per_m_f
export mutual_inductance_per_m_h
export coupled_line_section_override
export build_lc_ladder_line!
export transmission_line!
export couple_transmission_window!
export node_at_distance
export section_index_at_distance
export section_range_from_window
export add_parallel_lc_resonator!
export add_reflective_jpa!
export add_half_wave_resonator!
export add_quarter_wave_resonator!
export half_wave_resonator!
export quarter_wave_resonator!
export add_readout_line_with_purcell_filter!
export add_readout_purcell_qwr_mtl!

export build_parallel_lc_resonator_example
export build_reflective_jpa_capacitive_coupled_lc_example
export build_floating_lc_xy_line_example
export build_transmission_line_circuit_model_example
export build_readout_line_purcell_filter_example
export build_readout_line_hanging_qwr_mtl_example
export build_readout_purcell_hanging_qwr_mtl_example

export run_hbsolve
export run_frequency_sweep

export HBSolveResult
export extract_linearized_traces
export extract_zero_mode_sparameters
export sweep_result_dataframe

end
