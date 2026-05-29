### A Pluto.jl notebook ###
# v1.0.1

#> [frontmatter]
#> title = "05 Output Families S Z QE CM"
#> tags = ["julia-core", "hb", "outputs", "qe", "cm"]
#> description = "Executable Pluto tutorial showing Julia Core full requested-output-family extraction for S, Z, QE, QEideal, and CM."

using Markdown

# ╔═╡ 170576f8-3f27-43c6-b2dc-73908d980f72
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

# ╔═╡ 872d4388-4978-4a0e-b021-8d5df2bf1e4a
md"""
# 05 Output Families: S / Z / QE / QEideal / CM

This notebook teaches the result shape, not final device physics. It requests all product-default output families and inspects the full family keys returned by Julia Core.

Julia Core extracts requested families completely. Pluto, storage, and report layers choose what subset to plot or persist.
"""

# ╔═╡ 9f81206e-7052-4448-b2dc-9c3be981902a
md"""
## What should I expect?

- `result.traces` should include `:s_parameter_mode`, `:z_parameter_mode`, `:qe_mode`, `:qeideal_mode`, and `:cm_mode`.
- Missing requested families are errors in Julia Core.
- Solver-returned `NaN` values are preserved as solver output.
- The representative QE/CM plots here are API/extraction checks for a simple resonator, not calibrated amplifier metrics.
"""

# ╔═╡ ec88dd28-e5b9-4eac-a6a1-7c2cdcb7e1c6
example = build_grounded_lc_example(
    id="output-family-grounded-lc",
    point_count=7,
    n_pump_harmonics=1,
    n_modulation_harmonics=1,
    optional_hb_kwargs=Dict{Symbol,Any}(
        :iterations => 100,
        :ftol => 1e-8,
        :nbatches => 1,
    ),
)

# ╔═╡ 827b56f1-c01d-48fd-a188-5b8b9136d8bd
md"""
## Authoring Path
"""

# ╔═╡ 5986b11e-137d-4882-b234-5901edba3eb1
example.graph.components

# ╔═╡ 5cbe0d1d-b587-4de8-9970-c4b5036c88c6
example.graph.ports

# ╔═╡ c5e0aa20-103a-43d4-aa63-480cfad1ed33
example.graph.relations

# ╔═╡ d9da1ec7-99da-4b50-94e9-b56d0e3f05ea
md"""
## Compiled And HBProblemSpec Preview
"""

# ╔═╡ 3cdfc773-4b94-4752-b9a7-36558f13a419
example.compiled.netlist

# ╔═╡ ecfd492d-3401-4d3b-b13d-afc1ab0ba0b8
example.compiled.port_map

# ╔═╡ 8ee2561e-6fda-44e5-a8f9-e94c096c2093
example.compiled.component_values

# ╔═╡ e5c23829-79e4-42a6-8963-6fe2ed655f1d
(
    frequencies_hz=example.hb_problem.frequencies_hz,
    wp=example.hb_problem.wp,
    sources=example.hb_problem.sources,
    Nmodulationharmonics=example.hb_problem.Nmodulationharmonics,
    Npumpharmonics=example.hb_problem.Npumpharmonics,
)

# ╔═╡ 86a835f3-dc85-4677-8f10-75f77183376c
md"""
## Solve And Inspect Families
"""

# ╔═╡ 3f37b533-2b15-4e4c-894b-74e8195ee4d9
result = example.result

# ╔═╡ 2072444d-dd03-4954-a6af-0a6ab3f30be0
keys(result.traces)

# ╔═╡ 1f46e8ea-cda5-4bb2-93e7-e1a6895fb941
(
    s_keys=sort(collect(keys(result.traces[:s_parameter_mode]))),
    z_keys=sort(collect(keys(result.traces[:z_parameter_mode]))),
    qe_keys=sort(collect(keys(result.traces[:qe_mode]))),
    qeideal_keys=sort(collect(keys(result.traces[:qeideal_mode]))),
    cm_keys=sort(collect(keys(result.traces[:cm_mode]))),
)

# ╔═╡ 2d6b4f7f-b0d0-40c8-a553-f06153d7cc0f
begin
    frequencies_ghz = result.frequencies_hz ./ 1e9
    s11 = zero_mode_s(result, 1, 1)
    z11 = zero_mode_z(result, 1, 1)
end

# ╔═╡ b1f04f14-fb44-4713-bf3b-a9a12a5e69de
plot(
    frequencies_ghz,
    [db20(s11) real.(z11) imag.(z11)];
    xlabel="Frequency (GHz)",
    ylabel="Trace value",
    label=["|S11| (dB)" "real(Z11)" "imag(Z11)"],
    title="Representative S/Z traces",
)

# ╔═╡ c0553d20-7895-4834-82e5-a6ad6887fe74
begin
    qe_label = first(sort(collect(keys(result.traces[:qe_mode]))))
    qeideal_label = first(sort(collect(keys(result.traces[:qeideal_mode]))))
    cm_label = first(sort(collect(keys(result.traces[:cm_mode]))))
    qe_trace = result.traces[:qe_mode][qe_label]
    qeideal_trace = result.traces[:qeideal_mode][qeideal_label]
    cm_trace = result.traces[:cm_mode][cm_label]
end

# ╔═╡ 022c7266-8c74-431b-a967-f5f38f047566
plot(
    frequencies_ghz,
    [qe_trace qeideal_trace cm_trace];
    xlabel="Frequency (GHz)",
    ylabel="Solver-returned value",
    label=["QE: $(qe_label)" "QEideal: $(qeideal_label)" "CM: $(cm_label)"],
    title="Representative QE / QEideal / CM traces",
)

# ╔═╡ Cell order:
# ╠═170576f8-3f27-43c6-b2dc-73908d980f72
# ╟─872d4388-4978-4a0e-b021-8d5df2bf1e4a
# ╟─9f81206e-7052-4448-b2dc-9c3be981902a
# ╠═ec88dd28-e5b9-4eac-a6a1-7c2cdcb7e1c6
# ╟─827b56f1-c01d-48fd-a188-5b8b9136d8bd
# ╠═5986b11e-137d-4882-b234-5901edba3eb1
# ╠═5cbe0d1d-b587-4de8-9970-c4b5036c88c6
# ╠═c5e0aa20-103a-43d4-aa63-480cfad1ed33
# ╟─d9da1ec7-99da-4b50-94e9-b56d0e3f05ea
# ╠═3cdfc773-4b94-4752-b9a7-36558f13a419
# ╠═ecfd492d-3401-4d3b-b13d-afc1ab0ba0b8
# ╠═8ee2561e-6fda-44e5-a8f9-e94c096c2093
# ╠═e5c23829-79e4-42a6-8963-6fe2ed655f1d
# ╟─86a835f3-dc85-4677-8f10-75f77183376c
# ╠═3f37b533-2b15-4e4c-894b-74e8195ee4d9
# ╠═2072444d-dd03-4954-a6af-0a6ab3f30be0
# ╠═1f46e8ea-cda5-4bb2-93e7-e1a6895fb941
# ╠═2d6b4f7f-b0d0-40c8-a553-f06153d7cc0f
# ╠═b1f04f14-fb44-4713-bf3b-a9a12a5e69de
# ╠═c0553d20-7895-4834-82e5-a6ad6887fe74
# ╠═022c7266-8c74-431b-a967-f5f38f047566
