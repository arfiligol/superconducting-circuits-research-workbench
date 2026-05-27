using SuperconductingCircuitsCore

const mm = 1e-3

function build_design(params)
    length_m = params["length_mm"] * mm
    spec = RLGCSpec(
        length_m=length_m,
        n_sections=4,
        l_per_m_h=4.2e-7,
        c_per_m_f=1.7e-10,
    )
    draft = CircuitDraft("sweep_design")
    add_transmission_line!(draft; id="line", start_node="input", end_node="output", spec=spec)
    return (
        netlist=finalize_to_josephson_netlist(draft),
        length_m=length_m,
    )
end

sweep = SweepSpec([
    SweepAxis("length_mm", [0.8, 1.0, 1.2]),
])

result = run_design_sweep(build_design, sweep; threaded=false)

println("sweep points: ", length(result.points))
println("successful points: ", count(point -> point.success, result.points))
for point in result.points
    println("point ", point.point_index, " params=", point.parameters, " success=", point.success)
end
