module ReusableComponents

using CSV
using DataFrames

include("common.jl")
include("coupled_window.jl")
include("circuit_draft.jl")

export RLGCSpec
export CoupledWindowSpec
export phase_velocity
export section_values
export coupled_window_section_values

export FrameworkValidationError
export CircuitDraft
export AbstractReusableComponent
export ExternalPinComponent
export LCResonatorComponent
export LCQubitComponent
export DifferentialLCQubitComponent
export TunableCouplerComponent
export CPWLineComponent
export PurcellFilterComponent
export QuarterWaveResonatorComponent
export PinRef
export LineTapRef
export LineSpanRef
export GroundRef
export IdealConnectionRelation
export CapacitiveCouplingRelation
export CoupledWindowRelation
export SegmentationRequest
export SegmentationPlan
export FinalizationArtifact
export ProvenanceRecord
export SweepTarget
export ComponentParameterTarget
export RelationParameterTarget
export SweepAssignment
export SweepAxis
export SweepPlan
export SweepPoint
export SweepResultRow

export component_id
export component_prefix
export component_kind
export component_pins
export component_anchors
export owned_line_ids
export allowed_couplings
export ground_convention
export component_parameter_snapshot
export relation_parameter_snapshot

export external_pin!
export lc_resonator!
export lc_qubit!
export differential_lc_qubit!
export tunable_coupler!
export cpw_line!
export purcell_filter!
export quarter_wave_resonator!

export pin
export tap
export tap_m
export section
export section_m
export ground
export connect_pins!
export couple_capacitive!
export coupled_window!
export terminated_port!
export finalize_circuit
export component_parameter
export relation_parameter
export sweep_component
export sweep_relation
export sweep_parameters
export sweep_plan
export sweep_point
export design_sweep_point_count
export apply_sweep_point
export default_finalize_evaluator
export run_design_sweep

end
