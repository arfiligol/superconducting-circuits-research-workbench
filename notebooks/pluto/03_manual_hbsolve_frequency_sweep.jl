### A Pluto.jl notebook ###
# v0.20.x

# ╔═╡ 894b9e36-cc71-11ee-0001-4b4f65636f72
begin
    import Pkg
    Pkg.activate(joinpath(@__DIR__, "..", "..", "core", "julia", "SuperconductingCircuitsCore"))
    using SuperconductingCircuitsCore
end

# ╔═╡ 894b9e36-cc71-11ee-0002-4b4f65636f72
begin
    draft = CircuitDraft("manual_hbsolve_lc")
    add_port_with_termination!(draft; port_number=1, node="drive")
    add_component!(draft; name="C_coupling", node1="drive", node2="res", value=5.0e-15)
    add_component!(draft; name="L_res", node1="res", node2="0", value=8.0e-9)
    add_component!(draft; name="C_res", node1="res", node2="0", value=80.0e-15)
    netlist = finalize_to_josephson_netlist(draft; renumber_nodes=true)
end

# ╔═╡ 894b9e36-cc71-11ee-0003-4b4f65636f72
frequency_range_hz = (4.0e9, 8.0e9, 101)

# ╔═╡ 894b9e36-cc71-11ee-0004-4b4f65636f72
result = run_hbsolve(netlist, Dict(), frequency_range_hz)

# ╔═╡ 894b9e36-cc71-11ee-0005-4b4f65636f72
keys(result.traces)

# ╔═╡ 894b9e36-cc71-11ee-0006-4b4f65636f72
get(result.traces, :zero_mode_s, nothing)

# ╔═╡ Cell order:
# ╠═894b9e36-cc71-11ee-0001-4b4f65636f72
# ╠═894b9e36-cc71-11ee-0002-4b4f65636f72
# ╠═894b9e36-cc71-11ee-0003-4b4f65636f72
# ╠═894b9e36-cc71-11ee-0004-4b4f65636f72
# ╠═894b9e36-cc71-11ee-0005-4b4f65636f72
# ╠═894b9e36-cc71-11ee-0006-4b4f65636f72
