using SuperconductingCircuitsCore

draft = CircuitDraft("simple_lc_resonator")

add_port_with_termination!(draft; port_number=1, node="drive")
add_component!(draft; name="C_coupling", node1="drive", node2="res", value=5.0e-15)
add_component!(draft; name="L_res", node1="res", node2="0", value=8.0e-9)
add_component!(draft; name="C_res", node1="res", node2="0", value=80.0e-15)

netlist = finalize_to_josephson_netlist(draft; renumber_nodes=true)

println("simple_lc_resonator rows: ", length(netlist))
for row in netlist
    println(row)
end
