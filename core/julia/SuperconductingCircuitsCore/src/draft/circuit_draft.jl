###############################################################################
# Circuit Draft Layer
###############################################################################
#
# Why this file exists:
# ---------------------
# The low-level JosephsonCircuits netlist is intentionally simple:
#
#     (component_name, node_1, node_2, value)
#
# That format is great for simulation, but it is not a very convenient authoring
# surface once we want to do higher-level transformations such as:
#
# - "Create two transmission lines first"
# - "Later, couple this span on line A to that span on line B"
# - "Only at the very end, lower everything into a flat JosephsonCircuits netlist"
#
# This file adds a thin Julia-side draft layer for sandbox use.
# The layer is deliberately small:
#
# - `CircuitDraft`
#     Stores the "editable" circuit before we flatten it.
#
# - `TransmissionLineInstance`
#     A handle describing one transmission line in the draft.
#
# - `apply_coupled_window!`
#     Records that two spans on two lines should be replaced by a coupled window.
#
# - `finalize_to_josephson_netlist`
#     Performs the actual lowering into a flat netlist that JosephsonCircuits
#     can simulate.
#
# Important design choice:
# ------------------------
# We do NOT try to patch an already-built flat netlist in-place.
# Instead, we keep the editable relationships in the draft, and only generate
# the flat netlist during `finalize_to_josephson_netlist(...)`.
#
# This keeps the code much easier to reason about.
###############################################################################

###############################################################################
# 1. Public Draft Types
###############################################################################

"""
    LineSpan(start_m, stop_m)

Describe one physical span on a transmission line, in meters.

Example:

```julia
LineSpan(0.3e-3, 0.4e-3)
```

means "from 0.3 mm to 0.4 mm along that line".
"""
struct LineSpan
    start_m::Float64
    stop_m::Float64

    function LineSpan(start_m::Real, stop_m::Real)
        start_value = Float64(start_m)
        stop_value = Float64(stop_m)

        start_value >= 0 || _validation_error("LineSpan start_m must be non-negative.")
        stop_value > start_value || _validation_error("LineSpan stop_m must be greater than start_m.")

        return new(start_value, stop_value)
    end
end

"""
    span_length(span)

Return the physical length of the span, in meters.
"""
function span_length(span::LineSpan)
    return span.stop_m - span.start_m
end

"""
    TransmissionLineInstance

This is the editable handle returned by `add_transmission_line!`.

It does not directly contain the final netlist rows.
Instead, it stores the high-level intent needed to generate them later.

Fields:
- `id`
    Stable lookup key inside the draft.
- `prefix`
    Name prefix used later when generating actual component names.
- `start_node`, `end_node`
    External nodes where the line begins and ends.
- `spec`
    The base RLGC description for the uncoupled parts of the line.
- `ground_node`
    Which node should be treated as ground for shunt elements on this line.
- `add_shunt_at_last_node`
    Whether the last node of the line should receive the normal shunt branch.
    For a line shorted directly into ground through its final series element,
    we usually set this to `false`.
"""
struct TransmissionLineInstance
    id::String
    prefix::String
    start_node::String
    end_node::String
    spec::RLGCSpec
    ground_node::String
    add_shunt_at_last_node::Bool
end

"""
    ReadoutLineComponent

High-level two-port component representing one readout transmission line.

Unlike `TransmissionLineInstance`, this type is not intended for section-level
editing such as `apply_coupled_window!`.
Instead, it is meant for clean component-to-component wiring via `connect!`.
"""
struct ReadoutLineComponent
    id::String
    prefix::String
    left_pin::String
    right_pin::String
    line_id::String
    line_spec::RLGCSpec
    ground_node::String
end

"""
    HalfWavePurcellFilterComponent

High-level two-port component representing:

    left pin -- coupling capacitor -- half-wave RLGC line -- coupling capacitor -- right pin

This is the reusable "Purcell filter as a component" form that becomes useful
once we want to connect multiple components together through pins, instead of
manually inventing every intermediate node name in the top-level script.
"""
struct HalfWavePurcellFilterComponent
    id::String
    prefix::String
    left_pin::String
    right_pin::String
    line_id::String
    left_coupling_cap_f::Float64
    right_coupling_cap_f::Float64
    line_spec::RLGCSpec
    ground_node::String
end

"""
    QuarterWaveResonatorComponent

High-level one-port resonator component:

    feed pin -- coupling capacitor -- quarter-wave RLGC line -- open/short boundary

This component is especially useful when we want to:
- connect one side to some external bus or probe port
- still be able to target the internal distributed line with `apply_coupled_window!`
"""
struct QuarterWaveResonatorComponent
    id::String
    prefix::String
    feed_pin::String
    line_id::String
    coupling_cap_f::Float64
    line_spec::RLGCSpec
    boundary::Symbol
    ground_node::String
end

"""
    HangingQuarterWaveResonatorComponent

Passive quarter-wave resonator with no exposed drive/feed pin.

Physical picture:
- one end is left open internally
- the far end is usually shorted to ground
- the resonator is only "seen" by the rest of the system through distributed
  coupling such as a coupled window

This is the closer match to the common superconducting readout situation where
the resonator is not driven through its own dedicated external port.
"""
struct HangingQuarterWaveResonatorComponent
    id::String
    prefix::String
    line_id::String
    line_spec::RLGCSpec
    boundary::Symbol
    ground_node::String
end

"""
    CoupledWindowPlacement

Record one "relationship" inside the editable draft:

- line A, on span A
- line B, on span B
- should be replaced by one coupled-window model

The actual `L / C / K` components are not generated here yet.
They are only generated during finalization.
"""
struct CoupledWindowPlacement
    id::String
    prefix::String
    line_a_id::String
    line_b_id::String
    span_a::LineSpan
    span_b::LineSpan
    spec::CoupledWindowSpec
end

"""
    mutable struct CircuitDraft

Editable circuit container used in the sandbox before flattening to the
JosephsonCircuits tuple netlist.

This draft stores three kinds of information:

1. `lumped_components`
   Plain components such as capacitors, ports, resistors, etc.
2. `transmission_lines`
   High-level transmission-line instances that can later be transformed.
3. `coupled_windows`
   Relationships telling us which spans should become coupled windows.
"""
mutable struct CircuitDraft
    name::String
    ground_node::String
    lumped_components::Vector{Tuple{String,String,String,Any}}
    pin_components::Dict{String,Any}
    component_order::Vector{String}
    transmission_lines::Dict{String,TransmissionLineInstance}
    line_order::Vector{String}
    coupled_windows::Vector{CoupledWindowPlacement}
    node_connections::Vector{Tuple{String,String}}
end

"""
    CircuitDraft(name; ground_node="0")

Create an empty editable draft.
"""
function CircuitDraft(name::AbstractString; ground_node::AbstractString="0")
    isempty(name) && _validation_error("CircuitDraft name must not be empty.")

    return CircuitDraft(
        String(name),
        String(ground_node),
        Tuple{String,String,String,Any}[],
        Dict{String,Any}(),
        String[],
        Dict{String,TransmissionLineInstance}(),
        String[],
        CoupledWindowPlacement[],
        Tuple{String,String}[],
    )
end

###############################################################################
# 2. Small Internal Helper Types
###############################################################################
# These types are internal implementation details used only during finalization.
# They are not the user-facing authoring API.
###############################################################################

"""
    CoupledWindowEndpoints

When we finalize the draft, each coupled window needs to know:
- which node on the left belongs to that line-side window boundary
- which node on the right belongs to that line-side window boundary

We keep that pair in this tiny helper struct.
"""
struct CoupledWindowEndpoints
    left_node::String
    right_node::String
end

"""
    DraftLineChunk

An internal "planned chunk" of one line after all breakpoints have been applied.

Each line gets cut into smaller chunks by:
- the original line start
- the original line end
- every coupled-window start
- every coupled-window end

Each chunk is then classified as either:
- `:uncoupled`
- `:coupled`

For uncoupled chunks, we will emit a normal RLGC ladder.
For coupled chunks, we will remember their boundary nodes and later emit one
`add_coupled_window!` call for the corresponding pair.
"""
struct DraftLineChunk
    kind::Symbol
    line_id::String
    prefix::String
    start_m::Float64
    stop_m::Float64
    left_node::String
    right_node::String
    n_sections::Int
    add_shunt_at_last_node::Bool
    placement_id::String
end

###############################################################################
# 3. Basic Draft Authoring Helpers
###############################################################################

"""
    add_component!(draft; name, node1, node2, value)

Add a plain lumped component directly into the draft.

Use this for things that do not need section-aware editing:
- ports
- coupling capacitors
- 50 Ohm terminations
- simple lumped inductors/capacitors/resistors

This function does NOT immediately "simulate" anything.
It simply records the component in the editable draft.
"""
function add_component!(
    draft::CircuitDraft;
    name::AbstractString,
    node1,
    node2,
    value,
)
    isempty(name) && _validation_error("Component name must not be empty.")

    row = (String(name), string(node1), string(node2), value)
    push!(draft.lumped_components, row)
    return row
end

"""
    add_port_with_termination!(draft; port_number, node, resistance_ohm=50.0, prefix="port")

Convenience helper for the common JosephsonCircuits pattern:

```text
P<n>  node  ground
R     node  ground  50 Ohm
```

This is optional, but it makes the demo scripts easier to read.
"""
function add_port_with_termination!(
    draft::CircuitDraft;
    port_number::Int,
    node,
    resistance_ohm::Real=50.0,
    prefix::AbstractString="port",
)
    port_number > 0 || _validation_error("port_number must be positive.")
    resistance_ohm > 0 || _validation_error("resistance_ohm must be positive.")

    node_name = string(node)
    add_component!(draft; name="P$(port_number)", node1=node_name, node2=draft.ground_node, value=port_number)
    add_component!(
        draft;
        name="R_$(prefix)_$(port_number)",
        node1=node_name,
        node2=draft.ground_node,
        value=Float64(resistance_ohm),
    )

    return node_name
end

###############################################################################
# 3A. Pin and Connection Helpers
###############################################################################
#
# The central idea here is:
#
# - each high-level component owns named pins
# - each pin initially gets its own private symbolic node token
# - `connect!` declares that two pin-tokens should refer to the same net
# - only during finalization do we collapse those aliases into final node labels
#
# This lets us write:
#
#     connect!(draft, left_ro, :right, pf, :left)
#
# instead of manually inventing intermediate node names.
###############################################################################

function _pin_token(component_id::AbstractString, pin::Symbol)
    return "__pin__$(component_id)__$(String(pin))"
end

function _internal_token(component_id::AbstractString, tag::AbstractString)
    return "__internal__$(component_id)__$(tag)"
end

function _is_internal_pin_token(node::AbstractString)
    return startswith(node, "__pin__")
end

function _is_private_internal_token(node::AbstractString)
    return startswith(node, "__pin__") || startswith(node, "__internal__")
end

function _register_pin_component!(draft::CircuitDraft, component)
    component_id = _component_id(component)
    haskey(draft.pin_components, component_id) &&
        _validation_error("Component id '$(component_id)' is already registered in this draft.")

    draft.pin_components[component_id] = component
    push!(draft.component_order, component_id)
    return component
end

function _component_id(component)
    return component.id
end

function pin_node(component::TransmissionLineInstance, pin::Symbol)
    if pin == :left
        return component.start_node
    elseif pin == :right
        return component.end_node
    end
    _validation_error("TransmissionLineInstance supports only :left and :right pins.")
end

function pin_node(component::ReadoutLineComponent, pin::Symbol)
    if pin == :left
        return component.left_pin
    elseif pin == :right
        return component.right_pin
    end
    _validation_error("ReadoutLineComponent supports only :left and :right pins.")
end

function pin_node(component::HalfWavePurcellFilterComponent, pin::Symbol)
    if pin == :left
        return component.left_pin
    elseif pin == :right
        return component.right_pin
    end
    _validation_error("HalfWavePurcellFilterComponent supports only :left and :right pins.")
end

function pin_node(component::QuarterWaveResonatorComponent, pin::Symbol)
    if pin == :feed
        return component.feed_pin
    end
    _validation_error("QuarterWaveResonatorComponent supports only the :feed pin.")
end

function pin_node(component::HangingQuarterWaveResonatorComponent, pin::Symbol)
    _validation_error(
        "HangingQuarterWaveResonatorComponent does not expose any external pins. " *
        "It should only participate through apply_coupled_window! on its internal line."
    )
end

function _resolve_pin_component(draft::CircuitDraft, component_ref)
    if component_ref isa AbstractString
        component = get(draft.pin_components, String(component_ref), nothing)
        component === nothing && _validation_error("Unknown component id '$(component_ref)'.")
        return component
    end

    component_id = _component_id(component_ref)
    registered = get(draft.pin_components, component_id, nothing)
    registered === nothing &&
        _validation_error("Component '$(component_id)' is not registered in this draft.")
    return registered
end

"""
    connect!(draft, component_a, pin_a, component_b, pin_b)

Declare that two component pins should share one electrical node.

The connection is recorded symbolically in the draft first.
Actual node collapsing happens during finalization.
"""
function connect!(
    draft::CircuitDraft,
    component_a,
    pin_a::Symbol,
    component_b,
    pin_b::Symbol,
)
    resolved_a = _resolve_pin_component(draft, component_a)
    resolved_b = _resolve_pin_component(draft, component_b)

    node_a = pin_node(resolved_a, pin_a)
    node_b = pin_node(resolved_b, pin_b)

    push!(draft.node_connections, (node_a, node_b))
    return (node_a=node_a, node_b=node_b)
end

"""
    connect!(draft, component, pin, external_node)

Connect one component pin to a named external node.

This is useful for attaching ports, buses, or any other top-level net name.
"""
function connect!(
    draft::CircuitDraft,
    component,
    pin::Symbol,
    external_node::AbstractString,
)
    resolved_component = _resolve_pin_component(draft, component)
    node = pin_node(resolved_component, pin)
    push!(draft.node_connections, (node, String(external_node)))
    return (node=node, external_node=String(external_node))
end

"""
    apply_series_chain!(draft, components...)

Convenience "apply function" for the most common topology:

    component_1 -- component_2 -- component_3 -- ...

It simply connects:

    previous :right  ->  next :left

This is the authoring helper that makes a chain such as:

    Readout Line - Half-Wave Purcell Filter - Readout Line

feel natural to write.
"""
function apply_series_chain!(draft::CircuitDraft, components...)
    length(components) >= 2 ||
        _validation_error("apply_series_chain! requires at least two components.")

    connections = Any[]
    for idx in 1:(length(components) - 1)
        push!(connections, connect!(draft, components[idx], :right, components[idx + 1], :left))
    end
    return connections
end

"""
    add_readout_line_component!(draft; ...)

Create a reusable two-port readout-line component with symbolic pins.

The returned component can participate in:
- `connect!`
- `apply_series_chain!`

At finalize time it lowers to the existing `add_readout_line!` ladder builder.
"""
function add_readout_line_component!(
    draft::CircuitDraft;
    id::AbstractString,
    line_spec::RLGCSpec,
    prefix::AbstractString=String(id),
    ground_node::AbstractString=draft.ground_node,
)
    line_id = "$(String(id))__line"
    component = ReadoutLineComponent(
        String(id),
        String(prefix),
        _pin_token(id, :left),
        _pin_token(id, :right),
        line_id,
        line_spec,
        String(ground_node),
    )

    _register_pin_component!(draft, component)
    _register_internal_transmission_line!(
        draft;
        id=line_id,
        prefix=component.prefix,
        start_node=component.left_pin,
        end_node=component.right_pin,
        spec=component.line_spec,
        ground_node=component.ground_node,
        add_shunt_at_last_node=false,
    )
    return component
end

"""
    add_half_wave_purcell_filter_component!(draft; ...)

Create a reusable two-port Purcell-filter component with symbolic pins.

The caller only needs to think about:
- the component identity
- the left/right pins
- the coupling capacitor values
- the line spec

The internal nodes remain hidden inside the component and are generated only
when the draft is finalized.
"""
function add_half_wave_purcell_filter_component!(
    draft::CircuitDraft;
    id::AbstractString,
    left_coupling_cap_f::Real,
    right_coupling_cap_f::Real,
    line_spec::RLGCSpec,
    prefix::AbstractString=String(id),
    ground_node::AbstractString=draft.ground_node,
)
    left_coupling_cap_f > 0 || _validation_error("left_coupling_cap_f must be positive.")
    right_coupling_cap_f > 0 || _validation_error("right_coupling_cap_f must be positive.")
    line_id = "$(String(id))__line"
    internal_left_node = _internal_token(id, "line_left")
    internal_right_node = _internal_token(id, "line_right")

    component = HalfWavePurcellFilterComponent(
        String(id),
        String(prefix),
        _pin_token(id, :left),
        _pin_token(id, :right),
        line_id,
        Float64(left_coupling_cap_f),
        Float64(right_coupling_cap_f),
        line_spec,
        String(ground_node),
    )

    _register_pin_component!(draft, component)

    add_component!(
        draft;
        name=_component_name("C", component.prefix, "in"),
        node1=component.left_pin,
        node2=internal_left_node,
        value=component.left_coupling_cap_f,
    )
    add_component!(
        draft;
        name=_component_name("C", component.prefix, "out"),
        node1=internal_right_node,
        node2=component.right_pin,
        value=component.right_coupling_cap_f,
    )

    _register_internal_transmission_line!(
        draft;
        id=line_id,
        prefix=component.prefix,
        start_node=internal_left_node,
        end_node=internal_right_node,
        spec=component.line_spec,
        ground_node=component.ground_node,
    )

    return component
end

"""
    add_quarter_wave_resonator_component!(draft; ...)

Create a one-port quarter-wave resonator component whose internal distributed
line can still be targeted by `apply_coupled_window!`.
"""
function add_quarter_wave_resonator_component!(
    draft::CircuitDraft;
    id::AbstractString,
    coupling_cap_f::Real,
    line_spec::RLGCSpec,
    boundary::Symbol=:short,
    prefix::AbstractString=String(id),
    ground_node::AbstractString=draft.ground_node,
)
    coupling_cap_f > 0 || _validation_error("coupling_cap_f must be positive.")
    boundary in (:open, :short) || _validation_error("boundary must be :open or :short.")

    line_id = "$(String(id))__line"
    internal_feed_node = _internal_token(id, "line_feed")
    internal_end_node = boundary == :short ? String(ground_node) : _internal_token(id, "line_end")

    component = QuarterWaveResonatorComponent(
        String(id),
        String(prefix),
        _pin_token(id, :feed),
        line_id,
        Float64(coupling_cap_f),
        line_spec,
        boundary,
        String(ground_node),
    )

    _register_pin_component!(draft, component)

    add_component!(
        draft;
        name=_component_name("C", component.prefix, "coupling"),
        node1=component.feed_pin,
        node2=internal_feed_node,
        value=component.coupling_cap_f,
    )

    _register_internal_transmission_line!(
        draft;
        id=line_id,
        prefix=component.prefix,
        start_node=internal_feed_node,
        end_node=internal_end_node,
        spec=component.line_spec,
        ground_node=component.ground_node,
        add_shunt_at_last_node=boundary == :short ? false : true,
    )

    return component
end

"""
    add_hanging_quarter_wave_resonator_component!(draft; ...)

Create a passive quarter-wave resonator component with NO externally exposed
drive pin.

This matches the common superconducting-readout situation where the resonator
is not fed through its own probe line. Instead:

- one end of the resonator is left open internally
- the far end is usually shorted to ground
- the resonator only interacts with the rest of the circuit through a local
  distributed coupling mechanism such as `apply_coupled_window!`

Why keep this as a COMPONENT if it has no pins?
-----------------------------------------------
Because we still want a stable object handle that the top-level script can:

- name
- store
- pass into `apply_coupled_window!`

without manually tracking the hidden internal transmission-line id.
"""
function add_hanging_quarter_wave_resonator_component!(
    draft::CircuitDraft;
    id::AbstractString,
    line_spec::RLGCSpec,
    boundary::Symbol=:short,
    prefix::AbstractString=String(id),
    ground_node::AbstractString=draft.ground_node,
)
    boundary in (:open, :short) || _validation_error("boundary must be :open or :short.")

    line_id = "$(String(id))__line"

    # The left side of this resonator is intentionally left floating.
    #
    # That floating node is private to the component. No top-level `connect!`
    # call should ever target it.
    internal_open_node = _internal_token(id, "line_open")

    # The right side follows the same boundary convention as the existing
    # one-port resonator:
    #
    # - `:short` -> the line ends directly at ground
    # - `:open`  -> the line ends at a private floating node
    internal_end_node = boundary == :short ? String(ground_node) : _internal_token(id, "line_end")

    component = HangingQuarterWaveResonatorComponent(
        String(id),
        String(prefix),
        line_id,
        line_spec,
        boundary,
        String(ground_node),
    )

    _register_pin_component!(draft, component)

    _register_internal_transmission_line!(
        draft;
        id=line_id,
        prefix=component.prefix,
        start_node=internal_open_node,
        end_node=internal_end_node,
        spec=component.line_spec,
        ground_node=component.ground_node,
        add_shunt_at_last_node=boundary == :short ? false : true,
    )

    return component
end

function _register_internal_transmission_line!(
    draft::CircuitDraft;
    id::AbstractString,
    start_node,
    end_node,
    spec::RLGCSpec,
    prefix::AbstractString=String(id),
    ground_node::AbstractString=draft.ground_node,
    add_shunt_at_last_node::Bool=true,
)
    line_id = String(id)
    haskey(draft.transmission_lines, line_id) &&
        _validation_error("Internal transmission line id '$(line_id)' is already registered.")

    line = TransmissionLineInstance(
        line_id,
        String(prefix),
        string(start_node),
        string(end_node),
        spec,
        String(ground_node),
        add_shunt_at_last_node,
    )

    draft.transmission_lines[line.id] = line
    push!(draft.line_order, line.id)
    return line
end

"""
    add_transmission_line!(draft; ...)

Register one editable transmission line inside the draft.

At this stage we only store the line as a high-level object.
We do NOT immediately lower it into many `L` and `C` rows.

That delayed-lowering design is the whole point of this draft layer:
it lets us later apply transformations like `apply_coupled_window!`.
"""
function add_transmission_line!(
    draft::CircuitDraft;
    id::AbstractString,
    start_node,
    end_node,
    spec::RLGCSpec,
    prefix::AbstractString=String(id),
    ground_node::AbstractString=draft.ground_node,
    add_shunt_at_last_node::Bool=true,
)
    line_id = String(id)
    haskey(draft.pin_components, line_id) &&
        _validation_error("Component id '$(line_id)' is already registered in this draft.")
    haskey(draft.transmission_lines, line_id) &&
        _validation_error("Transmission line id '$(line_id)' is already registered in this draft.")

    line = TransmissionLineInstance(
        line_id,
        String(prefix),
        string(start_node),
        string(end_node),
        spec,
        String(ground_node),
        add_shunt_at_last_node,
    )

    draft.pin_components[line.id] = line
    push!(draft.component_order, line.id)
    _register_internal_transmission_line!(
        draft;
        id=line.id,
        prefix=line.prefix,
        start_node=line.start_node,
        end_node=line.end_node,
        spec=line.spec,
        ground_node=line.ground_node,
        add_shunt_at_last_node=line.add_shunt_at_last_node,
    )
    return line
end

###############################################################################
# 4. Coupled-Window Registration
###############################################################################

"""
    apply_coupled_window!(draft; ...)

Register the intent:

- line A span `span_a`
- line B span `span_b`
- should become one coupled window using `spec`

No flat netlist rows are generated yet.
We only record the relationship here.

This separation is the key idea of the draft layer:
- author/edit first
- flatten later
"""
function apply_coupled_window!(
    draft::CircuitDraft;
    prefix::AbstractString,
    line_a,
    span_a::LineSpan,
    line_b,
    span_b::LineSpan,
    spec::CoupledWindowSpec,
)
    placement_id = String(prefix)
    any(window -> window.id == placement_id, draft.coupled_windows) &&
        _validation_error("Coupled window id '$(placement_id)' is already in use.")

    line_a_instance = _resolve_line_instance(draft, line_a)
    line_b_instance = _resolve_line_instance(draft, line_b)

    line_a_instance.id != line_b_instance.id ||
        _validation_error("A coupled window must connect two different transmission lines.")

    _validate_span_within_line(span_a, line_a_instance)
    _validate_span_within_line(span_b, line_b_instance)

    span_length(span_a) ≈ span_length(span_b) ||
        _validation_error("Coupled spans on line A and line B must have the same physical length.")

    span_length(span_a) ≈ spec.length_m ||
        _validation_error("Coupled-window spec length_m must match the requested span length.")

    _validate_no_overlap_with_existing_windows(draft, line_a_instance.id, span_a)
    _validate_no_overlap_with_existing_windows(draft, line_b_instance.id, span_b)

    placement = CoupledWindowPlacement(
        placement_id,
        placement_id,
        line_a_instance.id,
        line_b_instance.id,
        span_a,
        span_b,
        spec,
    )

    push!(draft.coupled_windows, placement)
    return placement
end

###############################################################################
# 5. Finalization API
###############################################################################

"""
    finalize_to_josephson_netlist(draft; renumber_nodes=false)

Lower the editable draft into the flat tuple netlist expected by
JosephsonCircuits.

This function is intentionally split into clear stages:

1. Copy plain lumped components.
2. For each transmission line, compute all breakpoints.
3. Cut the line into chunks.
4. Emit uncoupled chunks immediately.
5. Emit coupled windows using the boundary nodes recorded in step 3.
6. Optionally renumber symbolic node labels into numeric strings.

The optional `renumber_nodes=true` step is useful if you want the final netlist
to look more like a traditional simulator input with numeric node labels.
"""
function finalize_to_josephson_netlist(
    draft::CircuitDraft;
    renumber_nodes::Bool=false,
)
    # -------------------------------------------------------------------------
    # Stage 0: Resolve all symbolic pin connections into final draft-level nets.
    # -------------------------------------------------------------------------
    # This is the new piece that makes `connect!` meaningful.
    #
    # Before we emit any components, we first collapse all of the declared
    # pin-to-pin and pin-to-external connections into final symbolic node names.
    resolve_node = _build_node_resolver(draft)

    # -------------------------------------------------------------------------
    # Stage 1: Start from the plain lumped components.
    # -------------------------------------------------------------------------
    # These components already have their final identity, so we can copy them
    # straight into the flattened netlist.
    flat_netlist = Tuple{String,String,String,Any}[]
    for (name, node1, node2, value) in draft.lumped_components
        push!(flat_netlist, (name, resolve_node(node1), resolve_node(node2), value))
    end

    # -------------------------------------------------------------------------
    # Stage 1A: High-level components do not emit anything directly here.
    # -------------------------------------------------------------------------
    # Why?
    # High-level components such as:
    #
    # - ReadoutLineComponent
    # - HalfWavePurcellFilterComponent
    # - QuarterWaveResonatorComponent
    # - HangingQuarterWaveResonatorComponent
    #
    # are now "composition shells":
    #
    # - their pins participate in `connect!`
    # - their internal lumped elements have already been registered
    # - their internal transmission lines live in `draft.transmission_lines`
    #
    # Therefore the real physical content is emitted in the normal lumped/line
    # stages, and the component objects themselves act as authoring handles.

    # -------------------------------------------------------------------------
    # Stage 2: Plan every transmission line chunk.
    # -------------------------------------------------------------------------
    # Each line is broken wherever a coupled window starts or stops.
    # Uncoupled chunks are emitted immediately.
    # Coupled chunks are not emitted yet; we only remember their boundary nodes.
    placement_endpoints = Dict{String, Dict{String,CoupledWindowEndpoints}}()

    for line_id in draft.line_order
        original_line = draft.transmission_lines[line_id]
        resolved_line = _resolved_transmission_line(original_line, resolve_node)
        breakpoints = _collect_line_breakpoints(draft, resolved_line)
        boundary_nodes = _build_boundary_nodes(resolved_line, breakpoints)
        chunks = _build_line_chunks(draft, resolved_line, breakpoints, boundary_nodes)

        for chunk in chunks
            if chunk.kind == :uncoupled
                _emit_uncoupled_chunk!(flat_netlist, resolved_line, chunk)
            elseif chunk.kind == :coupled
                endpoints_by_line = get!(
                    placement_endpoints,
                    chunk.placement_id,
                    Dict{String,CoupledWindowEndpoints}(),
                )
                endpoints_by_line[resolved_line.id] = CoupledWindowEndpoints(chunk.left_node, chunk.right_node)
            else
                _validation_error("Unknown chunk kind '$(chunk.kind)'.")
            end
        end
    end

    # -------------------------------------------------------------------------
    # Stage 3: Emit the actual coupled-window ladders.
    # -------------------------------------------------------------------------
    # By this point, both participating lines have already established the
    # boundary nodes where the coupled window should attach.
    for placement in draft.coupled_windows
        endpoints_by_line = get(placement_endpoints, placement.id, nothing)
        endpoints_by_line === nothing &&
            _validation_error("Internal error: missing endpoints for coupled window '$(placement.id)'.")

        endpoints_a = get(endpoints_by_line, placement.line_a_id, nothing)
        endpoints_b = get(endpoints_by_line, placement.line_b_id, nothing)

        endpoints_a === nothing &&
            _validation_error("Internal error: missing line-A endpoints for coupled window '$(placement.id)'.")
        endpoints_b === nothing &&
            _validation_error("Internal error: missing line-B endpoints for coupled window '$(placement.id)'.")

        add_coupled_window!(
            flat_netlist;
            prefix=placement.prefix,
            left_node_a=endpoints_a.left_node,
            right_node_a=endpoints_a.right_node,
            left_node_b=endpoints_b.left_node,
            right_node_b=endpoints_b.right_node,
            spec=placement.spec,
            ground_node=draft.ground_node,
        )
    end

    # -------------------------------------------------------------------------
    # Stage 4: Optional node renumbering.
    # -------------------------------------------------------------------------
    # JosephsonCircuits already accepts symbolic node labels, so this step is
    # optional. We keep it here because it mirrors the "final lowering" idea:
    # symbolic draft nodes first, numeric simulation nodes last.
    if renumber_nodes
        return _renumber_netlist_nodes(flat_netlist; ground_node=draft.ground_node)
    end

    return flat_netlist
end

###############################################################################
# 6. Internal Validation Helpers
###############################################################################

function _resolve_line_instance(draft::CircuitDraft, line_ref)
    if line_ref isa TransmissionLineInstance
        line_id = line_ref.id
    elseif line_ref isa ReadoutLineComponent
        line_id = line_ref.line_id
    elseif line_ref isa HalfWavePurcellFilterComponent
        line_id = line_ref.line_id
    elseif line_ref isa QuarterWaveResonatorComponent
        line_id = line_ref.line_id
    elseif line_ref isa HangingQuarterWaveResonatorComponent
        line_id = line_ref.line_id
    elseif line_ref isa AbstractString
        line_id = String(line_ref)
    else
        _validation_error(
            "Line reference must be a TransmissionLineInstance, a line-backed component, " *
            "or a line id string."
        )
    end

    line = get(draft.transmission_lines, line_id, nothing)
    line === nothing && _validation_error("Unknown transmission line id '$(line_id)'.")
    return line
end

function _component_pin_tokens(component::TransmissionLineInstance)
    return (component.start_node, component.end_node)
end

function _component_pin_tokens(component::ReadoutLineComponent)
    return (component.left_pin, component.right_pin)
end

function _component_pin_tokens(component::HalfWavePurcellFilterComponent)
    return (component.left_pin, component.right_pin)
end

function _component_pin_tokens(component::QuarterWaveResonatorComponent)
    return (component.feed_pin,)
end

function _component_pin_tokens(component::HangingQuarterWaveResonatorComponent)
    return ()
end

function _validate_span_within_line(span::LineSpan, line::TransmissionLineInstance)
    span.stop_m <= line.spec.length_m ||
        _validation_error(
            "Requested span $(span.start_m) to $(span.stop_m) m exceeds the line " *
            "'$(line.id)' length $(line.spec.length_m) m."
        )
end

function _spans_overlap(span_a::LineSpan, span_b::LineSpan)
    return min(span_a.stop_m, span_b.stop_m) > max(span_a.start_m, span_b.start_m)
end

function _validate_no_overlap_with_existing_windows(
    draft::CircuitDraft,
    line_id::AbstractString,
    new_span::LineSpan,
)
    for placement in draft.coupled_windows
        span = _span_for_line(placement, String(line_id))
        isnothing(span) && continue

        _spans_overlap(new_span, span) &&
            _validation_error(
                "The requested coupled-window span overlaps an existing window on " *
                "line '$(line_id)'. Overlapping windows on the same line are not " *
                "supported by this draft skeleton."
            )
    end
end

function _span_for_line(placement::CoupledWindowPlacement, line_id::AbstractString)
    if placement.line_a_id == line_id
        return placement.span_a
    elseif placement.line_b_id == line_id
        return placement.span_b
    end
    return nothing
end

###############################################################################
# 6A. Node-Resolution Helpers for `connect!`
###############################################################################
#
# `connect!` only records symbolic relationships.
# The functions below collapse those relationships into final node labels.
###############################################################################

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

    # Register every pin token up front, even if the caller never explicitly
    # connects it. This guarantees every pin belongs to some node group.
    for component in values(draft.pin_components)
        for token in _component_pin_tokens(component)
            ensure_node!(token)
        end
    end

    # Apply all explicit `connect!` relationships.
    for (node_a, node_b) in draft.node_connections
        union_nodes!(node_a, node_b)
    end

    # Group members by their union-find root.
    members_by_root = Dict{String,Vector{String}}()
    for node in keys(parent)
        root = find_root(node)
        push!(get!(members_by_root, root, String[]), node)
    end

    # Choose one final symbolic label for each node group.
    #
    # Preference order:
    # 1. Any explicit external node name
    # 2. Auto-generated `net_<n>` if the group only contains private pin tokens
    labels_by_root = Dict{String,String}()
    auto_net_index = 1

    for root in sort(collect(keys(members_by_root)))
        members = sort(members_by_root[root])
        external_names = filter(node -> !_is_private_internal_token(node), members)

        if !isempty(external_names)
            labels_by_root[root] = external_names[1]
        else
            labels_by_root[root] = "net_$(auto_net_index)"
            auto_net_index += 1
        end
    end

    return node -> begin
        node_string = string(node)
        if !haskey(parent, node_string)
            return node_string
        end
        return labels_by_root[find_root(node_string)]
    end
end

function _resolved_transmission_line(line::TransmissionLineInstance, resolve_node)
    return TransmissionLineInstance(
        line.id,
        line.prefix,
        resolve_node(line.start_node),
        resolve_node(line.end_node),
        line.spec,
        line.ground_node,
        line.add_shunt_at_last_node,
    )
end

###############################################################################
# 7. Internal Chunk Planning Helpers
###############################################################################

"""
    _collect_line_breakpoints(draft, line)

Return all x-positions where this line must be split.

The breakpoints always include:
- 0
- line total length
- every coupled-window start on this line
- every coupled-window stop on this line
"""
function _collect_line_breakpoints(draft::CircuitDraft, line::TransmissionLineInstance)
    breakpoints = Float64[0.0, line.spec.length_m]

    for placement in draft.coupled_windows
        span = _span_for_line(placement, line.id)
        isnothing(span) && continue
        _push_unique_breakpoint!(breakpoints, span.start_m)
        _push_unique_breakpoint!(breakpoints, span.stop_m)
    end

    sort!(breakpoints)
    return breakpoints
end

function _push_unique_breakpoint!(breakpoints::Vector{Float64}, value::Float64)
    any(existing -> isapprox(existing, value), breakpoints) || push!(breakpoints, value)
    return breakpoints
end

"""
    _build_boundary_nodes(line, breakpoints)

Assign concrete node names to every breakpoint on one line.

Example:
- first breakpoint -> original line start node
- last breakpoint  -> original line end node
- internal breakpoint -> autogenerated split node
"""
function _build_boundary_nodes(
    line::TransmissionLineInstance,
    breakpoints::Vector{Float64},
)
    boundary_nodes = String[]

    for idx in eachindex(breakpoints)
        if idx == 1
            push!(boundary_nodes, line.start_node)
        elseif idx == length(breakpoints)
            push!(boundary_nodes, line.end_node)
        else
            push!(boundary_nodes, "$(line.prefix)_boundary$(idx - 1)")
        end
    end

    return boundary_nodes
end

"""
    _build_line_chunks(...)

Convert one line into ordered chunks between adjacent breakpoints.

Each chunk is classified as:
- `:uncoupled`
- `:coupled`

For uncoupled chunks we also assign an approximate section count.

Why "approximate"?
------------------
Once we start cutting and replacing parts of the line, the original section grid
no longer needs to remain exact. In this skeleton we keep the line density
roughly similar by reusing the original section density:

    original_sections / original_length

This keeps the code simple and makes authoring far easier.
"""
function _build_line_chunks(
    draft::CircuitDraft,
    line::TransmissionLineInstance,
    breakpoints::Vector{Float64},
    boundary_nodes::Vector{String},
)
    chunks = DraftLineChunk[]

    for idx in 1:(length(breakpoints) - 1)
        start_m = breakpoints[idx]
        stop_m = breakpoints[idx + 1]
        left_node = boundary_nodes[idx]
        right_node = boundary_nodes[idx + 1]

        placement = _matching_window_for_interval(draft, line.id, start_m, stop_m)

        if isnothing(placement)
            chunk = DraftLineChunk(
                :uncoupled,
                line.id,
                "$(line.prefix)_chunk$(idx)",
                start_m,
                stop_m,
                left_node,
                right_node,
                _approximate_section_count(line.spec, stop_m - start_m),
                idx == (length(breakpoints) - 1) ? line.add_shunt_at_last_node : true,
                "",
            )
            push!(chunks, chunk)
        else
            chunk = DraftLineChunk(
                :coupled,
                line.id,
                placement.prefix,
                start_m,
                stop_m,
                left_node,
                right_node,
                placement.spec.n_sections,
                true,
                placement.id,
            )
            push!(chunks, chunk)
        end
    end

    return chunks
end

function _matching_window_for_interval(
    draft::CircuitDraft,
    line_id::AbstractString,
    start_m::Float64,
    stop_m::Float64,
)
    matches = CoupledWindowPlacement[]

    for placement in draft.coupled_windows
        span = _span_for_line(placement, line_id)
        isnothing(span) && continue

        if isapprox(span.start_m, start_m) && isapprox(span.stop_m, stop_m)
            push!(matches, placement)
        end
    end

    length(matches) <= 1 ||
        _validation_error(
            "Internal error: more than one coupled window matched the same interval " *
            "on line '$(line_id)'."
        )

    return isempty(matches) ? nothing : matches[1]
end

function _approximate_section_count(spec::RLGCSpec, chunk_length_m::Float64)
    chunk_length_m > 0 || _validation_error("Chunk length must be positive.")

    section_density = spec.n_sections / spec.length_m
    return max(1, round(Int, section_density * chunk_length_m))
end

###############################################################################
# 8. Internal Netlist Emission Helpers
###############################################################################

"""
    _emit_uncoupled_chunk!(flat_netlist, line, chunk)

Turn one uncoupled planned chunk back into a normal RLGC ladder.
"""
function _emit_uncoupled_chunk!(
    flat_netlist::Vector{Tuple{String,String,String,Any}},
    line::TransmissionLineInstance,
    chunk::DraftLineChunk,
)
    chunk_spec = RLGCSpec(
        length_m=chunk.stop_m - chunk.start_m,
        n_sections=chunk.n_sections,
        l_per_m_h=line.spec.l_per_m_h,
        c_per_m_f=line.spec.c_per_m_f,
        r_per_m_ohm=line.spec.r_per_m_ohm,
        g_per_m_s=line.spec.g_per_m_s,
    )

    add_distributed_segment!(
        flat_netlist;
        prefix=chunk.prefix,
        start_node=chunk.left_node,
        spec=chunk_spec,
        ground_node=line.ground_node,
        final_node=chunk.right_node,
        add_shunt_at_last_node=chunk.add_shunt_at_last_node,
    )

    return flat_netlist
end

###############################################################################
# 9. Optional Numeric Node Lowering
###############################################################################

"""
    _renumber_netlist_nodes(flat_netlist; ground_node="0")

Convert symbolic node names into numeric node labels:

```text
left_bus  -> "1"
pf_mid    -> "2"
...
```

Important exception:
--------------------
JosephsonCircuits `K` rows do not use node names in their second and third
tuple positions. They use the names of the two inductor components being
coupled. Therefore we must leave those entries unchanged.
"""
function _renumber_netlist_nodes(
    flat_netlist::Vector{Tuple{String,String,String,Any}};
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

    for (name, node1, node2, value) in flat_netlist
        if startswith(name, "K")
            push!(renumbered, (name, node1, node2, value))
        else
            push!(renumbered, (name, to_numeric_node(node1), to_numeric_node(node2), value))
        end
    end

    return renumbered
end
