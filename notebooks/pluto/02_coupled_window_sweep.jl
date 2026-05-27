### A Pluto.jl notebook ###
# v0.20.x

# ╔═╡ 6ca5cbe6-cc71-11ee-0001-4b4f65636f72
begin
    import Pkg
    Pkg.activate(joinpath(@__DIR__, "..", "..", "core", "julia", "SuperconductingCircuitsCore"))
    using SuperconductingCircuitsCore
end

# ╔═╡ 6ca5cbe6-cc71-11ee-0002-4b4f65636f72
const mm = 1e-3

# ╔═╡ 6ca5cbe6-cc71-11ee-0003-4b4f65636f72
function build_coupled_design(params)
    line_spec = RLGCSpec(
        length_m=1.0mm,
        n_sections=10,
        l_per_m_h=4.2e-7,
        c_per_m_f=1.7e-10,
    )
    window_spec = CoupledWindowSpec(
        length_m=params["window_length_mm"] * mm,
        n_sections=2,
        l11_per_m_h=4.2e-7,
        l22_per_m_h=4.2e-7,
        lm_per_m_h=0.5e-7,
        c1g_per_m_f=1.7e-10,
        c2g_per_m_f=1.7e-10,
        cm_per_m_f=params["cm_fF_per_m"] * 1e-15,
    )

    window_length_m = params["window_length_mm"] * mm
    draft = CircuitDraft("pluto_coupled_sweep")
    line_a = add_transmission_line!(draft; id="line_a", start_node="a0", end_node="a1", spec=line_spec)
    line_b = add_transmission_line!(draft; id="line_b", start_node="b0", end_node="b1", spec=line_spec)
    apply_coupled_window!(
        draft;
        prefix="window",
        line_a=line_a,
        span_a=LineSpan(0.2mm, 0.2mm + window_length_m),
        line_b=line_b,
        span_b=LineSpan(0.5mm, 0.5mm + window_length_m),
        spec=window_spec,
    )
    return finalize_to_josephson_netlist(draft)
end

# ╔═╡ 6ca5cbe6-cc71-11ee-0004-4b4f65636f72
sweep = SweepSpec([
    SweepAxis("window_length_mm", [0.05, 0.10, 0.15]),
    SweepAxis("cm_fF_per_m", [0.5, 1.0]),
])

# ╔═╡ 6ca5cbe6-cc71-11ee-0005-4b4f65636f72
result = run_design_sweep(build_coupled_design, sweep; threaded=false)

# ╔═╡ 6ca5cbe6-cc71-11ee-0006-4b4f65636f72
[(point.parameters, point.success, isnothing(point.result) ? 0 : length(point.result)) for point in result.points]

# ╔═╡ Cell order:
# ╠═6ca5cbe6-cc71-11ee-0001-4b4f65636f72
# ╠═6ca5cbe6-cc71-11ee-0002-4b4f65636f72
# ╠═6ca5cbe6-cc71-11ee-0003-4b4f65636f72
# ╠═6ca5cbe6-cc71-11ee-0004-4b4f65636f72
# ╠═6ca5cbe6-cc71-11ee-0005-4b4f65636f72
# ╠═6ca5cbe6-cc71-11ee-0006-4b4f65636f72
