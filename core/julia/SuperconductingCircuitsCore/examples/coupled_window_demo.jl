using SuperconductingCircuitsCore

const mm = 1e-3

line_spec = RLGCSpec(
    length_m=1.0mm,
    n_sections=12,
    l_per_m_h=4.2e-7,
    c_per_m_f=1.7e-10,
)

window_spec = CoupledWindowSpec(
    length_m=0.1mm,
    n_sections=3,
    l11_per_m_h=4.2e-7,
    l22_per_m_h=4.2e-7,
    lm_per_m_h=0.5e-7,
    c1g_per_m_f=1.7e-10,
    c2g_per_m_f=1.7e-10,
    cm_per_m_f=1.0e-12,
)

draft = CircuitDraft("coupled_window_demo")
line_a = add_transmission_line!(draft; id="line_a", start_node="a0", end_node="a1", spec=line_spec)
line_b = add_transmission_line!(draft; id="line_b", start_node="b0", end_node="b1", spec=line_spec)

apply_coupled_window!(
    draft;
    prefix="window",
    line_a=line_a,
    span_a=LineSpan(0.2mm, 0.3mm),
    line_b=line_b,
    span_b=LineSpan(0.4mm, 0.5mm),
    spec=window_spec,
)

netlist = finalize_to_josephson_netlist(draft)

println("coupled_window_demo rows: ", length(netlist))
for row in netlist[1:min(12, length(netlist))]
    println(row)
end
