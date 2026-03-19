using Printf
using JosephsonCircuits
using CSV
using DataFrames

include(joinpath(@__DIR__, "Reusable Component", "ReusableComponents.jl"))
using .ReusableComponents

# =============================================================================
# 1. Purpose of This Demo
# =============================================================================
#
# This script is a teaching-oriented example for the new Julia draft layer.
#
# The workflow shown here is exactly the authoring style we want:
#
# 1. Create an editable `CircuitDraft`
# 2. Register plain lumped components such as ports and 50 Ohm terminations
# 3. Register two transmission-line instances
# 4. Declare that one span on line A should be coupled to another span on line B
# 5. Finalize the draft into a JosephsonCircuits-compatible flat netlist
# 6. Run a simulation
#
# The key point is that the coupled-window relationship is declared AFTER the
# two transmission lines already exist.
# We are no longer forced to manually split the lines into pre/window/post
# segments in the top-level script.

# =============================================================================
# 2. Basic Unit Constants
# =============================================================================

const GHz = 1e9
const mm = 1e-3

# =============================================================================
# 3. Base RLGC Data for the Two Uncoupled Lines
# =============================================================================
#
# For this demo, both lines use the same per-unit-length RLGC values.
# Only their total lengths differ.
#
# Line A total length: 1.0 mm
# Line B total length: 2.0 mm
#
# The draft layer does not care that they have different total lengths.
# It only needs each line's own base RLGC description plus the spans that will
# later be coupled.

common_l_per_m = 4.202913385827e-7
common_c_per_m = 1.681169291339e-10
common_r_per_m = 0.0
common_g_per_m = 0.0

line_a_spec = RLGCSpec(
    length_m=1.0 * mm,
    n_sections=40,
    l_per_m_h=common_l_per_m,
    c_per_m_f=common_c_per_m,
    r_per_m_ohm=common_r_per_m,
    g_per_m_s=common_g_per_m,
)

line_b_spec = RLGCSpec(
    length_m=2.0 * mm,
    n_sections=80,
    l_per_m_h=common_l_per_m,
    c_per_m_f=common_c_per_m,
    r_per_m_ohm=common_r_per_m,
    g_per_m_s=common_g_per_m,
)

# =============================================================================
# 4. Create the Editable Draft
# =============================================================================
#
# At this point nothing has been lowered into a flat JosephsonCircuits netlist.
# We are still in the "editable authoring" phase.

draft = CircuitDraft("offset_coupled_two_line_demo")

# =============================================================================
# 5. Add Ports and 50 Ohm Terminations
# =============================================================================
#
# We create a standard 4-port environment:
#
#   port 1 -> left side of line A
#   port 2 -> right side of line A
#   port 3 -> left side of line B
#   port 4 -> right side of line B
#
# Each port node also gets a 50 Ohm shunt resistor to ground.

line_a_left = add_port_with_termination!(draft; port_number=1, node="line_a_left", prefix="line_a")
line_a_right = add_port_with_termination!(draft; port_number=2, node="line_a_right", prefix="line_a")
line_b_left = add_port_with_termination!(draft; port_number=3, node="line_b_left", prefix="line_b")
line_b_right = add_port_with_termination!(draft; port_number=4, node="line_b_right", prefix="line_b")

# =============================================================================
# 6. Register the Two Transmission Lines
# =============================================================================
#
# This is the first place where the new draft layer matters.
#
# We are NOT generating all of the line's `L/C` ladder elements yet.
# We are only registering two editable transmission-line instances.
#
# Later, `apply_coupled_window!` will refer back to these instances.

line_a = add_transmission_line!(
    draft;
    id="line_a",
    prefix="line_a",
    start_node=line_a_left,
    end_node=line_a_right,
    spec=line_a_spec,
)

line_b = add_transmission_line!(
    draft;
    id="line_b",
    prefix="line_b",
    start_node=line_b_left,
    end_node=line_b_right,
    spec=line_b_spec,
)

# =============================================================================
# 7. Define the Coupled-Window Physics
# =============================================================================
#
# We use `JosephsonCircuits.even_odd_to_mutual(...)` to convert even/odd modal
# data into the mutual-form per-unit-length quantities expected by
# `CoupledWindowSpec`.
#
# This is usually the most convenient bridge from EM / calculator data to the
# ladder model we actually simulate.

window_spec_from_modes = JosephsonCircuits.even_odd_to_mutual(
    56.0,  # Zeven
    44.0,  # Zodd
    2.45,  # neven
    2.60,  # nodd
)

window_spec = CoupledWindowSpec(
    length_m=0.1 * mm,
    n_sections=8,
    l11_per_m_h=window_spec_from_modes.L[1, 1],
    l22_per_m_h=window_spec_from_modes.L[2, 2],
    lm_per_m_h=window_spec_from_modes.L[1, 2],
    c1g_per_m_f=window_spec_from_modes.C[1, 1],
    c2g_per_m_f=window_spec_from_modes.C[2, 2],
    cm_per_m_f=window_spec_from_modes.C[1, 2],
)

window_section_values = coupled_window_section_values(window_spec)

@printf(
    "Per coupled-window section: L1=%.3e H, L2=%.3e H, M=%.3e H, k=%.4f, Cm=%.3e F\n",
    window_section_values.line_a.l_h,
    window_section_values.line_b.l_h,
    window_section_values.lm_h,
    window_section_values.k,
    window_section_values.cm_f,
)

# =============================================================================
# 8. Apply One Offset Coupled Window
# =============================================================================
#
# This is the authoring pattern we wanted:
#
# - line A already exists
# - line B already exists
# - now we declare that:
#       line A, from 0.3 mm to 0.4 mm
#   should couple to:
#       line B, from 0.7 mm to 0.8 mm
#
# The draft records this as a relationship.
# The actual ladder replacement happens only during finalization.

window = apply_coupled_window!(
    draft;
    prefix="offset_window",
    line_a=line_a,
    span_a=LineSpan(0.3 * mm, 0.4 * mm),
    line_b=line_b,
    span_b=LineSpan(0.7 * mm, 0.8 * mm),
    spec=window_spec,
)

@printf(
    "Registered coupled window '%s': line A %.3f-%.3f mm <-> line B %.3f-%.3f mm\n",
    window.id,
    window.span_a.start_m / mm,
    window.span_a.stop_m / mm,
    window.span_b.start_m / mm,
    window.span_b.stop_m / mm,
)

# =============================================================================
# 9. Finalize the Draft
# =============================================================================
#
# We finalize twice:
#
# 1. Symbolic-node netlist
#    Easier for humans to read because node names remain descriptive.
#
# 2. Renumbered-node netlist
#    Same circuit, but node labels become "1", "2", "3", ...
#    This demonstrates the "final lowering" idea discussed earlier.

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

@printf("\nSymbolic netlist component count: %d\n", length(symbolic_netlist))
@printf("Renumbered netlist component count: %d\n", length(numeric_netlist))

# =============================================================================
# 10. Run a Small-Signal Simulation
# =============================================================================
#
# We excite port 1 and inspect:
#
# - S21 : through transmission on line A
# - S41 : coupling from line A input to the far end of line B
#
# Because both lines are terminated and only weakly coupled over a short window,
# S21 should stay near the through-line behavior, while S41 should show a much
# smaller but non-zero transfer.

ws = 2π .* (1.0:0.05:12.0) .* GHz
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

s41 = solution.linearized.S(
    outputmode=(0,),
    outputport=4,
    inputmode=(0,),
    inputport=1,
    freqindex=:,
)

s21_mag = abs.(s21)
s41_mag = abs.(s41)

peak_s21_idx = argmax(s21_mag)
peak_s41_idx = argmax(s41_mag)

@printf(
    "\nPeak |S21| = %.4f at %.3f GHz\n",
    s21_mag[peak_s21_idx],
    freqs_GHz[peak_s21_idx],
)
@printf(
    "Peak |S41| = %.4f at %.3f GHz\n",
    s41_mag[peak_s41_idx],
    freqs_GHz[peak_s41_idx],
)

# =============================================================================
# 11. Save the Result for Later Inspection
# =============================================================================
#
# Saving a CSV is convenient because:
# - you can inspect it later without re-running the simulation
# - you can plot it however you want
# - it keeps the example self-contained

result_df = DataFrame(
    frequency_GHz=freqs_GHz,
    S21_real=real.(s21),
    S21_imag=imag.(s21),
    S21_mag=s21_mag,
    S41_real=real.(s41),
    S41_imag=imag.(s41),
    S41_mag=s41_mag,
)

csv_path = joinpath(@__DIR__, "draft_layer_offset_coupled_window_demo_sparams.csv")
CSV.write(csv_path, result_df)
println("\nSaved result CSV to: $csv_path")
