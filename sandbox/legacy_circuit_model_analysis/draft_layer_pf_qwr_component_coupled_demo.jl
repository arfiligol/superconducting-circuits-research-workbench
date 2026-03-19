using Printf
using JosephsonCircuits
using CSV
using DataFrames

include(joinpath(@__DIR__, "Reusable Component", "ReusableComponents.jl"))
using .ReusableComponents

# =============================================================================
# 1. Goal of This Demo
# =============================================================================
#
# This example combines the two ideas we care about:
#
# 1. component composition through `connect!` / `apply_series_chain!`
# 2. local distributed rewriting through `apply_coupled_window!`
#
# The circuit built here is:
#
#   Readout Line -> Half-Wave Purcell Filter -> Readout Line
#
# and, separately,
#
#   one passive Hanging Quarter-Wave Resonator component
#
# Then we declare that one span of the Purcell filter's internal line should be
# coupled to one span of the quarter-wave resonator's internal line.
#
# The important teaching point is:
#
# - the top-level script only manipulates COMPONENT objects
# - `apply_coupled_window!` can still reach the internal distributed line of
#   those components because the draft layer registered hidden internal
#   `TransmissionLineInstance`s for them

# =============================================================================
# 2. Basic Constants
# =============================================================================

const GHz = 1e9
const mm = 1e-3
const fF = 1e-15

# =============================================================================
# 3. Shared CPW RLGC Data
# =============================================================================

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
# 4. Create the Editable Draft
# =============================================================================

draft = CircuitDraft("pf_qwr_component_coupled_demo")

# =============================================================================
# 5. Register the Main Three-Component Chain
# =============================================================================

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

connect!(draft, left_readout, :left, "input_bus")
connect!(draft, right_readout, :right, "output_bus")

add_port_with_termination!(draft; port_number=1, node="input_bus", prefix="input")
add_port_with_termination!(draft; port_number=2, node="output_bus", prefix="output")

# =============================================================================
# 6. Register the Passive Hanging Quarter-Wave Resonator
# =============================================================================
#
# This version matches the more common lab setup where the resonator is not
# given its own driven probe port.
#
# It therefore has:
# - no exposed external pins
# - one hidden open end
# - one shorted end to ground
#
# Internally it still owns a distributed line, so it can participate in
# `apply_coupled_window!`.

qwr = add_hanging_quarter_wave_resonator_component!(
    draft;
    id="qwr",
    line_spec=quarter_wave_spec,
    boundary=:short,
)

# =============================================================================
# 7. Define the Coupled Window
# =============================================================================
#
# We now couple:
#
# - a middle span on the Purcell filter internal line
# - a span near the shorted end of the quarter-wave resonator internal line
#
# Notice that the top-level script never had to know the private internal line
# node names of either component.

window_mutual = JosephsonCircuits.even_odd_to_mutual(56.0, 44.0, 2.45, 2.60)

window_spec = CoupledWindowSpec(
    length_m=1.2 * mm,
    n_sections=6,
    l11_per_m_h=window_mutual.L[1, 1],
    l22_per_m_h=window_mutual.L[2, 2],
    lm_per_m_h=window_mutual.L[1, 2],
    c1g_per_m_f=window_mutual.C[1, 1],
    c2g_per_m_f=window_mutual.C[2, 2],
    cm_per_m_f=window_mutual.C[1, 2],
)

apply_coupled_window!(
    draft;
    prefix="pf_qwr_window",
    line_a=purcell_filter,
    span_a=LineSpan(4.2 * mm, 5.4 * mm),
    line_b=qwr,
    span_b=LineSpan(3.6 * mm, 4.8 * mm),
    spec=window_spec,
)

# =============================================================================
# 8. Finalize the Draft
# =============================================================================

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
# 9. Run a Simulation
# =============================================================================
#
# We inspect:
#
# The whole network is now a strict two-port system:
#
# - S21 : through transmission across the main readout/PF/readout chain
# - S11 : input reflection at the main input port

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

notch_idx = argmin(s21_mag)
peak_idx = argmax(s11_mag)

@printf(
    "\nDeepest |S21| notch = %.4f at %.3f GHz\n",
    s21_mag[notch_idx],
    freqs_GHz[notch_idx],
)
@printf(
    "Largest |S11| reflection = %.4f at %.3f GHz\n",
    s11_mag[peak_idx],
    freqs_GHz[peak_idx],
)

# =============================================================================
# 10. Save the Result
# =============================================================================

result_df = DataFrame(
    frequency_GHz=freqs_GHz,
    S21_real=real.(s21),
    S21_imag=imag.(s21),
    S21_mag=s21_mag,
    S11_real=real.(s11),
    S11_imag=imag.(s11),
    S11_mag=s11_mag,
)

csv_path = joinpath(@__DIR__, "draft_layer_pf_qwr_component_coupled_demo_sparams.csv")
CSV.write(csv_path, result_df)
println("\nSaved result CSV to: $csv_path")
