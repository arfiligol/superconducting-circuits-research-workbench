### A Pluto.jl notebook ###
# v1.0.1

#> [frontmatter]
#> title = "Point-Coupled Readout Resonator Sweep"
#> tags = ["julia-core", "hb", "readout", "point-coupling", "s21"]
#> description = "Executable Pluto tutorial sweeping a lumped point coupling capacitance and plotting real HBSolveResult S-parameter traces."

using Markdown

# ╔═╡ 4f4b0162-63fa-4f2e-8232-d66e0718264f
begin
    import Pkg

    core_project = normpath(joinpath(@__DIR__, "..", "..", "core", "julia", "SuperconductingCircuitsCore"))
    visualizer_project = normpath(joinpath(@__DIR__, "..", "..", "core", "julia", "SuperconductingCircuitsVisualizer"))
    core_project_file = normpath(joinpath(core_project, "Project.toml"))
    visualizer_project_file = normpath(joinpath(visualizer_project, "Project.toml"))
    active_project_file = normpath(something(Base.active_project(), ""))

    if active_project_file != core_project_file && active_project_file != visualizer_project_file
        Pkg.develop(path=core_project)
        Pkg.develop(path=visualizer_project)
    else
        core_project in LOAD_PATH || pushfirst!(LOAD_PATH, core_project)
        visualizer_project in LOAD_PATH || pushfirst!(LOAD_PATH, visualizer_project)
    end

    using SuperconductingCircuitsCore
    using SuperconductingCircuitsVisualizer

    figure_config = PlotlyFigureConfig(
        download_filename=splitext(basename(@__FILE__))[1],
    )

    include(joinpath(@__DIR__, "includes", "hb_example_helpers.jl"))
    using .HBExampleHelpers
end

# ╔═╡ a0ac5c2e-5a97-4e6b-8c25-683518732c66
md"""
# Point-Coupled Readout Resonator Sweep

This notebook repeats a readout-line + resonator point-coupled model while sweeping the lumped point coupling capacitance `Cc`.

It does not model a finite-length MTL coupled window. The MTL version is `04_readout_line_hanging_qwr_mtl.jl`.

Every curve below comes from a separate real Julia Core solve:

```julia
result = run_hb_problem(hb_problem)
```
"""

# ╔═╡ a00e4616-16f8-42eb-89c2-115c9cb6e1fd
md"""
## What should I expect?

- Larger `Cc` increases interaction between the through line and hanging resonator.
- The S21 feature should change depth and width as coupling changes.
- This is a lumped point-coupled ladder sensitivity example, not a calibrated distributed CPW / MTL model.
"""

# ╔═╡ 6932d6fc-6c7a-40be-b6ef-d990a57373a3
begin
    coupling_values = [0.8e-15, 2.0e-15, 4.0e-15]

    common_kwargs = (
        line_sections=2,
        resonator_sections=2,
        readout_series_inductance=0.6e-9,
        readout_shunt_capacitance=35e-15,
        resonator_series_inductance=3.5e-9,
        resonator_shunt_capacitance=45e-15,
        port_resistance=50.0,
        start_frequency=3.0e9,
        stop_frequency=8.0e9,
        point_count=15,
        pump_frequency=10.0e9,
        pump_current=0.0,
        optional_hb_kwargs=Dict{Symbol,Any}(
            :iterations => 100,
            :ftol => 1e-8,
            :nbatches => 1,
        ),
    )
end

# ╔═╡ d3f995a1-fbcb-4a5e-8a4c-909a7fb516ff
examples = [
    build_point_coupled_readout_resonator_mvp_example(;
        id="coupling-sweep-$(index)",
        coupling_capacitance=coupling,
        common_kwargs...,
    )
    for (index, coupling) in pairs(coupling_values)
]

# ╔═╡ f1e0a1c4-a7c4-4b83-a9c5-d4f12c81767f
md"""
## Authoring Path

The first sweep point is shown as the representative authored circuit. The loop above repeats the same Core path for each coupling value.
"""

# ╔═╡ 929d6cf9-cdaa-4d20-b9b6-4d5d6b162823
examples[1].graph.components

# ╔═╡ 4455b593-e302-49b5-8d97-f1383c2d94d4
examples[1].graph.ports

# ╔═╡ 5d361423-d19e-451b-b7b2-e74ace7e30d9
examples[1].graph.relations

# ╔═╡ 0e2cdf31-d665-42d3-89af-9cfe10c82812
md"""
## Compiled And HBProblemSpec Preview
"""

# ╔═╡ 744d3676-0748-45d2-bc64-797828601c11
examples[1].compiled.netlist

# ╔═╡ 09f3eb33-b570-412f-8417-7692f94b00c0
examples[1].compiled.port_map

# ╔═╡ b7585e76-06c0-4aac-a79c-f2f062d73cfe
examples[1].compiled.component_values

# ╔═╡ 4f564be0-297c-4acb-b8f9-7327312fd8b7
(
    frequencies_hz=examples[1].hb_problem.frequencies_hz,
    wp=examples[1].hb_problem.wp,
    sources=examples[1].hb_problem.sources,
    Nmodulationharmonics=examples[1].hb_problem.Nmodulationharmonics,
    Npumpharmonics=examples[1].hb_problem.Npumpharmonics,
)

# ╔═╡ c88516de-48c4-4f24-9f68-bab943ee4c2f
md"""
## Real Solver Results
"""

# ╔═╡ 8bedf46c-7985-4c62-9508-c90ca99f2199
results = [example.result for example in examples]

# ╔═╡ 0ea41b8d-8f3f-4a51-93f9-149d944884fd
keys(results[1].traces)

# ╔═╡ 66a5a642-dded-4c35-8334-1fa62ef3183b
begin
    s21_curves = [
        "Cc=$(round(coupling * 1e15; digits=2)) fF" => db20(zero_mode_s(result, 2, 1))
        for (coupling, result) in zip(coupling_values, results)
    ]
end

# ╔═╡ f4bb20d0-f90a-4b37-a86c-51c1fa1884ac
multi_curve_figure(
    results[1].frequencies_hz,
    s21_curves;
    title="Point-Coupling Sweep: S21 from HBSolveResult",
    yaxis_title="|S21| (dB)",
    config=figure_config,
)

# ╔═╡ 915d5d2e-4971-4d13-8099-738a16cae8cf
begin
    s11_curves = [
        "Cc=$(round(coupling * 1e15; digits=2)) fF" => db20(zero_mode_s(result, 1, 1))
        for (coupling, result) in zip(coupling_values, results)
    ]
    multi_curve_figure(
        results[1].frequencies_hz,
        s11_curves;
        title="Point-Coupling Sweep: S11 from HBSolveResult",
        yaxis_title="|S11| (dB)",
        config=figure_config,
    )
end

# ╔═╡ Cell order:
# ╠═4f4b0162-63fa-4f2e-8232-d66e0718264f
# ╟─a0ac5c2e-5a97-4e6b-8c25-683518732c66
# ╟─a00e4616-16f8-42eb-89c2-115c9cb6e1fd
# ╠═6932d6fc-6c7a-40be-b6ef-d990a57373a3
# ╠═d3f995a1-fbcb-4a5e-8a4c-909a7fb516ff
# ╟─f1e0a1c4-a7c4-4b83-a9c5-d4f12c81767f
# ╠═929d6cf9-cdaa-4d20-b9b6-4d5d6b162823
# ╠═4455b593-e302-49b5-8d97-f1383c2d94d4
# ╠═5d361423-d19e-451b-b7b2-e74ace7e30d9
# ╟─0e2cdf31-d665-42d3-89af-9cfe10c82812
# ╠═744d3676-0748-45d2-bc64-797828601c11
# ╠═09f3eb33-b570-412f-8417-7692f94b00c0
# ╠═b7585e76-06c0-4aac-a79c-f2f062d73cfe
# ╠═4f564be0-297c-4acb-b8f9-7327312fd8b7
# ╟─c88516de-48c4-4f24-9f68-bab943ee4c2f
# ╠═8bedf46c-7985-4c62-9508-c90ca99f2199
# ╠═0ea41b8d-8f3f-4a51-93f9-149d944884fd
# ╠═66a5a642-dded-4c35-8334-1fa62ef3183b
# ╠═f4bb20d0-f90a-4b37-a86c-51c1fa1884ac
# ╠═915d5d2e-4971-4d13-8099-738a16cae8cf
