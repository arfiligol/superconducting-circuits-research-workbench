using Printf
using JosephsonCircuits
using CSV
using DataFrames

include(joinpath(@__DIR__, "Reusable Component", "ReusableComponents.jl"))
using .ReusableComponents

# =============================================================================
# 1. What This Demo Tries to Teach
# =============================================================================
#
# This example focuses on the most basic workflow question:
#
#     "How do I connect multiple reusable components together?"
#
# We intentionally do NOT use coupled windows in this demo.
# Instead, we only show the component/pin/connect API:
#
#     Readout Line  ->  Half-Wave Purcell Filter  ->  Readout Line
#
# The new pieces to look at are:
#
# - `add_readout_line_component!`
# - `add_half_wave_purcell_filter_component!`
# - `connect!`
# - `apply_series_chain!`
#
# The key idea is:
# component connections are declared first, and only later flattened into a
# JosephsonCircuits netlist by `finalize_to_josephson_netlist(...)`.

# =============================================================================
# 2. Units and Shared RLGC Data
# =============================================================================

const GHz = 1e9
const mm = 1e-3
const fF = 1e-15

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

# =============================================================================
# 3. Create the Editable Draft
# =============================================================================

draft = CircuitDraft("component_chain_demo")

# =============================================================================
# 4. Register the Three Components
# =============================================================================
#
# None of these components receives its final node names yet.
# Each one only owns symbolic pins such as:
#
# - left readout line:  :left, :right
# - Purcell filter:     :left, :right
# - right readout line: :left, :right
#
# The actual node identities will be resolved after we declare the connections.

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

# =============================================================================
# 5. Connect the Three Components into One Chain
# =============================================================================
#
# This is the "apply function" version of series wiring.
#
# It performs:
#
#   left_readout :right  ->  purcell_filter :left
#   purcell_filter :right -> right_readout :left
#
# In other words, it builds:
#
#   Readout Line - Half-Wave Purcell Filter - Readout Line

apply_series_chain!(draft, left_readout, purcell_filter, right_readout)

# =============================================================================
# 6. Attach External Buses and Ports
# =============================================================================
#
# The chain itself is now assembled internally.
# We still need to expose the two ends of the chain to the outside world.
#
# We do that in two steps:
#
# 1. connect the component pins to named external buses
# 2. place the actual JosephsonCircuits ports and 50 Ohm terminations on those buses

connect!(draft, left_readout, :left, "input_bus")
connect!(draft, right_readout, :right, "output_bus")

add_port_with_termination!(draft; port_number=1, node="input_bus", prefix="input")
add_port_with_termination!(draft; port_number=2, node="output_bus", prefix="output")

# =============================================================================
# 7. Finalize the Draft
# =============================================================================
#
# We again produce both:
#
# - a human-readable symbolic netlist
# - a numerically renumbered netlist
#
# The important thing to notice is that the top-level script never manually
# invented the internal PF/readout connection nodes.
# Those were created automatically by the draft layer.

symbolic_netlist = finalize_to_josephson_netlist(draft; renumber_nodes=false)
numeric_netlist = finalize_to_josephson_netlist(draft; renumber_nodes=true)

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
# 8. Simulate the Two-Port Chain
# =============================================================================
#
# This is now just a normal JosephsonCircuits simulation of the flattened
# circuit. The authoring complexity stayed inside the draft layer.

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

s21_mag = abs.(s21)
peak_idx = argmax(s21_mag)

@printf(
    "\nPeak |S21| = %.4f at %.3f GHz\n",
    s21_mag[peak_idx],
    freqs_GHz[peak_idx],
)

# =============================================================================
# 9. Save the Result
# =============================================================================

result_df = DataFrame(
    frequency_GHz=freqs_GHz,
    S21_real=real.(s21),
    S21_imag=imag.(s21),
    S21_mag=s21_mag,
)

csv_path = joinpath(@__DIR__, "draft_layer_component_chain_demo_s21.csv")
CSV.write(csv_path, result_df)
println("\nSaved result CSV to: $csv_path")
