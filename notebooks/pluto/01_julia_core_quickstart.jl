### A Pluto.jl notebook ###
# v0.20.x

# ╔═╡ 4ab8b5e8-cc71-11ee-0001-4b4f65636f72
begin
    import Pkg
    Pkg.activate(joinpath(@__DIR__, "..", "..", "core", "julia", "SuperconductingCircuitsCore"))
    using SuperconductingCircuitsCore
end

# ╔═╡ 4ab8b5e8-cc71-11ee-0002-4b4f65636f72
const mm = 1e-3

# ╔═╡ 4ab8b5e8-cc71-11ee-0003-4b4f65636f72
line_spec = RLGCSpec(
    length_m=1.0mm,
    n_sections=8,
    l_per_m_h=4.2e-7,
    c_per_m_f=1.7e-10,
)

# ╔═╡ 4ab8b5e8-cc71-11ee-0004-4b4f65636f72
begin
    draft = CircuitDraft("pluto_quickstart")
    readout = add_readout_line_component!(draft; id="readout", line_spec=line_spec)
    connect!(draft, readout, :left, "input")
    connect!(draft, readout, :right, "output")
    add_port_with_termination!(draft; port_number=1, node="input")
    add_port_with_termination!(draft; port_number=2, node="output")
    netlist = finalize_to_josephson_netlist(draft)
end

# ╔═╡ 4ab8b5e8-cc71-11ee-0005-4b4f65636f72
netlist[1:min(12, length(netlist))]

# ╔═╡ Cell order:
# ╠═4ab8b5e8-cc71-11ee-0001-4b4f65636f72
# ╠═4ab8b5e8-cc71-11ee-0002-4b4f65636f72
# ╠═4ab8b5e8-cc71-11ee-0003-4b4f65636f72
# ╠═4ab8b5e8-cc71-11ee-0004-4b4f65636f72
# ╠═4ab8b5e8-cc71-11ee-0005-4b4f65636f72
