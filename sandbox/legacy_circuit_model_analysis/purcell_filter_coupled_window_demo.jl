using Printf
using JosephsonCircuits
using PlotlyJS
using CSV
using DataFrames

include(joinpath(@__DIR__, "Reusable Component", "ReusableComponents.jl"))
using .ReusableComponents

# =============================================================================
# 1. What This Script Represents
# =============================================================================
#
# This is the "current recommended" sandbox authoring style for the circuit:
#
#   Readout Line -> Half-Wave Purcell Filter -> Readout Line
#
# together with one extra:
#
#   one passive Hanging Quarter-Wave Readout Resonator
#
# where one span of the Purcell filter's internal transmission line is coupled
# to one span of the resonator's internal transmission line through the
# coupled-window model.
#
# Compared with the older manual script style, this version intentionally uses:
#
# - high-level reusable COMPONENT objects
# - explicit `connect!` / `apply_series_chain!` authoring
# - `apply_coupled_window!` directly on the components
# - one final lowering step into the flat JosephsonCircuits netlist
#
# The main advantage is that the top-level script no longer has to manually
# invent all intermediate nodes such as:
#
# - `pf_window_left`
# - `pf_window_right`
# - the resonator's internal split nodes near the coupled region
#
# Those details are now managed by the Julia draft layer.

# =============================================================================
# 2. Basic Units
# =============================================================================

const GHz = 1e9
const mm = 1e-3
const fF = 1e-15

# =============================================================================
# 3. Shared CPW RLGC Data
# =============================================================================
#
# We reuse the same uncoupled CPW working point that was already used in the
# earlier sandbox scripts.
#
# All three main distributed structures below are still ordinary RLGC lines:
#
# - left readout line
# - Purcell filter internal line
# - right readout line
#
# The passive quarter-wave resonator also uses the same uncoupled RLGC base
# values.
#
# The coupled-window section will later replace one local span of the Purcell
# filter line and one local span of the resonator line.

common_l_per_m = 4.202913385827e-7
common_c_per_m = 1.681169291339e-10
common_r_per_m = 0.0
common_g_per_m = 0.0

left_readout_spec = RLGCSpec(
    length_m=2.5 * mm,
    n_sections=20,
    l_per_m_h=common_l_per_m,
    c_per_m_f=common_c_per_m,
    r_per_m_ohm=common_r_per_m,
    g_per_m_s=common_g_per_m,
)

purcell_filter_spec = RLGCSpec(
    length_m=10.0 * mm,
    n_sections=48,
    l_per_m_h=common_l_per_m,
    c_per_m_f=common_c_per_m,
    r_per_m_ohm=common_r_per_m,
    g_per_m_s=common_g_per_m,
)

right_readout_spec = RLGCSpec(
    length_m=2.5 * mm,
    n_sections=20,
    l_per_m_h=common_l_per_m,
    c_per_m_f=common_c_per_m,
    r_per_m_ohm=common_r_per_m,
    g_per_m_s=common_g_per_m,
)

quarter_wave_spec = RLGCSpec(
    length_m=5.0 * mm,
    n_sections=25,
    l_per_m_h=common_l_per_m,
    c_per_m_f=common_c_per_m,
    r_per_m_ohm=common_r_per_m,
    g_per_m_s=common_g_per_m,
)

# =============================================================================
# 4. Create the Editable Circuit Draft
# =============================================================================
#
# The draft is the high-level authoring surface.
# At this stage we are still defining components and relationships.
# We have NOT yet generated the final JosephsonCircuits tuple netlist.

draft = CircuitDraft("purcell_filter_coupled_window_demo")

# =============================================================================
# 5. Build the Main Three-Component Chain
# =============================================================================
#
# This is the first major authoring step.
#
# We create three reusable components:
#
# - left readout line
# - half-wave Purcell filter
# - right readout line
#
# Then we connect them in series using:
#
#     apply_series_chain!(draft, left_readout, purcell_filter, right_readout)
#
# This is exactly the kind of "Apply Function" you asked for earlier.
#
# It means:
#
#     left_readout :right -> purcell_filter :left
#     purcell_filter :right -> right_readout :left
#
# without manually writing intermediate node names in the top-level script.

left_readout = add_readout_line_component!(
    draft;
    id="left_readout",
    line_spec=left_readout_spec,
)

purcell_filter = add_half_wave_purcell_filter_component!(
    draft;
    id="purcell_filter",
    left_coupling_cap_f=12.0 * fF,
    right_coupling_cap_f=12.0 * fF,
    line_spec=purcell_filter_spec,
)

right_readout = add_readout_line_component!(
    draft;
    id="right_readout",
    line_spec=right_readout_spec,
)

apply_series_chain!(draft, left_readout, purcell_filter, right_readout)

# =============================================================================
# 6. Expose the Main Chain to the Outside World
# =============================================================================
#
# The three components are now internally wired together, but we still need
# ports at the two ends of the chain.
#
# We therefore connect:
#
# - left readout line :left  -> "input_bus"
# - right readout line :right -> "output_bus"
#
# and then place JosephsonCircuits ports + 50 Ohm shunt terminations there.

connect!(draft, left_readout, :left, "input_bus")
connect!(draft, right_readout, :right, "output_bus")

add_port_with_termination!(draft; port_number=1, node="input_bus", prefix="input")
add_port_with_termination!(draft; port_number=2, node="output_bus", prefix="output")

# =============================================================================
# 7. Add the Passive Hanging Quarter-Wave Resonator
# =============================================================================
#
# In our lab's more common readout picture, the resonator is NOT driven through
# its own dedicated external port.
#
# Instead, it is modeled as:
#
#   internal open end -- quarter-wave distributed line -- short to ground
#
# This is still represented as a reusable COMPONENT object in the draft layer,
# but it has no exposed pins.
#
# The reason we still keep it as a component object is that the top-level script
# can later hand this object directly to `apply_coupled_window!`, which will
# target the resonator's hidden internal transmission line.

qwr = add_hanging_quarter_wave_resonator_component!(
    draft;
    id="qwr",
    line_spec=quarter_wave_spec,
    boundary=:short,
)

# =============================================================================
# 8. Define the Coupled-Window Physics
# =============================================================================
#
# We use `JosephsonCircuits.even_odd_to_mutual(...)` to convert modal data:
#
# - Zeven
# - Zodd
# - neven
# - nodd
#
# into the mutual-form per-unit-length matrices needed by `CoupledWindowSpec`.
#
# The chosen physical spans are:
#
# - Purcell filter internal line:      4.2 mm -> 5.4 mm
# - Quarter-wave resonator internal line: 3.6 mm -> 4.8 mm
#
# Both spans are 1.2 mm long, matching the `length_m` of the coupled-window
# model.

window_mutual = JosephsonCircuits.even_odd_to_mutual(
    56.0,  # Zeven
    44.0,  # Zodd
    2.45,  # neven
    2.60,  # nodd
)

coupled_window_spec = CoupledWindowSpec(
    length_m=1.2 * mm,
    n_sections=6,
    l11_per_m_h=window_mutual.L[1, 1],
    l22_per_m_h=window_mutual.L[2, 2],
    lm_per_m_h=window_mutual.L[1, 2],
    c1g_per_m_f=window_mutual.C[1, 1],
    c2g_per_m_f=window_mutual.C[2, 2],
    cm_per_m_f=window_mutual.C[1, 2],
)

window_section = coupled_window_section_values(coupled_window_spec)

@printf(
    "Coupled window per section: L1=%.3e H, L2=%.3e H, M=%.3e H, k=%.4f, Cg1=%.3e F, Cg2=%.3e F, Cm=%.3e F\n",
    window_section.line_a.l_h,
    window_section.line_b.l_h,
    window_section.lm_h,
    window_section.k,
    window_section.line_a.c_f,
    window_section.line_b.c_f,
    window_section.cm_f,
)

# =============================================================================
# 9. Apply the Coupled Window to Two Existing Components
# =============================================================================
#
# This is the second important "Apply Function" in the draft layer:
#
#     apply_coupled_window!(...)
#
# The key point is that we are NOT passing low-level internal node names here.
# We are passing the COMPONENT objects themselves:
#
# - `purcell_filter`
# - `qwr`
#
# The draft layer internally knows which distributed line belongs to each
# component, and which span on that line should be replaced by the coupled
# window.
#
# Notice that the resonator span is chosen close to the shorted end.
# This matches the physical picture you described: the coupled section sits on
# the ground-side portion of the resonator.

window_placement = apply_coupled_window!(
    draft;
    prefix="pf_qwr_window",
    line_a=purcell_filter,
    span_a=LineSpan(4.2 * mm, 5.4 * mm),
    line_b=qwr,
    span_b=LineSpan(3.6 * mm, 4.8 * mm),
    spec=coupled_window_spec,
)

@printf(
    "Registered coupled window '%s': PF %.3f-%.3f mm <-> QWR %.3f-%.3f mm\n",
    window_placement.id,
    window_placement.span_a.start_m / mm,
    window_placement.span_a.stop_m / mm,
    window_placement.span_b.start_m / mm,
    window_placement.span_b.stop_m / mm,
)

# =============================================================================
# 10. Finalize the Draft into the Flat Simulation Netlist
# =============================================================================
#
# We finalize twice:
#
# 1. symbolic_netlist
#    Keeps symbolic node labels, which makes it easier to inspect what happened.
#
# 2. numeric_netlist
#    Renumbers nodes into "1", "2", "3", ... before simulation.
#
# The physics is the same in both cases. The only difference is readability.

symbolic_netlist = finalize_to_josephson_netlist(draft; renumber_nodes=false)
numeric_netlist = finalize_to_josephson_netlist(draft; renumber_nodes=true)

println()
println("First 12 rows of the symbolic netlist:")
for row in symbolic_netlist[1:min(12, length(symbolic_netlist))]
    println("  ", row)
end

println()
println("First 12 rows of the renumbered netlist:")
for row in numeric_netlist[1:min(12, length(numeric_netlist))]
    println("  ", row)
end

@printf("\nFinal symbolic component count: %d\n", length(symbolic_netlist))

# =============================================================================
# 11. Run the JosephsonCircuits Simulation
# =============================================================================
#
# We inspect two traces:
#
# The whole system is now a pure TWO-PORT network:
#
# - port 1: main input
# - port 2: main output
#
# So the two most useful traces are:
#
# - S21 : through transmission from the main input to the main output
# - S11 : input reflection seen from the main input
#
# The same simulation logic is used as before; only the authoring surface has
# changed.

ws = 2π .* (5.0:0.01:7.0) .* GHz
wp = (2π * 8.001 * GHz,)
sources = [(mode=(1,), port=1, current=0.0)]
Npumpharmonics = (1,)
Nmodulationharmonics = (1,)

solution = hbsolve(
    ws,
    wp,
    sources,
    Nmodulationharmonics,
    Npumpharmonics,
    numeric_netlist,
    Dict{Any,Float64}();
    returnS=true,
    sorting=:name,
)

freqs_GHz = solution.linearized.w ./ (2π .* GHz)

s21 = solution.linearized.S(
    outputmode=(0,),
    outputport=2,
    inputmode=(0,),
    inputport=1,
    freqindex=:,
)

s11 = solution.linearized.S(
    outputmode=(0,),
    outputport=1,
    inputmode=(0,),
    inputport=1,
    freqindex=:,
)

s21_mag = abs.(s21)
s11_mag = abs.(s11)

s21_notch_idx = argmin(s21_mag)
s11_peak_idx = argmax(s11_mag)

@printf(
    "\nDeepest |S21| notch = %.4f at %.3f GHz\n",
    s21_mag[s21_notch_idx],
    freqs_GHz[s21_notch_idx],
)
@printf(
    "Largest |S11| reflection = %.4f at %.3f GHz\n",
    s11_mag[s11_peak_idx],
    freqs_GHz[s11_peak_idx],
)

# =============================================================================
# 12. Save the Simulation Result
# =============================================================================

demo_df = DataFrame(
    frequency_GHz=freqs_GHz,
    S21_real=real.(s21),
    S21_imag=imag.(s21),
    S21_mag=s21_mag,
    S11_real=real.(s11),
    S11_imag=imag.(s11),
    S11_mag=s11_mag,
)

csv_path = joinpath(@__DIR__, "purcell_filter_coupled_window_demo_sparams.csv")
CSV.write(csv_path, demo_df)
println("\nSaved S-parameter data to: $csv_path")

# =============================================================================
# 13. Plot
# =============================================================================

demo_plot = plot(
    [
        scatter(mode="lines", x=freqs_GHz, y=s21_mag, name="|S21|"),
        scatter(mode="lines", x=freqs_GHz, y=s11_mag, name="|S11|"),
    ],
    Layout(
        title="Two-Port PF with Ground-Side Coupled Hanging Quarter-Wave Resonator",
        xaxis=attr(title="Frequency (GHz)"),
        yaxis=attr(title="Magnitude"),
    ),
)

if isinteractive()
    display(demo_plot)
end
