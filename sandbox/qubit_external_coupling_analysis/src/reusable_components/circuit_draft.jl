###############################################################################
# Reusable Component Framework v1
###############################################################################
#
# Components declare local structure. Relations declare cross-component intent.
# Finalization is the only stage that emits JosephsonCircuits primitive rows.
###############################################################################

###############################################################################
# Validation
###############################################################################

struct FrameworkValidationError <: Exception
    message::String
end

Base.showerror(io::IO, err::FrameworkValidationError) = print(io, err.message)

function _validation_error(message::AbstractString)
    throw(FrameworkValidationError(String(message)))
end

function _require(condition::Bool, message::AbstractString)
    condition || _validation_error(message)
end

###############################################################################
# Public semantic model
###############################################################################

abstract type AbstractReusableComponent end
abstract type AbstractEndpointRef end
abstract type AbstractCompositionRelation end
abstract type AbstractSweepTarget end

struct LineDeclaration
    id::String
    component_id::String
    name::Symbol
    prefix::String
    start_node::String
    end_node::String
    spec::RLGCSpec
    ground_node::String
    add_shunt_at_last_node::Bool
end

struct ExternalPinComponent <: AbstractReusableComponent
    id::String
    prefix::String
    node::String
end

struct LCResonatorComponent <: AbstractReusableComponent
    id::String
    prefix::String
    L_h::Float64
    C_f::Float64
end

struct LCQubitComponent <: AbstractReusableComponent
    id::String
    prefix::String
    L_h::Float64
    C_f::Float64
end

struct DifferentialLCQubitComponent <: AbstractReusableComponent
    id::String
    prefix::String
    Cg1_f::Float64
    Cg2_f::Float64
    Cq_f::Float64
    Lq_h::Float64
end

struct TunableCouplerComponent <: AbstractReusableComponent
    id::String
    prefix::String
    L_h::Float64
    C_f::Float64
end

struct CPWLineComponent <: AbstractReusableComponent
    id::String
    prefix::String
    line::RLGCSpec
    ground_node::String
    add_shunt_at_last_node::Bool
end

struct PurcellFilterComponent <: AbstractReusableComponent
    id::String
    prefix::String
    line::RLGCSpec
    left_coupling_cap_f::Float64
    right_coupling_cap_f::Float64
    ground_node::String
    line_left_node::String
    line_right_node::String
end

struct QuarterWaveResonatorComponent <: AbstractReusableComponent
    id::String
    prefix::String
    line::RLGCSpec
    boundary::Symbol
    ground_node::String
end

struct PinRef <: AbstractEndpointRef
    component_id::String
    pin::Symbol
end

struct LineTapRef <: AbstractEndpointRef
    component_id::String
    line::Symbol
    position::Float64
    mode::Symbol
end

struct LineSpanRef <: AbstractEndpointRef
    component_id::String
    line::Symbol
    start::Float64
    stop::Float64
    mode::Symbol
end

struct GroundRef <: AbstractEndpointRef
end

struct IdealConnectionRelation <: AbstractCompositionRelation
    id::String
    endpoint_a::AbstractEndpointRef
    endpoint_b::AbstractEndpointRef
    modification_mode::Symbol
end

struct CapacitiveCouplingRelation <: AbstractCompositionRelation
    id::String
    endpoint_a::AbstractEndpointRef
    endpoint_b::AbstractEndpointRef
    capacitance_f::Float64
    modification_mode::Symbol
end

struct CoupledWindowRelation <: AbstractCompositionRelation
    id::String
    endpoint_a::LineSpanRef
    endpoint_b::LineSpanRef
    spec::CoupledWindowSpec
    modification_mode::Symbol
end

struct PortTerminationRelation <: AbstractCompositionRelation
    id::String
    endpoint::AbstractEndpointRef
    port_number::Int
    resistance_ohm::Float64
    modification_mode::Symbol
end

struct SegmentationRequest
    line_id::String
    position_m::Float64
    reason::Symbol
    relation_id::String
end

struct SegmentPlan
    kind::Symbol
    line_id::String
    component_id::String
    prefix::String
    start_m::Float64
    stop_m::Float64
    left_node::String
    right_node::String
    n_sections::Int
    add_shunt_at_last_node::Bool
    relation_id::String
end

struct LineSegmentationPlan
    line_id::String
    breakpoints_m::Vector{Float64}
    boundary_nodes::Vector{String}
    requests::Vector{SegmentationRequest}
    segments::Vector{SegmentPlan}
end

struct SegmentationPlan
    lines::Dict{String,LineSegmentationPlan}
end

struct ProvenanceRecord
    row_index::Int
    generated_name::String
    primitive_kind::Symbol
    component_ids::Vector{String}
    relation_id::Union{Nothing,String}
    source::Symbol
    role::Symbol
    semantic_path::Vector{String}
    segment_id::Union{Nothing,String}
    parameter_owner::Union{Nothing,Symbol}
    parameter_snapshot::Dict{Symbol,Any}
end

struct FinalizationArtifact
    netlist::Vector{Tuple{String,String,String,Any}}
    provenance_table::Vector{ProvenanceRecord}
    node_map::Dict{String,String}
    segmentation_plan::SegmentationPlan
end

mutable struct CircuitDraft
    name::String
    ground_node::String
    components::Dict{String,AbstractReusableComponent}
    component_order::Vector{String}
    relations::Vector{AbstractCompositionRelation}
    relation_ids::Set{String}
    finalization_config::Dict{Symbol,Any}
end

function CircuitDraft(name::AbstractString; ground_node::AbstractString="0")
    _require(!isempty(name), "CircuitDraft name must not be empty.")
    return CircuitDraft(
        String(name),
        String(ground_node),
        Dict{String,AbstractReusableComponent}(),
        String[],
        AbstractCompositionRelation[],
        Set{String}(),
        Dict{Symbol,Any}(),
    )
end

###############################################################################
# Component interface
###############################################################################

component_id(component::AbstractReusableComponent) = component.id
component_prefix(component::AbstractReusableComponent) = component.prefix

component_kind(::ExternalPinComponent) = :external_pin
component_kind(::LCResonatorComponent) = :lc_resonator
component_kind(::LCQubitComponent) = :lc_qubit
component_kind(::DifferentialLCQubitComponent) = :differential_lc_qubit
component_kind(::TunableCouplerComponent) = :tunable_coupler
component_kind(::CPWLineComponent) = :cpw_line
component_kind(::PurcellFilterComponent) = :purcell_filter
component_kind(::QuarterWaveResonatorComponent) = :quarter_wave_resonator

function _pin_token(component_id::AbstractString, pin_name::Symbol)
    return "__pin__$(component_id)__$(String(pin_name))"
end

function _internal_token(component_id::AbstractString, tag::AbstractString)
    return "__internal__$(component_id)__$(tag)"
end

function _is_private_token(node::AbstractString)
    return startswith(node, "__pin__") || startswith(node, "__internal__")
end

function _public_pin(component_id::AbstractString, pin_name::Symbol)
    return _pin_token(component_id, pin_name)
end

function _line_id(component_id::AbstractString, line_name::Symbol)
    return "$(component_id)__$(String(line_name))"
end

function _line_declaration(;
    component_id::AbstractString,
    line_name::Symbol=:main,
    prefix::AbstractString=String(component_id),
    start_node,
    end_node,
    spec::RLGCSpec,
    ground_node::AbstractString="0",
    add_shunt_at_last_node::Bool=true,
)
    return LineDeclaration(
        _line_id(component_id, line_name),
        String(component_id),
        line_name,
        String(prefix),
        string(start_node),
        string(end_node),
        spec,
        String(ground_node),
        add_shunt_at_last_node,
    )
end

_pins(component::ExternalPinComponent) = Dict(:node => component.node)
_pins(component::LCResonatorComponent) = Dict(:plus => _public_pin(component.id, :plus), :minus => _public_pin(component.id, :minus))
_pins(component::LCQubitComponent) = Dict(:pad => _public_pin(component.id, :pad), :minus => _public_pin(component.id, :minus))
_pins(component::DifferentialLCQubitComponent) = Dict(:pad1 => _public_pin(component.id, :pad1), :pad2 => _public_pin(component.id, :pad2))
_pins(component::TunableCouplerComponent) = Dict(:left => _public_pin(component.id, :left), :right => _public_pin(component.id, :right))
_pins(component::CPWLineComponent) = Dict(:left => _public_pin(component.id, :left), :right => _public_pin(component.id, :right))
_pins(component::PurcellFilterComponent) = Dict(:left => _public_pin(component.id, :left), :right => _public_pin(component.id, :right))
_pins(component::QuarterWaveResonatorComponent) = Dict(:open => _public_pin(component.id, :open), :feed => _public_pin(component.id, :open))

_anchors(::AbstractReusableComponent) = Dict{Symbol,Any}()
_anchors(::CPWLineComponent) = Dict(:tap => :main, :section => :main)
_anchors(::PurcellFilterComponent) = Dict(:tap => :main, :section => :main)
_anchors(::QuarterWaveResonatorComponent) = Dict(:tap => :main, :section => :main)

_owned_lines(::AbstractReusableComponent) = Dict{Symbol,LineDeclaration}()

function _owned_lines(component::CPWLineComponent)
    pins = _pins(component)
    return Dict(
        :main => _line_declaration(
            component_id=component.id,
            line_name=:main,
            prefix=component.prefix,
            start_node=pins[:left],
            end_node=pins[:right],
            spec=component.line,
            ground_node=component.ground_node,
            add_shunt_at_last_node=component.add_shunt_at_last_node,
        ),
    )
end

function _owned_lines(component::PurcellFilterComponent)
    return Dict(
        :main => _line_declaration(
            component_id=component.id,
            line_name=:main,
            prefix=component.prefix,
            start_node=component.line_left_node,
            end_node=component.line_right_node,
            spec=component.line,
            ground_node=component.ground_node,
            add_shunt_at_last_node=true,
        ),
    )
end

function _owned_lines(component::QuarterWaveResonatorComponent)
    pins = _pins(component)
    end_node = component.boundary == :short ? component.ground_node : _internal_token(component.id, "line_end")
    return Dict(
        :main => _line_declaration(
            component_id=component.id,
            line_name=:main,
            prefix=component.prefix,
            start_node=pins[:open],
            end_node=end_node,
            spec=component.line,
            ground_node=component.ground_node,
            add_shunt_at_last_node=component.boundary == :open,
        ),
    )
end

component_pins(component::AbstractReusableComponent) = sort(collect(keys(_pins(component))); by=String)
component_anchors(component::AbstractReusableComponent) = sort(collect(keys(_anchors(component))); by=String)
owned_line_ids(component::AbstractReusableComponent) = [line.id for line in values(_owned_lines(component))]

ground_convention(::ExternalPinComponent) = :external
ground_convention(::LCResonatorComponent) = :floating
ground_convention(::LCQubitComponent) = :floating
ground_convention(::DifferentialLCQubitComponent) = :differential
ground_convention(::TunableCouplerComponent) = :floating
ground_convention(::CPWLineComponent) = :single_ended
ground_convention(::PurcellFilterComponent) = :single_ended
ground_convention(component::QuarterWaveResonatorComponent) = component.boundary == :short ? :single_ended : :floating

allowed_couplings(::ExternalPinComponent) = Set([:ideal_connection, :capacitive_pin, :port])
allowed_couplings(::LCResonatorComponent) = Set([:ideal_connection, :capacitive_pin, :inductive_pin])
allowed_couplings(::LCQubitComponent) = Set([:ideal_connection, :capacitive_pin])
allowed_couplings(::DifferentialLCQubitComponent) = Set([:capacitive_pin, :port])
allowed_couplings(::TunableCouplerComponent) = Set([:ideal_connection, :capacitive_pin])
allowed_couplings(::CPWLineComponent) = Set([:ideal_connection, :capacitive_tap, :coupled_window, :port])
allowed_couplings(::PurcellFilterComponent) = Set([:ideal_connection, :capacitive_tap, :coupled_window, :port])
allowed_couplings(::QuarterWaveResonatorComponent) = Set([:capacitive_pin, :capacitive_tap, :coupled_window])

lowering_rule(::ExternalPinComponent) = :none
lowering_rule(::LCResonatorComponent) = :parallel_lc
lowering_rule(::LCQubitComponent) = :qubit_lc
lowering_rule(::DifferentialLCQubitComponent) = :differential_lc
lowering_rule(::TunableCouplerComponent) = :parallel_lc
lowering_rule(::CPWLineComponent) = :distributed_line
lowering_rule(::PurcellFilterComponent) = :purcell_filter
lowering_rule(::QuarterWaveResonatorComponent) = :quarter_wave_resonator

component_parameter_snapshot(component::ExternalPinComponent) = Dict{Symbol,Any}()
component_parameter_snapshot(component::LCResonatorComponent) = Dict{Symbol,Any}(:L_h => component.L_h, :C_f => component.C_f)
component_parameter_snapshot(component::LCQubitComponent) = Dict{Symbol,Any}(:L_h => component.L_h, :C_f => component.C_f)
component_parameter_snapshot(component::DifferentialLCQubitComponent) = Dict{Symbol,Any}(:Cg1_f => component.Cg1_f, :Cg2_f => component.Cg2_f, :Cq_f => component.Cq_f, :Lq_h => component.Lq_h)
component_parameter_snapshot(component::TunableCouplerComponent) = Dict{Symbol,Any}(:L_h => component.L_h, :C_f => component.C_f)
function _rlgc_snapshot(spec::RLGCSpec)
    return Dict{Symbol,Any}(
        :length_m => spec.length_m,
        :n_sections => spec.n_sections,
        :l_per_m_h => spec.l_per_m_h,
        :c_per_m_f => spec.c_per_m_f,
        :r_per_m_ohm => spec.r_per_m_ohm,
        :g_per_m_s => spec.g_per_m_s,
    )
end

component_parameter_snapshot(component::CPWLineComponent) = _rlgc_snapshot(component.line)
component_parameter_snapshot(component::PurcellFilterComponent) = merge(_rlgc_snapshot(component.line), Dict{Symbol,Any}(:left_coupling_cap_f => component.left_coupling_cap_f, :right_coupling_cap_f => component.right_coupling_cap_f))
component_parameter_snapshot(component::QuarterWaveResonatorComponent) = merge(_rlgc_snapshot(component.line), Dict{Symbol,Any}(:boundary => component.boundary))

function validate_component(component::AbstractReusableComponent)
    _require(!isempty(component_id(component)), "Component id must not be empty.")
    _require(!isempty(component_prefix(component)), "Component '$(component_id(component))' prefix must not be empty.")
    for (pin_name, node) in _pins(component)
        _require(!isempty(string(pin_name)), "Component '$(component_id(component))' has an empty pin name.")
        _require(!isempty(node), "Component '$(component_id(component))' pin ':$(pin_name)' has an empty node.")
    end
end

function validate_component(component::LCResonatorComponent)
    invoke(validate_component, Tuple{AbstractReusableComponent}, component)
    _require(component.L_h > 0, "Component '$(component.id)' L_h must be positive.")
    _require(component.C_f > 0, "Component '$(component.id)' C_f must be positive.")
end

function validate_component(component::LCQubitComponent)
    invoke(validate_component, Tuple{AbstractReusableComponent}, component)
    _require(component.L_h > 0, "Component '$(component.id)' L_h must be positive.")
    _require(component.C_f > 0, "Component '$(component.id)' C_f must be positive.")
end

function validate_component(component::DifferentialLCQubitComponent)
    invoke(validate_component, Tuple{AbstractReusableComponent}, component)
    _require(component.Cg1_f >= 0, "Component '$(component.id)' Cg1_f must be non-negative.")
    _require(component.Cg2_f >= 0, "Component '$(component.id)' Cg2_f must be non-negative.")
    _require(component.Cq_f > 0, "Component '$(component.id)' Cq_f must be positive.")
    _require(component.Lq_h > 0, "Component '$(component.id)' Lq_h must be positive.")
end

function validate_component(component::TunableCouplerComponent)
    invoke(validate_component, Tuple{AbstractReusableComponent}, component)
    _require(component.L_h > 0, "Component '$(component.id)' L_h must be positive.")
    _require(component.C_f > 0, "Component '$(component.id)' C_f must be positive.")
end

function validate_component(component::CPWLineComponent)
    invoke(validate_component, Tuple{AbstractReusableComponent}, component)
    _validate_rlgc_spec(component.line)
end

function validate_component(component::PurcellFilterComponent)
    invoke(validate_component, Tuple{AbstractReusableComponent}, component)
    _validate_rlgc_spec(component.line)
    _require(component.left_coupling_cap_f > 0, "Component '$(component.id)' left_coupling_cap_f must be positive.")
    _require(component.right_coupling_cap_f > 0, "Component '$(component.id)' right_coupling_cap_f must be positive.")
end

function validate_component(component::QuarterWaveResonatorComponent)
    invoke(validate_component, Tuple{AbstractReusableComponent}, component)
    _validate_rlgc_spec(component.line)
    _require(component.boundary in (:open, :short), "Component '$(component.id)' boundary must be :open or :short.")
end

###############################################################################
# Component constructors and endpoint helpers
###############################################################################

ground() = GroundRef()

function pin(component::AbstractReusableComponent, name::Symbol)
    pins = _pins(component)
    haskey(pins, name) ||
        _validation_error("Component '$(component_id(component))' does not expose pin ':$(name)'.")
    return PinRef(component_id(component), name)
end

function tap(component::AbstractReusableComponent, position::Real; line::Symbol=:main)
    position_value = Float64(position)
    _require(0.0 <= position_value <= 1.0, "tap position must be a fraction between 0 and 1.")
    haskey(_owned_lines(component), line) ||
        _validation_error("Component '$(component_id(component))' does not expose line ':$(line)'.")
    return LineTapRef(component_id(component), line, position_value, :fraction)
end

function tap_m(component::AbstractReusableComponent, position_m::Real; line::Symbol=:main)
    position_value = Float64(position_m)
    line_decl = get(_owned_lines(component), line, nothing)
    line_decl === nothing &&
        _validation_error("Component '$(component_id(component))' does not expose line ':$(line)'.")
    _require(0.0 <= position_value <= line_decl.spec.length_m, "tap_m position must fall inside line ':$(line)'.")
    return LineTapRef(component_id(component), line, position_value, :meter)
end

function section(component::AbstractReusableComponent, start::Real, stop::Real; line::Symbol=:main)
    start_value = Float64(start)
    stop_value = Float64(stop)
    _require(0.0 <= start_value < stop_value <= 1.0, "section bounds must satisfy 0 <= start < stop <= 1.")
    haskey(_owned_lines(component), line) ||
        _validation_error("Component '$(component_id(component))' does not expose line ':$(line)'.")
    return LineSpanRef(component_id(component), line, start_value, stop_value, :fraction)
end

function section_m(component::AbstractReusableComponent, start_m::Real, stop_m::Real; line::Symbol=:main)
    start_value = Float64(start_m)
    stop_value = Float64(stop_m)
    line_decl = get(_owned_lines(component), line, nothing)
    line_decl === nothing &&
        _validation_error("Component '$(component_id(component))' does not expose line ':$(line)'.")
    _require(0.0 <= start_value < stop_value <= line_decl.spec.length_m, "section_m bounds must fall inside line ':$(line)'.")
    return LineSpanRef(component_id(component), line, start_value, stop_value, :meter)
end

function _register_component!(draft::CircuitDraft, component::AbstractReusableComponent)
    validate_component(component)
    haskey(draft.components, component_id(component)) &&
        _validation_error("Component id '$(component_id(component))' is already registered.")
    any(existing -> component_prefix(existing) == component_prefix(component), values(draft.components)) &&
        _validation_error("Component prefix '$(component_prefix(component))' is already registered.")
    draft.components[component_id(component)] = component
    push!(draft.component_order, component_id(component))
    return component
end

function _component(draft::CircuitDraft, id::AbstractString)
    component = get(draft.components, String(id), nothing)
    component === nothing && _validation_error("Unknown component id '$(id)'.")
    return component
end

function _line_for_ref(draft::CircuitDraft, ref::Union{LineTapRef,LineSpanRef})
    component = _component(draft, ref.component_id)
    line = get(_owned_lines(component), ref.line, nothing)
    line === nothing &&
        _validation_error("Component '$(component_id(component))' does not expose line ':$(ref.line)'.")
    return line
end

function _position_m(ref::LineTapRef, line::LineDeclaration)
    ref.mode == :fraction && return ref.position * line.spec.length_m
    ref.mode == :meter && return ref.position
    _validation_error("Unsupported tap coordinate mode ':$(ref.mode)'.")
end

function _span_m(ref::LineSpanRef, line::LineDeclaration)
    if ref.mode == :fraction
        return (start_m=ref.start * line.spec.length_m, stop_m=ref.stop * line.spec.length_m)
    elseif ref.mode == :meter
        return (start_m=ref.start, stop_m=ref.stop)
    end
    _validation_error("Unsupported section coordinate mode ':$(ref.mode)'.")
end

function external_pin!(draft::CircuitDraft, id::AbstractString; prefix::AbstractString=String(id))
    return _register_component!(draft, ExternalPinComponent(String(id), String(prefix), String(id)))
end

function lc_resonator!(draft::CircuitDraft, id::AbstractString; L::Real, C::Real, prefix::AbstractString=String(id))
    return _register_component!(draft, LCResonatorComponent(String(id), String(prefix), Float64(L), Float64(C)))
end

function lc_qubit!(draft::CircuitDraft, id::AbstractString; L::Real, C::Real, prefix::AbstractString=String(id))
    return _register_component!(draft, LCQubitComponent(String(id), String(prefix), Float64(L), Float64(C)))
end

function differential_lc_qubit!(
    draft::CircuitDraft,
    id::AbstractString;
    Cg1::Real,
    Cg2::Real,
    Cq::Real,
    Lq::Real,
    prefix::AbstractString=String(id),
)
    return _register_component!(
        draft,
        DifferentialLCQubitComponent(String(id), String(prefix), Float64(Cg1), Float64(Cg2), Float64(Cq), Float64(Lq)),
    )
end

function tunable_coupler!(draft::CircuitDraft, id::AbstractString; L::Real, C::Real, prefix::AbstractString=String(id))
    return _register_component!(draft, TunableCouplerComponent(String(id), String(prefix), Float64(L), Float64(C)))
end

function cpw_line!(
    draft::CircuitDraft,
    id::AbstractString;
    line::RLGCSpec,
    prefix::AbstractString=String(id),
    ground_node::AbstractString=draft.ground_node,
    add_shunt_at_last_node::Bool=false,
)
    return _register_component!(
        draft,
        CPWLineComponent(String(id), String(prefix), line, String(ground_node), add_shunt_at_last_node),
    )
end

function purcell_filter!(
    draft::CircuitDraft,
    id::AbstractString;
    line::RLGCSpec,
    left_coupling_cap_f::Real,
    right_coupling_cap_f::Real,
    prefix::AbstractString=String(id),
    ground_node::AbstractString=draft.ground_node,
)
    component_id_value = String(id)
    return _register_component!(
        draft,
        PurcellFilterComponent(
            component_id_value,
            String(prefix),
            line,
            Float64(left_coupling_cap_f),
            Float64(right_coupling_cap_f),
            String(ground_node),
            _internal_token(component_id_value, "line_left"),
            _internal_token(component_id_value, "line_right"),
        ),
    )
end

function quarter_wave_resonator!(
    draft::CircuitDraft,
    id::AbstractString;
    line::RLGCSpec,
    boundary::Symbol=:short,
    prefix::AbstractString=String(id),
    ground_node::AbstractString=draft.ground_node,
)
    return _register_component!(
        draft,
        QuarterWaveResonatorComponent(String(id), String(prefix), line, boundary, String(ground_node)),
    )
end

###############################################################################
# Relation helpers
###############################################################################

function _next_relation_id(draft::CircuitDraft, prefix::AbstractString)
    base = String(prefix)
    if !in(base, draft.relation_ids)
        return base
    end
    idx = 2
    while in("$(base)_$(idx)", draft.relation_ids)
        idx += 1
    end
    return "$(base)_$(idx)"
end

function _relation_id(relation::AbstractCompositionRelation)
    return relation.id
end

function _relation_mode(relation::AbstractCompositionRelation)
    return relation.modification_mode
end

function _register_relation!(draft::CircuitDraft, relation::AbstractCompositionRelation)
    id = _relation_id(relation)
    _require(!isempty(id), "Relation id must not be empty.")
    in(id, draft.relation_ids) && _validation_error("Relation id '$(id)' is already registered.")
    push!(draft.relations, relation)
    push!(draft.relation_ids, id)
    return relation
end

function _is_discrete_endpoint(endpoint::AbstractEndpointRef)
    return endpoint isa PinRef || endpoint isa GroundRef
end

function connect_pins!(
    draft::CircuitDraft,
    endpoint_a::AbstractEndpointRef,
    endpoint_b::AbstractEndpointRef;
    id=nothing,
)
    _is_discrete_endpoint(endpoint_a) ||
        _validation_error("connect_pins! accepts only PinRef or GroundRef endpoints.")
    _is_discrete_endpoint(endpoint_b) ||
        _validation_error("connect_pins! accepts only PinRef or GroundRef endpoints.")
    relation_id = isnothing(id) ? _next_relation_id(draft, "connect") : String(id)
    return _register_relation!(draft, IdealConnectionRelation(relation_id, endpoint_a, endpoint_b, :additive))
end

function couple_capacitive!(
    draft::CircuitDraft,
    endpoint_a::AbstractEndpointRef,
    endpoint_b::AbstractEndpointRef;
    C::Real,
    id=nothing,
)
    _require(C > 0, "Coupling capacitance C must be positive.")
    endpoint_a isa LineSpanRef && _validation_error("couple_capacitive! does not accept LineSpanRef.")
    endpoint_b isa LineSpanRef && _validation_error("couple_capacitive! does not accept LineSpanRef.")
    relation_id = isnothing(id) ? _next_relation_id(draft, "cap_coupling") : String(id)
    return _register_relation!(
        draft,
        CapacitiveCouplingRelation(relation_id, endpoint_a, endpoint_b, Float64(C), :additive),
    )
end

function coupled_window!(
    draft::CircuitDraft,
    endpoint_a::LineSpanRef,
    endpoint_b::LineSpanRef;
    spec::CoupledWindowSpec,
    id=nothing,
)
    _validate_coupled_window_spec(spec)
    relation_id = isnothing(id) ? _next_relation_id(draft, "coupled_window") : String(id)
    return _register_relation!(
        draft,
        CoupledWindowRelation(relation_id, endpoint_a, endpoint_b, spec, :replacement),
    )
end

function terminated_port!(
    draft::CircuitDraft,
    endpoint::AbstractEndpointRef;
    port_number::Int,
    resistance_ohm::Real=50.0,
    id=nothing,
)
    _require(port_number > 0, "port_number must be positive.")
    _require(resistance_ohm > 0, "resistance_ohm must be positive.")
    endpoint isa LineSpanRef && _validation_error("terminated_port! does not accept LineSpanRef.")
    relation_id = isnothing(id) ? _next_relation_id(draft, "port$(port_number)") : String(id)
    return _register_relation!(
        draft,
        PortTerminationRelation(relation_id, endpoint, port_number, Float64(resistance_ohm), :annotation_only),
    )
end

###############################################################################
# Finalization
###############################################################################

function finalize_circuit(draft::CircuitDraft; renumber_nodes::Bool=false)
    _validate_component_graph(draft)
    _validate_relations(draft)

    resolve_node, semantic_node_map = _build_node_resolver(draft)
    lines = _collect_lines(draft)
    replacement_spans = _collect_replacement_spans(draft, lines)
    segmentation_requests = _collect_segmentation_requests(draft, lines, replacement_spans)
    _validate_segmentation_conflicts(replacement_spans, segmentation_requests)
    segmentation_plan = _build_segmentation_plan(draft, lines, replacement_spans, segmentation_requests, resolve_node)

    netlist = Tuple{String,String,String,Any}[]
    provenance = ProvenanceRecord[]

    _emit_component_rows!(netlist, provenance, draft, resolve_node)
    _emit_line_rows!(netlist, provenance, draft, lines, segmentation_plan)
    _emit_additive_relation_rows!(netlist, provenance, draft, segmentation_plan, resolve_node)
    _emit_replacement_relation_rows!(netlist, provenance, draft, segmentation_plan)

    final_node_map = copy(semantic_node_map)
    for line_plan in values(segmentation_plan.lines)
        for node in line_plan.boundary_nodes
            final_node_map[node] = get(final_node_map, node, node)
        end
    end

    if renumber_nodes
        netlist, numeric_node_map = _renumber_netlist_nodes(netlist; ground_node=draft.ground_node)
        for (node, numeric_node) in numeric_node_map
            final_node_map[node] = numeric_node
        end
    end

    return FinalizationArtifact(netlist, provenance, final_node_map, segmentation_plan)
end

function _validate_component_graph(draft::CircuitDraft)
    seen_prefixes = Set{String}()
    for component_id_value in draft.component_order
        component = draft.components[component_id_value]
        validate_component(component)
        in(component_prefix(component), seen_prefixes) &&
            _validation_error("Component prefix '$(component_prefix(component))' is duplicated.")
        push!(seen_prefixes, component_prefix(component))
    end
end

function _validate_endpoint_exists(draft::CircuitDraft, endpoint::PinRef, relation_id::String)
    component = _component(draft, endpoint.component_id)
    haskey(_pins(component), endpoint.pin) ||
        _validation_error("Relation '$(relation_id)' references unknown pin ':$(endpoint.pin)' on component '$(endpoint.component_id)'.")
end

function _validate_endpoint_exists(draft::CircuitDraft, endpoint::LineTapRef, relation_id::String)
    line = _line_for_ref(draft, endpoint)
    _validate_position(line, _position_m(endpoint, line), relation_id)
end

function _validate_endpoint_exists(draft::CircuitDraft, endpoint::LineSpanRef, relation_id::String)
    line = _line_for_ref(draft, endpoint)
    span = _span_m(endpoint, line)
    _validate_span(line, span.start_m, span.stop_m, relation_id)
end

_validate_endpoint_exists(::CircuitDraft, ::GroundRef, ::String) = nothing

function _require_endpoint_capability(draft::CircuitDraft, endpoint::PinRef, capability::Symbol, relation_id::String)
    component = _component(draft, endpoint.component_id)
    in(capability, allowed_couplings(component)) ||
        _validation_error("Relation '$(relation_id)' requires :$(capability) on component '$(component_id(component))'.")
end

function _require_endpoint_capability(draft::CircuitDraft, endpoint::LineTapRef, capability::Symbol, relation_id::String)
    component = _component(draft, endpoint.component_id)
    in(capability, allowed_couplings(component)) ||
        _validation_error("Relation '$(relation_id)' requires :$(capability) on component '$(component_id(component))'.")
end

function _require_endpoint_capability(draft::CircuitDraft, endpoint::LineSpanRef, capability::Symbol, relation_id::String)
    component = _component(draft, endpoint.component_id)
    in(capability, allowed_couplings(component)) ||
        _validation_error("Relation '$(relation_id)' requires :$(capability) on component '$(component_id(component))'.")
end

_require_endpoint_capability(::CircuitDraft, ::GroundRef, ::Symbol, ::String) = nothing

function _validate_relations(draft::CircuitDraft)
    seen_relation_ids = Set{String}()
    seen_ports = Set{Int}()
    for relation in draft.relations
        relation_id_value = _relation_id(relation)
        _require(!isempty(relation_id_value), "Relation id must not be empty.")
        in(relation_id_value, seen_relation_ids) &&
            _validation_error("Relation id '$(relation_id_value)' is duplicated.")
        push!(seen_relation_ids, relation_id_value)

        mode = _relation_mode(relation)
        mode in (:additive, :segmentation_only, :replacement, :annotation_only) ||
            _validation_error("Relation '$(relation_id_value)' has invalid modification mode ':$(mode)'.")

        if relation isa IdealConnectionRelation
            _is_discrete_endpoint(relation.endpoint_a) ||
                _validation_error("connect_pins! relation '$(relation.id)' has non-discrete endpoint A.")
            _is_discrete_endpoint(relation.endpoint_b) ||
                _validation_error("connect_pins! relation '$(relation.id)' has non-discrete endpoint B.")
            _validate_endpoint_exists(draft, relation.endpoint_a, relation.id)
            _validate_endpoint_exists(draft, relation.endpoint_b, relation.id)
            _require_endpoint_capability(draft, relation.endpoint_a, :ideal_connection, relation.id)
            _require_endpoint_capability(draft, relation.endpoint_b, :ideal_connection, relation.id)
        elseif relation isa CapacitiveCouplingRelation
            relation.endpoint_a isa LineSpanRef &&
                _validation_error("Capacitive relation '$(relation.id)' cannot use LineSpanRef.")
            relation.endpoint_b isa LineSpanRef &&
                _validation_error("Capacitive relation '$(relation.id)' cannot use LineSpanRef.")
            _validate_endpoint_exists(draft, relation.endpoint_a, relation.id)
            _validate_endpoint_exists(draft, relation.endpoint_b, relation.id)
            _require_endpoint_capability(draft, relation.endpoint_a, relation.endpoint_a isa LineTapRef ? :capacitive_tap : :capacitive_pin, relation.id)
            _require_endpoint_capability(draft, relation.endpoint_b, relation.endpoint_b isa LineTapRef ? :capacitive_tap : :capacitive_pin, relation.id)
        elseif relation isa CoupledWindowRelation
            _validate_coupled_window_spec(relation.spec)
            _validate_endpoint_exists(draft, relation.endpoint_a, relation.id)
            _validate_endpoint_exists(draft, relation.endpoint_b, relation.id)
            _require_endpoint_capability(draft, relation.endpoint_a, :coupled_window, relation.id)
            _require_endpoint_capability(draft, relation.endpoint_b, :coupled_window, relation.id)
        elseif relation isa PortTerminationRelation
            in(relation.port_number, seen_ports) &&
                _validation_error("Port number $(relation.port_number) is used by more than one relation.")
            push!(seen_ports, relation.port_number)
            _validate_endpoint_exists(draft, relation.endpoint, relation.id)
            _require_endpoint_capability(draft, relation.endpoint, :port, relation.id)
        end
    end
end

function _endpoint_node_token(draft::CircuitDraft, endpoint::PinRef)
    component = _component(draft, endpoint.component_id)
    node = get(_pins(component), endpoint.pin, nothing)
    node === nothing && _validation_error("Unknown pin ':$(endpoint.pin)' on component '$(component_id(component))'.")
    return node
end

_endpoint_node_token(draft::CircuitDraft, ::GroundRef) = draft.ground_node

function _build_node_resolver(draft::CircuitDraft)
    parent = Dict{String,String}()

    function ensure_node!(node::String)
        haskey(parent, node) || (parent[node] = node)
        return node
    end

    function find_root(node::String)
        ensure_node!(node)
        root = node
        while parent[root] != root
            root = parent[root]
        end
        current = node
        while parent[current] != current
            next_node = parent[current]
            parent[current] = root
            current = next_node
        end
        return root
    end

    function union_nodes!(node_a::String, node_b::String)
        root_a = find_root(node_a)
        root_b = find_root(node_b)
        root_a == root_b && return
        parent[root_b] = root_a
    end

    for component in values(draft.components)
        for node in values(_pins(component))
            ensure_node!(node)
        end
    end
    ensure_node!(draft.ground_node)

    for relation in draft.relations
        relation isa IdealConnectionRelation || continue
        node_a = _endpoint_node_token(draft, relation.endpoint_a)
        node_b = _endpoint_node_token(draft, relation.endpoint_b)
        union_nodes!(node_a, node_b)
    end

    members_by_root = Dict{String,Vector{String}}()
    for node in keys(parent)
        root = find_root(node)
        push!(get!(members_by_root, root, String[]), node)
    end

    labels_by_root = Dict{String,String}()
    auto_net_index = 1
    for root in sort(collect(keys(members_by_root)))
        members = sort(members_by_root[root])
        public_names = filter(node -> !_is_private_token(node), members)
        if !isempty(public_names)
            labels_by_root[root] = public_names[1]
        else
            labels_by_root[root] = "net_$(auto_net_index)"
            auto_net_index += 1
        end
    end

    node_map = Dict{String,String}()
    for node in keys(parent)
        node_map[node] = labels_by_root[find_root(node)]
    end

    resolver = node -> begin
        node_string = string(node)
        if haskey(parent, node_string)
            return labels_by_root[find_root(node_string)]
        end
        return node_string
    end

    return resolver, node_map
end

function _collect_lines(draft::CircuitDraft)
    lines = Dict{String,LineDeclaration}()
    ordered_ids = String[]
    for component_id_value in draft.component_order
        component = draft.components[component_id_value]
        for line_name in sort(collect(keys(_owned_lines(component))); by=String)
            line = _owned_lines(component)[line_name]
            haskey(lines, line.id) && _validation_error("Duplicate owned line id '$(line.id)'.")
            lines[line.id] = line
            push!(ordered_ids, line.id)
        end
    end
    return (by_id=lines, order=ordered_ids)
end

function _collect_replacement_spans(draft::CircuitDraft, lines)
    spans = Dict{String,Vector{NamedTuple}}()
    for relation in draft.relations
        relation isa CoupledWindowRelation || continue
        line_a = _line_for_ref(draft, relation.endpoint_a)
        line_b = _line_for_ref(draft, relation.endpoint_b)
        line_a.id == line_b.id && _validation_error("Coupled-window relation '$(relation.id)' must use two different lines.")
        span_a = _span_m(relation.endpoint_a, line_a)
        span_b = _span_m(relation.endpoint_b, line_b)
        _validate_span(line_a, span_a.start_m, span_a.stop_m, relation.id)
        _validate_span(line_b, span_b.start_m, span_b.stop_m, relation.id)
        isapprox(span_a.stop_m - span_a.start_m, span_b.stop_m - span_b.start_m) ||
            _validation_error("Coupled-window relation '$(relation.id)' spans must have the same physical length.")
        isapprox(span_a.stop_m - span_a.start_m, relation.spec.length_m) ||
            _validation_error("Coupled-window relation '$(relation.id)' spec length must match section length.")

        push!(get!(spans, line_a.id, NamedTuple[]), (start_m=span_a.start_m, stop_m=span_a.stop_m, relation_id=relation.id))
        push!(get!(spans, line_b.id, NamedTuple[]), (start_m=span_b.start_m, stop_m=span_b.stop_m, relation_id=relation.id))
    end
    return spans
end

function _collect_segmentation_requests(draft::CircuitDraft, lines, replacement_spans)
    requests = Dict{String,Vector{SegmentationRequest}}()

    for (line_id_value, spans) in replacement_spans
        for span in spans
            push!(get!(requests, line_id_value, SegmentationRequest[]), SegmentationRequest(line_id_value, span.start_m, :coupled_window_start, span.relation_id))
            push!(get!(requests, line_id_value, SegmentationRequest[]), SegmentationRequest(line_id_value, span.stop_m, :coupled_window_stop, span.relation_id))
        end
    end

    for relation in draft.relations
        relation isa CapacitiveCouplingRelation || continue
        for endpoint in (relation.endpoint_a, relation.endpoint_b)
            endpoint isa LineTapRef || continue
            line = _line_for_ref(draft, endpoint)
            position = _position_m(endpoint, line)
            _validate_position(line, position, relation.id)
            push!(get!(requests, line.id, SegmentationRequest[]), SegmentationRequest(line.id, position, :line_tap, relation.id))
        end
    end

    return requests
end

function _validate_position(line::LineDeclaration, position_m::Float64, relation_id::AbstractString)
    0.0 <= position_m <= line.spec.length_m ||
        _validation_error("Relation '$(relation_id)' requested a tap outside line '$(line.id)'.")
end

function _validate_span(line::LineDeclaration, start_m::Float64, stop_m::Float64, relation_id::AbstractString)
    0.0 <= start_m < stop_m <= line.spec.length_m ||
        _validation_error("Relation '$(relation_id)' requested a section outside line '$(line.id)'.")
end

function _validate_segmentation_conflicts(replacement_spans, segmentation_requests)
    for (line_id_value, spans) in replacement_spans
        sorted_spans = sort(spans; by=span -> span.start_m)
        for idx in 1:(length(sorted_spans) - 1)
            current = sorted_spans[idx]
            next_span = sorted_spans[idx + 1]
            current.stop_m > next_span.start_m &&
                _validation_error("Overlapping replacement spans on line '$(line_id_value)' are not supported.")
        end

        for request in get(segmentation_requests, line_id_value, SegmentationRequest[])
            request.reason == :line_tap || continue
            for span in spans
                if span.start_m < request.position_m < span.stop_m
                    _validation_error(
                        "Line tap from relation '$(request.relation_id)' falls inside replaced " *
                        "MTL span '$(span.relation_id)' on line '$(line_id_value)'."
                    )
                end
            end
        end
    end
end

function _build_segmentation_plan(draft::CircuitDraft, lines, replacement_spans, requests, resolve_node)
    plans = Dict{String,LineSegmentationPlan}()
    for line_id_value in lines.order
        line = lines.by_id[line_id_value]
        line_requests = get(requests, line_id_value, SegmentationRequest[])
        breakpoints = Float64[0.0, line.spec.length_m]
        for request in line_requests
            _push_unique_breakpoint!(breakpoints, request.position_m)
        end
        sort!(breakpoints)

        boundary_nodes = String[]
        for idx in eachindex(breakpoints)
            if idx == 1
                push!(boundary_nodes, resolve_node(line.start_node))
            elseif idx == length(breakpoints)
                push!(boundary_nodes, resolve_node(line.end_node))
            else
                push!(boundary_nodes, "$(line.prefix)_boundary$(idx - 1)")
            end
        end

        segments = SegmentPlan[]
        for idx in 1:(length(breakpoints) - 1)
            start_m = breakpoints[idx]
            stop_m = breakpoints[idx + 1]
            replacement = _matching_replacement(line_id_value, start_m, stop_m, replacement_spans)
            if isnothing(replacement)
                push!(
                    segments,
                    SegmentPlan(
                        :uncoupled,
                        line.id,
                        line.component_id,
                        "$(line.prefix)_chunk$(idx)",
                        start_m,
                        stop_m,
                        boundary_nodes[idx],
                        boundary_nodes[idx + 1],
                        _section_count_for_chunk(line.spec, stop_m - start_m),
                        idx == (length(breakpoints) - 1) ? line.add_shunt_at_last_node : true,
                        "",
                    ),
                )
            else
                relation = _relation_by_id(draft, replacement.relation_id)
                relation isa CoupledWindowRelation ||
                    _validation_error("Replacement relation '$(replacement.relation_id)' is not a CoupledWindowRelation.")
                push!(
                    segments,
                    SegmentPlan(
                        :replacement,
                        line.id,
                        line.component_id,
                        relation.id,
                        start_m,
                        stop_m,
                        boundary_nodes[idx],
                        boundary_nodes[idx + 1],
                        relation.spec.n_sections,
                        true,
                        relation.id,
                    ),
                )
            end
        end

        plans[line_id_value] = LineSegmentationPlan(line_id_value, breakpoints, boundary_nodes, line_requests, segments)
    end
    return SegmentationPlan(plans)
end

function _push_unique_breakpoint!(breakpoints::Vector{Float64}, value::Float64)
    any(existing -> isapprox(existing, value), breakpoints) || push!(breakpoints, value)
    return breakpoints
end

function _matching_replacement(line_id_value::String, start_m::Float64, stop_m::Float64, replacement_spans)
    matches = NamedTuple[]
    for span in get(replacement_spans, line_id_value, NamedTuple[])
        if isapprox(span.start_m, start_m) && isapprox(span.stop_m, stop_m)
            push!(matches, span)
        end
    end
    length(matches) <= 1 || _validation_error("Multiple replacements match one line segment on line '$(line_id_value)'.")
    return isempty(matches) ? nothing : matches[1]
end

function _section_count_for_chunk(spec::RLGCSpec, length_m::Float64)
    _require(length_m > 0, "Chunk length must be positive.")
    density = spec.n_sections / spec.length_m
    return max(1, round(Int, density * length_m))
end

function _relation_by_id(draft::CircuitDraft, relation_id::AbstractString)
    for relation in draft.relations
        relation.id == relation_id && return relation
    end
    _validation_error("Unknown relation id '$(relation_id)'.")
end

###############################################################################
# Primitive emission and provenance
###############################################################################

function _primitive_kind(name::AbstractString)
    isempty(name) && return :unknown
    return Symbol(String([first(name)]))
end

function _push_row!(
    netlist::Vector{Tuple{String,String,String,Any}},
    provenance::Vector{ProvenanceRecord},
    row::Tuple{String,String,String,Any};
    component_ids=String[],
    relation_id=nothing,
    role::Symbol,
    semantic_path=String[],
    segment_id=nothing,
    parameter_owner=nothing,
    parameter_snapshot=Dict{Symbol,Any}(),
)
    row_index = length(netlist) + 1
    push!(netlist, row)
    push!(
        provenance,
        ProvenanceRecord(
            row_index,
            row[1],
            _primitive_kind(row[1]),
            String.(component_ids),
            isnothing(relation_id) ? nothing : String(relation_id),
            :finalization,
            role,
            String.(semantic_path),
            isnothing(segment_id) ? nothing : String(segment_id),
            isnothing(parameter_owner) ? nothing : Symbol(parameter_owner),
            Dict{Symbol,Any}(parameter_snapshot),
        ),
    )
end

function _emit_component_rows!(netlist, provenance, draft::CircuitDraft, resolve_node)
    for component_id_value in draft.component_order
        component = draft.components[component_id_value]
        lower_component!(netlist, provenance, component, draft, resolve_node)
    end
end

function lower_component!(netlist, provenance, component::AbstractReusableComponent, draft::CircuitDraft, resolve_node)
    rule = lowering_rule(component)
    if rule in (:none, :distributed_line, :quarter_wave_resonator)
        return
    end
    _validation_error("Unknown lowering rule ':$(rule)' for component '$(component_id(component))'.")
end

function lower_component!(netlist, provenance, component::LCResonatorComponent, draft::CircuitDraft, resolve_node)
    _emit_parallel_lc!(netlist, provenance, component, resolve_node; left_pin=:plus, right_pin=:minus)
end

function lower_component!(netlist, provenance, component::LCQubitComponent, draft::CircuitDraft, resolve_node)
    _emit_parallel_lc!(netlist, provenance, component, resolve_node; left_pin=:pad, right_pin=:minus)
end

function lower_component!(netlist, provenance, component::TunableCouplerComponent, draft::CircuitDraft, resolve_node)
    _emit_parallel_lc!(netlist, provenance, component, resolve_node; left_pin=:left, right_pin=:right)
end

function lower_component!(netlist, provenance, component::DifferentialLCQubitComponent, draft::CircuitDraft, resolve_node)
    pad1 = resolve_node(_pins(component)[:pad1])
    pad2 = resolve_node(_pins(component)[:pad2])
    prefix = component.prefix
    snapshot = component_parameter_snapshot(component)

    if component.Cg1_f > 0
        name = _component_name("C", prefix, "g1")
        _push_row!(netlist, provenance, (name, pad1, draft.ground_node, component.Cg1_f); component_ids=[component.id], role=:component_self_lumped, semantic_path=[component.id, "Cg1"], parameter_owner=:component, parameter_snapshot=snapshot)
    end
    if component.Cg2_f > 0
        name = _component_name("C", prefix, "g2")
        _push_row!(netlist, provenance, (name, pad2, draft.ground_node, component.Cg2_f); component_ids=[component.id], role=:component_self_lumped, semantic_path=[component.id, "Cg2"], parameter_owner=:component, parameter_snapshot=snapshot)
    end

    c_name = _component_name("C", prefix, "q")
    l_name = _component_name("L", prefix, "q")
    _push_row!(netlist, provenance, (c_name, pad1, pad2, component.Cq_f); component_ids=[component.id], role=:component_self_lumped, semantic_path=[component.id, "Cq"], parameter_owner=:component, parameter_snapshot=snapshot)
    _push_row!(netlist, provenance, (l_name, pad1, pad2, component.Lq_h); component_ids=[component.id], role=:component_self_lumped, semantic_path=[component.id, "Lq"], parameter_owner=:component, parameter_snapshot=snapshot)
end

function lower_component!(netlist, provenance, component::PurcellFilterComponent, draft::CircuitDraft, resolve_node)
    prefix = component.prefix
    snapshot = component_parameter_snapshot(component)
    pins = _pins(component)
    left_name = _component_name("C", prefix, "in")
    right_name = _component_name("C", prefix, "out")
    _push_row!(netlist, provenance, (left_name, resolve_node(pins[:left]), component.line_left_node, component.left_coupling_cap_f); component_ids=[component.id], role=:component_self_lumped, semantic_path=[component.id, "left_coupler"], parameter_owner=:component, parameter_snapshot=snapshot)
    _push_row!(netlist, provenance, (right_name, component.line_right_node, resolve_node(pins[:right]), component.right_coupling_cap_f); component_ids=[component.id], role=:component_self_lumped, semantic_path=[component.id, "right_coupler"], parameter_owner=:component, parameter_snapshot=snapshot)
end

function _emit_parallel_lc!(netlist, provenance, component, resolve_node; left_pin::Symbol, right_pin::Symbol)
    pins = _pins(component)
    node_a = resolve_node(pins[left_pin])
    node_b = resolve_node(pins[right_pin])
    prefix = component_prefix(component)
    snapshot = component_parameter_snapshot(component)
    c_name = _component_name("C", prefix, "self")
    l_name = _component_name("L", prefix, "self")
    _push_row!(netlist, provenance, (c_name, node_a, node_b, component.C_f); component_ids=[component_id(component)], role=:component_self_lumped, semantic_path=[component_id(component), "C"], parameter_owner=:component, parameter_snapshot=snapshot)
    _push_row!(netlist, provenance, (l_name, node_a, node_b, component.L_h); component_ids=[component_id(component)], role=:component_self_lumped, semantic_path=[component_id(component), "L"], parameter_owner=:component, parameter_snapshot=snapshot)
end

function _emit_line_rows!(netlist, provenance, draft::CircuitDraft, lines, plan::SegmentationPlan)
    for line_id_value in lines.order
        line = lines.by_id[line_id_value]
        line_plan = plan.lines[line_id_value]
        component = _component(draft, line.component_id)
        snapshot = component_parameter_snapshot(component)
        for segment in line_plan.segments
            segment.kind == :uncoupled || continue
            chunk_spec = RLGCSpec(
                length_m=segment.stop_m - segment.start_m,
                n_sections=segment.n_sections,
                l_per_m_h=line.spec.l_per_m_h,
                c_per_m_f=line.spec.c_per_m_f,
                r_per_m_ohm=line.spec.r_per_m_ohm,
                g_per_m_s=line.spec.g_per_m_s,
            )
            before = length(netlist)
            add_distributed_segment!(
                netlist;
                prefix=segment.prefix,
                start_node=segment.left_node,
                spec=chunk_spec,
                ground_node=line.ground_node,
                final_node=segment.right_node,
                add_shunt_at_last_node=segment.add_shunt_at_last_node,
            )
            _add_generated_provenance!(
                provenance,
                netlist,
                before;
                component_ids=[line.component_id],
                relation_id=nothing,
                default_role=:component_distributed_self,
                semantic_path=[line.component_id, line.id, segment.prefix],
                segment_id=segment.prefix,
                parameter_owner=:component,
                parameter_snapshot=snapshot,
            )
        end
    end
end

function _emit_additive_relation_rows!(netlist, provenance, draft::CircuitDraft, plan::SegmentationPlan, resolve_node)
    for relation in draft.relations
        if relation isa CapacitiveCouplingRelation
            node_a = _resolved_endpoint_node(draft, relation.endpoint_a, plan, resolve_node)
            node_b = _resolved_endpoint_node(draft, relation.endpoint_b, plan, resolve_node)
            name = _component_name("C", relation.id, "coupling")
            _push_row!(
                netlist,
                provenance,
                (name, node_a, node_b, relation.capacitance_f);
                component_ids=_component_ids_for_endpoints(draft, relation.endpoint_a, relation.endpoint_b),
                relation_id=relation.id,
                role=:relation_lumped_coupling_C,
                semantic_path=[relation.id],
                parameter_owner=:relation,
                parameter_snapshot=relation_parameter_snapshot(relation),
            )
        elseif relation isa PortTerminationRelation
            node = _resolved_endpoint_node(draft, relation.endpoint, plan, resolve_node)
            port_name = "P$(relation.port_number)"
            resistor_name = _component_name("R", relation.id, "termination")
            snapshot = relation_parameter_snapshot(relation)
            _push_row!(netlist, provenance, (port_name, node, draft.ground_node, relation.port_number); component_ids=_component_ids_for_endpoints(draft, relation.endpoint), relation_id=relation.id, role=:relation_port, semantic_path=[relation.id, "port"], parameter_owner=:relation, parameter_snapshot=snapshot)
            _push_row!(netlist, provenance, (resistor_name, node, draft.ground_node, relation.resistance_ohm); component_ids=_component_ids_for_endpoints(draft, relation.endpoint), relation_id=relation.id, role=:relation_port, semantic_path=[relation.id, "termination"], parameter_owner=:relation, parameter_snapshot=snapshot)
        end
    end
end

function _emit_replacement_relation_rows!(netlist, provenance, draft::CircuitDraft, plan::SegmentationPlan)
    for relation in draft.relations
        relation isa CoupledWindowRelation || continue
        endpoints_a = _replacement_segment_endpoints(draft, relation.endpoint_a, relation.id, plan)
        endpoints_b = _replacement_segment_endpoints(draft, relation.endpoint_b, relation.id, plan)
        before = length(netlist)
        add_coupled_window!(
            netlist;
            prefix=relation.id,
            left_node_a=endpoints_a.left_node,
            right_node_a=endpoints_a.right_node,
            left_node_b=endpoints_b.left_node,
            right_node_b=endpoints_b.right_node,
            spec=relation.spec,
            ground_node=draft.ground_node,
        )
        _add_generated_provenance!(
            provenance,
            netlist,
            before;
            component_ids=_component_ids_for_endpoints(draft, relation.endpoint_a, relation.endpoint_b),
            relation_id=relation.id,
            default_role=:relation_mtl,
            semantic_path=[relation.id, relation.endpoint_a.component_id, relation.endpoint_b.component_id],
            segment_id=relation.id,
            parameter_owner=:relation,
            parameter_snapshot=relation_parameter_snapshot(relation),
        )
    end
end

function _component_ids_for_endpoints(draft::CircuitDraft, endpoints::AbstractEndpointRef...)
    ids = String[]
    for endpoint in endpoints
        if endpoint isa PinRef || endpoint isa LineTapRef || endpoint isa LineSpanRef
            push!(ids, endpoint.component_id)
        end
    end
    return unique(ids)
end

function _add_generated_provenance!(
    provenance,
    netlist,
    before::Int;
    component_ids,
    relation_id,
    default_role::Symbol,
    semantic_path::Vector{String},
    segment_id,
    parameter_owner,
    parameter_snapshot::Dict{Symbol,Any},
)
    for idx in (before + 1):length(netlist)
        name = netlist[idx][1]
        role = _role_for_generated_row(name, default_role)
        row_index = idx
        push!(
            provenance,
            ProvenanceRecord(
                row_index,
                name,
                _primitive_kind(name),
                String.(component_ids),
                isnothing(relation_id) ? nothing : String(relation_id),
                :finalization,
                role,
                String.(semantic_path),
                isnothing(segment_id) ? nothing : String(segment_id),
                isnothing(parameter_owner) ? nothing : Symbol(parameter_owner),
                Dict{Symbol,Any}(parameter_snapshot),
            ),
        )
    end
end

function _role_for_generated_row(name::String, default_role::Symbol)
    if default_role == :component_distributed_self
        startswith(name, "L") && return :component_distributed_self_L
        startswith(name, "C") && return :component_distributed_self_C
        return :component_distributed_self_lumped
    elseif default_role == :relation_mtl
        startswith(name, "K") && return :relation_mutual_K
        occursin("_xsec", name) && return :relation_mtl_cross_C
        startswith(name, "L") && return :relation_mtl_self_L
        startswith(name, "C") && return :relation_mtl_self_C
        return :relation_mtl_self_lumped
    end
    return default_role
end

function relation_parameter_snapshot(relation::IdealConnectionRelation)
    return Dict{Symbol,Any}()
end

function relation_parameter_snapshot(relation::CapacitiveCouplingRelation)
    return Dict{Symbol,Any}(:capacitance_f => relation.capacitance_f)
end

function relation_parameter_snapshot(relation::CoupledWindowRelation)
    return Dict{Symbol,Any}(
        :length_m => relation.spec.length_m,
        :n_sections => relation.spec.n_sections,
        :l11_per_m_h => relation.spec.l11_per_m_h,
        :l22_per_m_h => relation.spec.l22_per_m_h,
        :lm_per_m_h => relation.spec.lm_per_m_h,
        :c1g_per_m_f => relation.spec.c1g_per_m_f,
        :c2g_per_m_f => relation.spec.c2g_per_m_f,
        :cm_per_m_f => relation.spec.cm_per_m_f,
    )
end

function relation_parameter_snapshot(relation::PortTerminationRelation)
    return Dict{Symbol,Any}(:port_number => relation.port_number, :resistance_ohm => relation.resistance_ohm)
end

function _resolved_endpoint_node(draft::CircuitDraft, endpoint::PinRef, plan, resolve_node)
    return resolve_node(_endpoint_node_token(draft, endpoint))
end

_resolved_endpoint_node(draft::CircuitDraft, ::GroundRef, plan, resolve_node) = draft.ground_node

function _resolved_endpoint_node(draft::CircuitDraft, endpoint::LineTapRef, plan::SegmentationPlan, resolve_node)
    line = _line_for_ref(draft, endpoint)
    position = _position_m(endpoint, line)
    line_plan = plan.lines[line.id]
    for (idx, breakpoint) in enumerate(line_plan.breakpoints_m)
        if isapprox(breakpoint, position)
            return line_plan.boundary_nodes[idx]
        end
    end
    _validation_error("Internal error: unresolved tap endpoint on line '$(line.id)'.")
end

function _resolved_endpoint_node(draft::CircuitDraft, endpoint::LineSpanRef, plan, resolve_node)
    _validation_error("LineSpanRef cannot resolve to a discrete endpoint.")
end

function _replacement_segment_endpoints(draft::CircuitDraft, endpoint::LineSpanRef, relation_id_value::String, plan::SegmentationPlan)
    line = _line_for_ref(draft, endpoint)
    line_plan = plan.lines[line.id]
    for segment in line_plan.segments
        if segment.kind == :replacement && segment.relation_id == relation_id_value
            return (left_node=segment.left_node, right_node=segment.right_node)
        end
    end
    _validation_error("Internal error: missing replacement segment for relation '$(relation_id_value)' on line '$(line.id)'.")
end

###############################################################################
# Semantic sweep
###############################################################################

struct ComponentParameterTarget <: AbstractSweepTarget
    component_id::String
    parameter::Symbol
end

struct RelationParameterTarget <: AbstractSweepTarget
    relation_id::String
    parameter::Symbol
end

const SweepTarget = Union{ComponentParameterTarget,RelationParameterTarget}

struct SweepAssignment
    target::SweepTarget
    value::Any
end

struct SweepAxis
    label::String
    unit::String
    display_divisor::Float64
    assignments_by_index::Vector{Vector{SweepAssignment}}
    display_values::Vector{Any}
    value_labels::Vector{String}
end

struct SweepPlan
    axes::Vector{SweepAxis}
end

struct SweepPoint
    index::Int
    coordinates::Tuple
    assignments::Vector{SweepAssignment}
    metadata::Dict{Symbol,Any}
end

struct SweepResultRow
    data::Dict{Symbol,Any}
end

component_parameter(component_id::AbstractString, parameter::Symbol) = ComponentParameterTarget(String(component_id), parameter)
relation_parameter(relation_id::AbstractString, parameter::Symbol) = RelationParameterTarget(String(relation_id), parameter)

function _value_label(value)
    value isa Number && return string(value)
    return string(value)
end

function _display_value(value, divisor::Float64)
    value isa Number && return value / divisor
    return value
end

function sweep_component(
    component_id::AbstractString,
    parameter::Symbol,
    values;
    label::AbstractString="$(component_id).$(parameter)",
    unit::AbstractString="",
    display_divisor::Real=1.0,
)
    target = component_parameter(component_id, parameter)
    divisor = Float64(display_divisor)
    raw_values = collect(values)
    assignments = [[SweepAssignment(target, value)] for value in raw_values]
    display_values = [_display_value(value, divisor) for value in raw_values]
    return SweepAxis(String(label), String(unit), divisor, assignments, display_values, _value_label.(display_values))
end

function sweep_relation(
    relation_id::AbstractString,
    parameter::Symbol,
    values;
    label::AbstractString="$(relation_id).$(parameter)",
    unit::AbstractString="",
    display_divisor::Real=1.0,
)
    target = relation_parameter(relation_id, parameter)
    divisor = Float64(display_divisor)
    raw_values = collect(values)
    assignments = [[SweepAssignment(target, value)] for value in raw_values]
    display_values = [_display_value(value, divisor) for value in raw_values]
    return SweepAxis(String(label), String(unit), divisor, assignments, display_values, _value_label.(display_values))
end

function sweep_parameters(assignments; values, label::AbstractString, unit::AbstractString="", display_divisor::Real=1.0)
    raw_values = collect(values)
    divisor = Float64(display_divisor)
    assignment_specs = collect(assignments)
    axis_assignments = Vector{Vector{SweepAssignment}}()
    for (value_index, value) in enumerate(raw_values)
        point_assignments = SweepAssignment[]
        for spec in assignment_specs
            spec isa Pair || _validation_error("sweep_parameters assignments must be target => transform pairs.")
            target = _parse_sweep_target(spec.first)
            rhs = spec.second
            assignment_value = if rhs isa Function
                rhs(value)
            elseif rhs isa AbstractVector || rhs isa Tuple
                rhs[value_index]
            else
                rhs
            end
            push!(point_assignments, SweepAssignment(target, assignment_value))
        end
        push!(axis_assignments, point_assignments)
    end
    display_values = [_display_value(value, divisor) for value in raw_values]
    return SweepAxis(String(label), String(unit), divisor, axis_assignments, display_values, _value_label.(display_values))
end

_parse_sweep_target(target::ComponentParameterTarget) = target
_parse_sweep_target(target::RelationParameterTarget) = target

function _parse_sweep_target(target::Tuple)
    length(target) == 3 || _validation_error("Tuple sweep target must be (:component|:relation, id, parameter).")
    owner, id, parameter = target
    parameter isa Symbol || _validation_error("Tuple sweep target parameter must be a Symbol.")
    owner == :component && return component_parameter(String(id), parameter)
    owner == :relation && return relation_parameter(String(id), parameter)
    _validation_error("Tuple sweep target owner must be :component or :relation.")
end

function sweep_plan(axes::SweepAxis...)
    return SweepPlan(collect(axes))
end

function design_sweep_point_count(plan::SweepPlan)
    total = 1
    for axis in plan.axes
        total *= max(length(axis.assignments_by_index), 1)
    end
    return total
end

function _decode_design_sweep_index(plan::SweepPlan, sweep_index::Int)
    isempty(plan.axes) && return ()
    remaining = sweep_index
    coordinates = zeros(Int, length(plan.axes))
    for axis_index in length(plan.axes):-1:1
        axis_size = max(length(plan.axes[axis_index].assignments_by_index), 1)
        coordinates[axis_index] = remaining % axis_size
        remaining ÷= axis_size
    end
    return Tuple(coordinates)
end

function sweep_point(plan::SweepPlan, sweep_index::Int)
    total = design_sweep_point_count(plan)
    0 <= sweep_index < total || _validation_error("Sweep index $(sweep_index) is outside 0:$(total - 1).")
    coordinates = _decode_design_sweep_index(plan, sweep_index)
    assignments = SweepAssignment[]
    metadata = Dict{Symbol,Any}(:sweep_index => sweep_index, :axis_count => length(plan.axes))
    for (axis_index, axis) in enumerate(plan.axes)
        coord = coordinates[axis_index]
        append!(assignments, axis.assignments_by_index[coord + 1])
        metadata[Symbol("axis_$(axis_index)_label")] = axis.label
        metadata[Symbol("axis_$(axis_index)_unit")] = axis.unit
        metadata[Symbol("axis_$(axis_index)_coordinate")] = coord
        metadata[Symbol("axis_$(axis_index)_value")] = axis.display_values[coord + 1]
        metadata[Symbol("axis_$(axis_index)_value_label")] = axis.value_labels[coord + 1]
    end
    return SweepPoint(sweep_index, coordinates, assignments, metadata)
end

function _clone_draft(draft::CircuitDraft)
    return CircuitDraft(
        draft.name,
        draft.ground_node,
        copy(draft.components),
        copy(draft.component_order),
        copy(draft.relations),
        copy(draft.relation_ids),
        copy(draft.finalization_config),
    )
end

function apply_sweep_point(draft::CircuitDraft, point::SweepPoint)
    patched = _clone_draft(draft)
    for assignment in point.assignments
        _apply_assignment!(patched, assignment)
    end
    return patched
end

function _apply_assignment!(draft::CircuitDraft, assignment::SweepAssignment)
    target = assignment.target
    if target isa ComponentParameterTarget
        component = _component(draft, target.component_id)
        draft.components[target.component_id] = with_component_parameter(component, target.parameter, assignment.value)
    elseif target isa RelationParameterTarget
        found = false
        for idx in eachindex(draft.relations)
            if draft.relations[idx].id == target.relation_id
                draft.relations[idx] = with_relation_parameter(draft.relations[idx], target.parameter, assignment.value)
                found = true
                break
            end
        end
        found || _validation_error("Unknown relation id '$(target.relation_id)' in sweep target.")
    end
end

function _positive_float(value, name::Symbol)
    value = Float64(value)
    value > 0 || _validation_error("Sweep parameter ':$(name)' must be positive.")
    return value
end

function _nonnegative_float(value, name::Symbol)
    value = Float64(value)
    value >= 0 || _validation_error("Sweep parameter ':$(name)' must be non-negative.")
    return value
end

function _with_rlgc_parameter(spec::RLGCSpec, parameter::Symbol, value)
    if parameter in (:length_m, :line_length_m)
        return RLGCSpec(length_m=_positive_float(value, parameter), n_sections=spec.n_sections, l_per_m_h=spec.l_per_m_h, c_per_m_f=spec.c_per_m_f, r_per_m_ohm=spec.r_per_m_ohm, g_per_m_s=spec.g_per_m_s)
    elseif parameter == :n_sections
        n = Int(value)
        n > 0 || _validation_error("n_sections must be positive.")
        return RLGCSpec(length_m=spec.length_m, n_sections=n, l_per_m_h=spec.l_per_m_h, c_per_m_f=spec.c_per_m_f, r_per_m_ohm=spec.r_per_m_ohm, g_per_m_s=spec.g_per_m_s)
    elseif parameter in (:l_per_m_h, :c_per_m_f, :r_per_m_ohm, :g_per_m_s)
        kwargs = Dict{Symbol,Any}(
            :length_m => spec.length_m,
            :n_sections => spec.n_sections,
            :l_per_m_h => spec.l_per_m_h,
            :c_per_m_f => spec.c_per_m_f,
            :r_per_m_ohm => spec.r_per_m_ohm,
            :g_per_m_s => spec.g_per_m_s,
        )
        kwargs[parameter] = parameter in (:r_per_m_ohm, :g_per_m_s) ? _nonnegative_float(value, parameter) : _positive_float(value, parameter)
        return RLGCSpec(; kwargs...)
    end
    _validation_error("Unsupported RLGC parameter ':$(parameter)'.")
end

function with_component_parameter(component::LCResonatorComponent, parameter::Symbol, value)
    parameter in (:L, :L_h) && return LCResonatorComponent(component.id, component.prefix, _positive_float(value, parameter), component.C_f)
    parameter in (:C, :C_f) && return LCResonatorComponent(component.id, component.prefix, component.L_h, _positive_float(value, parameter))
    _validation_error("Unsupported component parameter ':$(parameter)' for '$(component.id)'.")
end

function with_component_parameter(component::LCQubitComponent, parameter::Symbol, value)
    parameter in (:L, :L_h) && return LCQubitComponent(component.id, component.prefix, _positive_float(value, parameter), component.C_f)
    parameter in (:C, :C_f) && return LCQubitComponent(component.id, component.prefix, component.L_h, _positive_float(value, parameter))
    _validation_error("Unsupported component parameter ':$(parameter)' for '$(component.id)'.")
end

function with_component_parameter(component::DifferentialLCQubitComponent, parameter::Symbol, value)
    parameter == :Cg1_f && return DifferentialLCQubitComponent(component.id, component.prefix, _nonnegative_float(value, parameter), component.Cg2_f, component.Cq_f, component.Lq_h)
    parameter == :Cg2_f && return DifferentialLCQubitComponent(component.id, component.prefix, component.Cg1_f, _nonnegative_float(value, parameter), component.Cq_f, component.Lq_h)
    parameter == :Cq_f && return DifferentialLCQubitComponent(component.id, component.prefix, component.Cg1_f, component.Cg2_f, _positive_float(value, parameter), component.Lq_h)
    parameter == :Lq_h && return DifferentialLCQubitComponent(component.id, component.prefix, component.Cg1_f, component.Cg2_f, component.Cq_f, _positive_float(value, parameter))
    _validation_error("Unsupported component parameter ':$(parameter)' for '$(component.id)'.")
end

function with_component_parameter(component::TunableCouplerComponent, parameter::Symbol, value)
    parameter in (:L, :L_h) && return TunableCouplerComponent(component.id, component.prefix, _positive_float(value, parameter), component.C_f)
    parameter in (:C, :C_f) && return TunableCouplerComponent(component.id, component.prefix, component.L_h, _positive_float(value, parameter))
    _validation_error("Unsupported component parameter ':$(parameter)' for '$(component.id)'.")
end

function with_component_parameter(component::CPWLineComponent, parameter::Symbol, value)
    return CPWLineComponent(component.id, component.prefix, _with_rlgc_parameter(component.line, parameter, value), component.ground_node, component.add_shunt_at_last_node)
end

function with_component_parameter(component::PurcellFilterComponent, parameter::Symbol, value)
    parameter == :left_coupling_cap_f && return PurcellFilterComponent(component.id, component.prefix, component.line, _positive_float(value, parameter), component.right_coupling_cap_f, component.ground_node, component.line_left_node, component.line_right_node)
    parameter == :right_coupling_cap_f && return PurcellFilterComponent(component.id, component.prefix, component.line, component.left_coupling_cap_f, _positive_float(value, parameter), component.ground_node, component.line_left_node, component.line_right_node)
    return PurcellFilterComponent(component.id, component.prefix, _with_rlgc_parameter(component.line, parameter, value), component.left_coupling_cap_f, component.right_coupling_cap_f, component.ground_node, component.line_left_node, component.line_right_node)
end

function with_component_parameter(component::QuarterWaveResonatorComponent, parameter::Symbol, value)
    return QuarterWaveResonatorComponent(component.id, component.prefix, _with_rlgc_parameter(component.line, parameter, value), component.boundary, component.ground_node)
end

function with_component_parameter(component::ExternalPinComponent, parameter::Symbol, value)
    _validation_error("External pin component '$(component.id)' has no sweepable component parameters.")
end

function _with_coupled_window_spec_parameter(spec::CoupledWindowSpec, parameter::Symbol, value)
    kwargs = Dict{Symbol,Any}(
        :length_m => spec.length_m,
        :n_sections => spec.n_sections,
        :l11_per_m_h => spec.l11_per_m_h,
        :l22_per_m_h => spec.l22_per_m_h,
        :lm_per_m_h => spec.lm_per_m_h,
        :c1g_per_m_f => spec.c1g_per_m_f,
        :c2g_per_m_f => spec.c2g_per_m_f,
        :cm_per_m_f => spec.cm_per_m_f,
        :r1_per_m_ohm => spec.r1_per_m_ohm,
        :r2_per_m_ohm => spec.r2_per_m_ohm,
        :g1_per_m_s => spec.g1_per_m_s,
        :g2_per_m_s => spec.g2_per_m_s,
    )
    if parameter in (:window_length_m, :length_m)
        kwargs[:length_m] = _positive_float(value, parameter)
    elseif parameter == :n_sections
        n = Int(value)
        n > 0 || _validation_error("n_sections must be positive.")
        kwargs[:n_sections] = n
    elseif haskey(kwargs, parameter)
        positive_params = (:l11_per_m_h, :l22_per_m_h, :c1g_per_m_f, :c2g_per_m_f)
        kwargs[parameter] = if parameter in positive_params
            _positive_float(value, parameter)
        elseif parameter == :lm_per_m_h
            Float64(value)
        else
            _nonnegative_float(value, parameter)
        end
    else
        _validation_error("Unsupported coupled-window parameter ':$(parameter)'.")
    end
    return CoupledWindowSpec(; kwargs...)
end

function _with_span_parameter(span::LineSpanRef, parameter::Symbol, value)
    if parameter in (:endpoint_start, :start)
        return LineSpanRef(span.component_id, span.line, Float64(value), span.stop, span.mode)
    elseif parameter in (:endpoint_stop, :stop)
        return LineSpanRef(span.component_id, span.line, span.start, Float64(value), span.mode)
    elseif parameter in (:endpoint_start_m, :start_m)
        return LineSpanRef(span.component_id, span.line, Float64(value), span.stop, :meter)
    elseif parameter in (:endpoint_stop_m, :stop_m)
        return LineSpanRef(span.component_id, span.line, span.start, Float64(value), :meter)
    end
    _validation_error("Unsupported span endpoint parameter ':$(parameter)'.")
end

function with_relation_parameter(relation::CapacitiveCouplingRelation, parameter::Symbol, value)
    parameter in (:C, :capacitance_f) &&
        return CapacitiveCouplingRelation(relation.id, relation.endpoint_a, relation.endpoint_b, _positive_float(value, parameter), relation.modification_mode)
    _validation_error("Unsupported relation parameter ':$(parameter)' for relation '$(relation.id)'.")
end

function with_relation_parameter(relation::CoupledWindowRelation, parameter::Symbol, value)
    if startswith(String(parameter), "endpoint_a_")
        local_parameter = Symbol(replace(String(parameter), "endpoint_a_" => ""))
        return CoupledWindowRelation(relation.id, _with_span_parameter(relation.endpoint_a, local_parameter, value), relation.endpoint_b, relation.spec, relation.modification_mode)
    elseif startswith(String(parameter), "endpoint_b_")
        local_parameter = Symbol(replace(String(parameter), "endpoint_b_" => ""))
        return CoupledWindowRelation(relation.id, relation.endpoint_a, _with_span_parameter(relation.endpoint_b, local_parameter, value), relation.spec, relation.modification_mode)
    end
    return CoupledWindowRelation(relation.id, relation.endpoint_a, relation.endpoint_b, _with_coupled_window_spec_parameter(relation.spec, parameter, value), relation.modification_mode)
end

function with_relation_parameter(relation::PortTerminationRelation, parameter::Symbol, value)
    parameter == :resistance_ohm &&
        return PortTerminationRelation(relation.id, relation.endpoint, relation.port_number, _positive_float(value, parameter), relation.modification_mode)
    _validation_error("Unsupported relation parameter ':$(parameter)' for relation '$(relation.id)'.")
end

function with_relation_parameter(relation::IdealConnectionRelation, parameter::Symbol, value)
    _validation_error("Ideal connection relation '$(relation.id)' has no sweepable relation parameters.")
end

function default_finalize_evaluator(patched_draft::CircuitDraft, artifact::FinalizationArtifact, point::SweepPoint)
    return Dict{Symbol,Any}(
        :success => true,
        :netlist_rows => length(artifact.netlist),
        :provenance_rows => length(artifact.provenance_table),
    )
end

function run_design_sweep(
    draft::CircuitDraft,
    plan::SweepPlan;
    evaluator=default_finalize_evaluator,
    on_error::Symbol=:throw,
    use_threads::Bool=false,
    persisted_csv_path::Union{Nothing,AbstractString}=nothing,
)
    on_error in (:throw, :record) || _validation_error("on_error must be :throw or :record.")
    total = design_sweep_point_count(plan)
    rows = Vector{Dict{Symbol,Any}}(undef, total)

    function evaluate_index(sweep_index::Int)
        point = sweep_point(plan, sweep_index)
        row = copy(point.metadata)
        row[:assignment_count] = length(point.assignments)
        try
            patched = apply_sweep_point(draft, point)
            artifact = finalize_circuit(patched)
            result = evaluator(patched, artifact, point)
            for (key, value) in pairs(result)
                row[Symbol(key)] = value
            end
            row[:success] = get(row, :success, true)
        catch err
            on_error == :throw && rethrow()
            row[:success] = false
            row[:error_type] = string(typeof(err))
            row[:error] = sprint(showerror, err)
        end
        return row
    end

    if use_threads && total > 1
        Base.Threads.@threads for sweep_index in 0:(total - 1)
            rows[sweep_index + 1] = evaluate_index(sweep_index)
        end
    else
        for sweep_index in 0:(total - 1)
            rows[sweep_index + 1] = evaluate_index(sweep_index)
        end
    end

    df = _sweep_rows_to_dataframe(rows)
    if !isnothing(persisted_csv_path)
        mkpath(dirname(String(persisted_csv_path)))
        CSV.write(String(persisted_csv_path), df)
    end
    return df
end

function _sweep_rows_to_dataframe(rows::Vector{Dict{Symbol,Any}})
    keys_all = Symbol[]
    for row in rows
        for key in keys(row)
            in(key, keys_all) || push!(keys_all, key)
        end
    end
    columns = Dict{Symbol,Vector{Any}}()
    for key in keys_all
        columns[key] = [get(row, key, missing) for row in rows]
    end
    return DataFrame(columns)
end

###############################################################################
# Optional numeric node lowering
###############################################################################

function _renumber_netlist_nodes(
    netlist::Vector{Tuple{String,String,String,Any}};
    ground_node::AbstractString="0",
)
    node_map = Dict{String,String}()
    renumbered = Tuple{String,String,String,Any}[]

    function to_numeric_node(node::String)
        if node == ground_node || node == "0"
            return "0"
        end
        if !haskey(node_map, node)
            node_map[node] = string(length(node_map) + 1)
        end
        return node_map[node]
    end

    for (name, node1, node2, value) in netlist
        if startswith(name, "K")
            push!(renumbered, (name, node1, node2, value))
        else
            push!(renumbered, (name, to_numeric_node(node1), to_numeric_node(node2), value))
        end
    end

    return renumbered, node_map
end
