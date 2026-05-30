### A Pluto.jl notebook ###
# v1.0.1

#> [frontmatter]
#> title = "01 Grounded LC Reflection"
#> tags = ["julia-core", "hb", "s-parameters", "lc-resonator"]
#> description = "A small Julia Core Pluto example that solves a one-port grounded LC resonator and plots real S/Z traces from HBSolveResult."

using Markdown
using InteractiveUtils

# ╔═╡ 91fd6d8b-4c2f-4512-8734-1c18848986e1
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

# ╔═╡ 40fbad2b-47b1-4943-a1f8-1d0506ec882c
md"""
# 01 Grounded LC Reflection

This notebook simulates a one-port grounded LC resonator through the Julia Core HB path:

```text
port 1 + 50 ohm reference
    -> node
    -> C to ground
    -> L to ground
```

The solver output below is real `HBSolveResult` data. The plots read directly from `result.traces`.

The notebook follows the shared seven-point structure: parameters, reusable plan builder, EngineeringGraph, compiled circuit, HBProblemSpec, solver result, and real plotted traces with a physics sanity check.
"""

# ╔═╡ ad208c65-0358-440b-a4ac-169d414127ec
md"""
## 1. Parameters And f0 Estimate

All user-facing values use default Julia Core units: farads, henries, ohms, hertz, and amperes.
"""

# ╔═╡ db955f48-67d8-4549-9c65-1fdb8b232cd8
begin
    capacitance = 80e-15
    inductance = 10e-9
    resistance = 50.0

    start_frequency = 1.0e9
    stop_frequency = 10.0e9
    point_count = 1000

    pump_frequency = 8.0e9
    pump_current = 0.0
    n_pump_harmonics = 8
    n_modulation_harmonics = 16

    optional_hb_kwargs = Dict{Symbol,Any}(
        :nbatches => 1,
        :iterations => 200,
        :ftol => 1e-8,
    )
end

# ╔═╡ d7842212-1f9d-4d92-a48c-6ecbd08a8104
begin
    f0_estimate_hz = 1 / (2π * sqrt(inductance * capacitance))
    (
        formula="1/(2π*sqrt(L*C))",
        capacitance_farad=capacitance,
        inductance_henry=inductance,
        f0_estimate_ghz=f0_estimate_hz / 1e9,
    )
end

# ╔═╡ c3307206-1833-427d-9884-5ef9ea2b42c2
md"""
## 2. Reusable Plan Builder

This helper keeps the notebook compact while still returning the inspectable Julia Core objects: `plan`, `graph`, `compiled`, `hb_problem`, and the real solver `result`.
"""

# ╔═╡ de46ddde-15dc-42cb-af0f-d37322bb9e5f
example = build_grounded_lc_example(
    id="grounded-lc-reflection",
    capacitance=capacitance,
    inductance=inductance,
    resistance=resistance,
    start_frequency=start_frequency,
    stop_frequency=stop_frequency,
    point_count=point_count,
    pump_frequency=pump_frequency,
    pump_current=pump_current,
    n_pump_harmonics=n_pump_harmonics,
    n_modulation_harmonics=n_modulation_harmonics,
    optional_hb_kwargs=optional_hb_kwargs,
)

# ╔═╡ b6abfdc0-b1b1-40c2-8b56-c95b9589272b
md"""
## 3. EngineeringGraph

The EngineeringGraph remains component-level and human-facing. The compiled netlist is the solver representation.
"""

# ╔═╡ 3f85c3f9-f7b4-4551-8a57-f2bc714fa891
example.graph.components

# ╔═╡ 43ab6fea-e482-4473-abd0-81a6adc375c7
example.graph.ports

# ╔═╡ 6504a7c3-93bd-4cd6-8e2a-96226f435c1f
example.graph.relations

# ╔═╡ f99a2267-dff5-46fd-b92b-48d338ad287d
md"""
## 4. Compiled Circuit

The compiler output is the solver-facing representation. Inspect the netlist rows, external port map, and component values before looking at solver output.
"""

# ╔═╡ a31c69d4-e191-4242-b7d2-43e7c9208bde
example.compiled.netlist

# ╔═╡ 536e763e-7b0b-40fd-9f0f-f09b03e7272e
example.compiled.port_map

# ╔═╡ 3b2e5a45-8138-477c-a195-23cf9e20edc0
example.compiled.component_values

# ╔═╡ 9168eae7-7f76-4d65-a2dc-498a5030ea1c
md"""
## 5. HBProblemSpec

`HBProblemSpec` carries the normalized frequencies, angular frequencies, pump axis, zero-current source binding, harmonics, controls, observables, and solver kwargs.
"""

# ╔═╡ 2d59d427-2a76-4f3c-af0b-d7abe0db63c7
hb_problem = example.hb_problem

# ╔═╡ 95bbd69d-164c-43b4-85e9-ed59f518970b
(
    frequencies_hz=hb_problem.frequencies_hz,
    ws_count=length(hb_problem.ws),
    wp=hb_problem.wp,
    sources=hb_problem.sources,
    Nmodulationharmonics=hb_problem.Nmodulationharmonics,
    Npumpharmonics=hb_problem.Npumpharmonics,
    controls=hb_problem.controls,
    observables=hb_problem.observables,
    optional_hb_kwargs=hb_problem.optional_hb_kwargs,
)

# ╔═╡ ff39a5a5-0452-4a2d-9ec6-33ba3f96496e
md"""
## 6. Solver Result

The result contains all requested output families returned by the solver. This notebook plots a small subset for teaching.
"""

# ╔═╡ 09ba2ec8-4d94-4033-b4cc-bf6c520a8112
result = example.result

# ╔═╡ 9f5da57c-ce18-48a3-bba0-86fd67613e1c
keys(result.traces)

# ╔═╡ ad62c614-e336-4a3b-a8c2-98bb6675cc18
begin
    s11 = zero_mode_s(result, 1, 1)
    z_label = "om=0|op=1|im=0|ip=1"
    z_traces = get(result.traces, :z_parameter_mode, nothing)
    z11 = z_traces isa AbstractDict && haskey(z_traces, z_label) ? zero_mode_z(result, 1, 1) : nothing
    y11 = 1 ./ z11
    frequencies_ghz = result.frequencies_hz ./ 1e9
end

# ╔═╡ 843549ea-5324-490b-97b7-f4e2b1d6b4f8
md"""
## 7. Expected Physics And Real Plots

For a lossless grounded parallel LC, the ideal shunt impedance is largest near `f0 = 1/(2π*sqrt(L*C))`. Reflection magnitude should remain near 0 dB because this one-port has no dissipative loss, while S11 phase and Z11 carry the resonance signature.
"""

# ╔═╡ 95d0c7ea-898a-4564-b2eb-d3f75e51a708
begin
    nearest_f0_index = argmin(abs.(result.frequencies_hz .- f0_estimate_hz))

    (
        f0_estimate_ghz=f0_estimate_hz / 1e9,
        nearest_simulated_frequency_ghz=frequencies_ghz[nearest_f0_index],
        s11_magnitude_db_near_f0=20 * log10(abs(s11[nearest_f0_index])),
        s11_near_unit_magnitude=abs(abs(s11[nearest_f0_index]) - 1) <= 0.25,
        z11_available=!isnothing(z11),
        z11_imag_crosses_zero=!isnothing(z11) ? minimum(imag.(z11)) <= 0 <= maximum(imag.(z11)) : missing,
    )
end

# ╔═╡ 2ed2ac19-e7d0-42c4-af38-f597931fbf7d
s_parameter_magnitude_figure(
    result.frequencies_hz,
    ["S11" => s11];
    title="Grounded LC Reflection Magnitude",
    config=figure_config,
)

# ╔═╡ adf182b9-3b6c-4fe4-b731-207fae096f0c
s_parameter_phase_figure(
    result.frequencies_hz,
    ["S11" => s11];
    title="Grounded LC Reflection Phase",
    config=figure_config,
)

# ╔═╡ 20614025-d8ce-40f2-b32c-c56d536e766e
begin
    if isnothing(z11)
        "Z11 is not available. Available Z labels: $(join(sort(collect(keys(z_traces))), ", "))"
    else
        z_trace_figure(
            result.frequencies_hz,
            ["Z11" => z11];
            title="Grounded LC Input Impedance",
            config=figure_config,
        )
    end
end

# ╔═╡ 2ef40f9c-b518-4fa7-aad3-23ea171a7551
begin
    if isnothing(z11)
        "Y11 is not available because Z11 is not available."
    else
        y_trace_figure(
            result.frequencies_hz,
            ["Y11" => y11];
            title="Grounded LC Input Admittance",
            config=figure_config,
        )
    end
end

# ╔═╡ Cell order:
# ╠═91fd6d8b-4c2f-4512-8734-1c18848986e1
# ╟─40fbad2b-47b1-4943-a1f8-1d0506ec882c
# ╟─ad208c65-0358-440b-a4ac-169d414127ec
# ╠═db955f48-67d8-4549-9c65-1fdb8b232cd8
# ╠═d7842212-1f9d-4d92-a48c-6ecbd08a8104
# ╟─c3307206-1833-427d-9884-5ef9ea2b42c2
# ╠═de46ddde-15dc-42cb-af0f-d37322bb9e5f
# ╟─b6abfdc0-b1b1-40c2-8b56-c95b9589272b
# ╠═3f85c3f9-f7b4-4551-8a57-f2bc714fa891
# ╠═43ab6fea-e482-4473-abd0-81a6adc375c7
# ╠═6504a7c3-93bd-4cd6-8e2a-96226f435c1f
# ╟─f99a2267-dff5-46fd-b92b-48d338ad287d
# ╠═a31c69d4-e191-4242-b7d2-43e7c9208bde
# ╠═536e763e-7b0b-40fd-9f0f-f09b03e7272e
# ╠═3b2e5a45-8138-477c-a195-23cf9e20edc0
# ╟─9168eae7-7f76-4d65-a2dc-498a5030ea1c
# ╠═2d59d427-2a76-4f3c-af0b-d7abe0db63c7
# ╠═95bbd69d-164c-43b4-85e9-ed59f518970b
# ╟─ff39a5a5-0452-4a2d-9ec6-33ba3f96496e
# ╠═09ba2ec8-4d94-4033-b4cc-bf6c520a8112
# ╠═9f5da57c-ce18-48a3-bba0-86fd67613e1c
# ╠═ad62c614-e336-4a3b-a8c2-98bb6675cc18
# ╟─843549ea-5324-490b-97b7-f4e2b1d6b4f8
# ╠═95d0c7ea-898a-4564-b2eb-d3f75e51a708
# ╠═2ed2ac19-e7d0-42c4-af38-f597931fbf7d
# ╠═adf182b9-3b6c-4fe4-b731-207fae096f0c
# ╠═20614025-d8ce-40f2-b32c-c56d536e766e
# ╠═2ef40f9c-b518-4fa7-aad3-23ea171a7551
