### A Pluto.jl notebook ###
# v1.0.1

#> [frontmatter]
#> title = "03 Readout Line Hanging QWR"
#> tags = ["julia-core", "hb", "readout", "quarter-wave-resonator", "s21"]
#> description = "Executable Pluto tutorial for a two-port readout LC ladder with a hanging quarter-wave resonator and real S21/S11 traces from HBSolveResult."

using Markdown

# ╔═╡ 2fb0afde-26f9-4b78-a6b8-f9df9c5e4b01
begin
    import Pkg

    core_project = normpath(joinpath(@__DIR__, "..", "..", "core", "julia", "SuperconductingCircuitsCore"))
    core_project_file = normpath(joinpath(core_project, "Project.toml"))
    active_project_file = normpath(something(Base.active_project(), ""))

    if active_project_file != core_project_file
        Pkg.develop(path=core_project)
    end

    using SuperconductingCircuitsCore
    using Plots

    include(joinpath(@__DIR__, "includes", "hb_example_helpers.jl"))
    using .HBExampleHelpers
end

# ╔═╡ 6bd23c0b-b876-49bb-94c0-5d35a0324992
md"""
# 03 Readout Line + Hanging Quarter-wave Resonator

This executable notebook builds a small readout-style two-port network:

```text
input port -> LC ladder readout line -> output port
                         |
                         Cc
                         |
               grounded LC ladder resonator
```

The circuit uses real Julia Core relations: `series_inductor!`, `shunt_capacitor!`, `couple_capacitive!`, and `external_port!`. All plots below read solver traces from `result = run_hb_problem(hb_problem)`.
"""

# ╔═╡ 0d23ff26-a059-41d8-b050-9e7d01d0c003
md"""
## What should I expect?

- The readout line provides through transmission from port 1 to port 2.
- The hanging resonator is coupled to an internal readout node through `Cc`.
- `S21` should show a resonator feature near the ladder resonator band.
- Stronger coupling capacitance should deepen or broaden the feature.
- This MVP is a lumped ladder approximation, not a distributed CPW field solve.
"""

# ╔═╡ bfb5cf36-2474-47a1-9022-833b5a802c92
begin
    line_sections = 2
    resonator_sections = 2

    readout_series_inductance = 0.6e-9
    readout_shunt_capacitance = 35e-15
    resonator_series_inductance = 3.5e-9
    resonator_shunt_capacitance = 45e-15
    coupling_capacitance = 2.0e-15
    port_resistance = 50.0

    start_frequency = 3.0e9
    stop_frequency = 8.0e9
    point_count = 21

    pump_frequency = 10.0e9
    pump_current = 0.0

    optional_hb_kwargs = Dict{Symbol,Any}(
        :iterations => 120,
        :ftol => 1e-8,
        :nbatches => 1,
    )
end

# ╔═╡ c0966500-51d5-4ac7-a96d-9ef1eaa52680
example = build_readout_line_hanging_qwr_example(
    line_sections=line_sections,
    resonator_sections=resonator_sections,
    readout_series_inductance=readout_series_inductance,
    readout_shunt_capacitance=readout_shunt_capacitance,
    resonator_series_inductance=resonator_series_inductance,
    resonator_shunt_capacitance=resonator_shunt_capacitance,
    coupling_capacitance=coupling_capacitance,
    port_resistance=port_resistance,
    start_frequency=start_frequency,
    stop_frequency=stop_frequency,
    point_count=point_count,
    pump_frequency=pump_frequency,
    pump_current=pump_current,
    optional_hb_kwargs=optional_hb_kwargs,
)

# ╔═╡ 72b60b8b-dcfd-427a-8f64-332ee7fa7d20
md"""
## EngineeringGraph

The graph is the human-facing component/relation view. The netlist shown later is the solver-facing lowering.
"""

# ╔═╡ d13372ee-d5df-4a0d-965a-518ac3c1ecb0
example.graph.components

# ╔═╡ 9f9aa226-629c-4d35-ad98-40d3ee8288ab
example.graph.ports

# ╔═╡ 061836f0-3350-45e9-aceb-b15ba36206f0
example.graph.relations

# ╔═╡ 2a2db546-5784-4835-a360-cb0860d4ab21
md"""
## Compiled Representation

These cells show the JosephsonCircuits-facing rows and maps used by `HBProblemSpec`.
"""

# ╔═╡ 9f0e43d4-86ec-4cd2-9676-c234c2160a9d
example.compiled.netlist

# ╔═╡ d626e098-5cf1-484e-a4bc-f02a2c5094e6
example.compiled.port_map

# ╔═╡ d954d748-3614-486b-b1eb-034724ec9872
example.compiled.component_values

# ╔═╡ 58ed0d46-bbd7-4a7d-9b47-4198f48785dd
md"""
## HBProblemSpec

Pump-off still declares a pump axis and pump source slot. The source current is bound to `0.0`; the pump frequency remains finite and positive.
"""

# ╔═╡ ddf748d4-dc88-45cb-bba1-4635dcc30278
hb_problem = example.hb_problem

# ╔═╡ f3600c49-9c6a-479b-8aa0-46e513af7fb7
(
    frequencies_hz=hb_problem.frequencies_hz,
    wp=hb_problem.wp,
    sources=hb_problem.sources,
    Nmodulationharmonics=hb_problem.Nmodulationharmonics,
    Npumpharmonics=hb_problem.Npumpharmonics,
)

# ╔═╡ ff2d6a19-6612-470a-a353-8028c1fb6b7f
md"""
## Solve

The following result is the real Julia Core execution path. The S/Z plots below read from `result.traces`.
"""

# ╔═╡ a865f158-9254-4810-b239-25604baa62d8
result = example.result

# ╔═╡ a91e0f1e-aefd-4e1d-a669-77d9dc9c5223
keys(result.traces)

# ╔═╡ 1b908a8b-e9ff-4e5e-9305-d285a8e2508d
result.traces[:portnumbers]

# ╔═╡ 10b24722-8810-493c-8f61-1ce634ac763a
begin
    frequencies_ghz = result.frequencies_hz ./ 1e9
    s11 = zero_mode_s(result, 1, 1)
    s21 = zero_mode_s(result, 2, 1)
    z11 = zero_mode_z(result, 1, 1)
    z21 = zero_mode_z(result, 2, 1)
end

# ╔═╡ fdd3e9ef-2dc7-4f3b-8841-14d480754695
plot(
    frequencies_ghz,
    [db20(s21) db20(s11)];
    xlabel="Frequency (GHz)",
    ylabel="Magnitude (dB)",
    label=["S21" "S11"],
    title="Readout line + hanging resonator S-parameters",
)

# ╔═╡ 3703176d-f5f2-4eb5-a8f5-ae133d0e08c4
plot(
    frequencies_ghz,
    [phase_deg(s21) phase_deg(s11)];
    xlabel="Frequency (GHz)",
    ylabel="Phase (deg)",
    label=["phase(S21)" "phase(S11)"],
    title="S-parameter phase",
)

# ╔═╡ a1d664e7-667b-451f-9949-9741e6882790
plot(
    frequencies_ghz,
    [real.(z11) imag.(z11) real.(z21) imag.(z21)];
    xlabel="Frequency (GHz)",
    ylabel="Impedance (ohm)",
    label=["real(Z11)" "imag(Z11)" "real(Z21)" "imag(Z21)"],
    title="Zero-mode Z traces",
)

# ╔═╡ 1e1587d6-6256-4343-987b-5778f8863b3a
begin
    y = zero_mode_y_matrix(result; ports=[1, 2])
    y21 = y.values[2, 1, :]
    plot(
        frequencies_ghz,
        [real.(y21) imag.(y21)];
        xlabel="Frequency (GHz)",
        ylabel="Y21 (S)",
        label=["real(Y21)" "imag(Y21)"],
        title="Derived admittance from solver Z traces",
    )
end

# ╔═╡ Cell order:
# ╠═2fb0afde-26f9-4b78-a6b8-f9df9c5e4b01
# ╟─6bd23c0b-b876-49bb-94c0-5d35a0324992
# ╟─0d23ff26-a059-41d8-b050-9e7d01d0c003
# ╠═bfb5cf36-2474-47a1-9022-833b5a802c92
# ╠═c0966500-51d5-4ac7-a96d-9ef1eaa52680
# ╟─72b60b8b-dcfd-427a-8f64-332ee7fa7d20
# ╠═d13372ee-d5df-4a0d-965a-518ac3c1ecb0
# ╠═9f9aa226-629c-4d35-ad98-40d3ee8288ab
# ╠═061836f0-3350-45e9-aceb-b15ba36206f0
# ╟─2a2db546-5784-4835-a360-cb0860d4ab21
# ╠═9f0e43d4-86ec-4cd2-9676-c234c2160a9d
# ╠═d626e098-5cf1-484e-a4bc-f02a2c5094e6
# ╠═d954d748-3614-486b-b1eb-034724ec9872
# ╟─58ed0d46-bbd7-4a7d-9b47-4198f48785dd
# ╠═ddf748d4-dc88-45cb-bba1-4635dcc30278
# ╠═f3600c49-9c6a-479b-8aa0-46e513af7fb7
# ╟─ff2d6a19-6612-470a-a353-8028c1fb6b7f
# ╠═a865f158-9254-4810-b239-25604baa62d8
# ╠═a91e0f1e-aefd-4e1d-a669-77d9dc9c5223
# ╠═1b908a8b-e9ff-4e5e-9305-d285a8e2508d
# ╠═10b24722-8810-493c-8f61-1ce634ac763a
# ╠═fdd3e9ef-2dc7-4f3b-8841-14d480754695
# ╠═3703176d-f5f2-4eb5-a8f5-ae133d0e08c4
# ╠═a1d664e7-667b-451f-9949-9741e6882790
