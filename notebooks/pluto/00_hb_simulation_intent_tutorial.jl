### A Pluto.jl notebook ###
# v1.0.1

#> [frontmatter]
#> title = "00 LC Resonator Reflection"
#> tags = ["julia-core", "hb", "lc-resonator", "s-parameters"]
#> description = "Self-contained Julia Core Pluto tutorial for a grounded LC resonator, HBProblemSpec construction, and real S11/Z11 plots from HBSolveResult."

using Markdown
using InteractiveUtils

# ╔═╡ 2a35f7a7-4bf1-4b18-8e06-8709ff044900
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
    using .HBExampleHelpers: db20, phase_deg, zero_mode_s, zero_mode_z
end

# ╔═╡ 8532fbc3-1b76-4a57-8fb1-6729fbf50901
md"""
# 00 LC Resonator / Grounded LC Reflection

This notebook is the minimal Julia Core workflow. It builds a one-port shunt LC resonator:

```text
50 ohm port -> node
                 |-- C -- ground
                 |-- L -- ground
```

The system is lumped: the capacitor and inductor are point elements at the same circuit node. No transmission-line or coupling-window approximation is used here.
"""

# ╔═╡ 9a7f2a7d-f772-48d1-88c4-b12b440b7402
md"""
## Physics And Modeling Convention

A parallel LC has admittance `Y = jωC + 1/(jωL)`. Near
`f0 = 1 / (2π * sqrt(L * C))`, the ideal shunt admittance crosses through zero and the shunt impedance is large.

For a lossless one-port, `|S11|` remains close to unity. The resonance is easiest to see in `phase(S11)` and in the real/imaginary parts of `Z11`.
"""

# ╔═╡ 49fc223e-0102-4cb3-a747-d05865f88755
begin
    capacitance = 80.0e-15
    inductance = 10.0e-9
    port_resistance = 50.0

    start_frequency = 1.0e9
    stop_frequency = 10.0e9
    point_count = 101

    pump_frequency = 8.0e9
    pump_current = 0.0

    optional_hb_kwargs = Dict{Symbol,Any}(
        :nbatches => 1,
        :iterations => 120,
        :ftol => 1e-8,
    )
end

# ╔═╡ 950c83dd-31d4-4546-8f91-34c1d75c76e2
f0_estimate = 1 / (2π * sqrt(inductance * capacitance))

# ╔═╡ 4dd73542-6d50-4f02-aaf5-ffcf67e6516e
(
    capacitance_f=capacitance,
    inductance_h=inductance,
    f0_estimate_ghz=f0_estimate / 1e9,
    frequency_span_ghz=(start_frequency / 1e9, stop_frequency / 1e9),
)

# ╔═╡ c421ced1-bc7d-4265-aef9-51e153086981
md"""
## Julia Core Authoring

`build_lc_resonator_example` is a non-Pluto Core builder that returns the same objects a notebook would build manually: `CircuitPlan`, `EngineeringGraph`, compiled netlist, `HBProblemSpec`, and a real solver result.
"""

# ╔═╡ 6037c548-7e6b-4295-9ef3-387bb26dfe51
example = build_lc_resonator_example(
    capacitance=capacitance,
    inductance=inductance,
    port_resistance=port_resistance,
    start_frequency=start_frequency,
    stop_frequency=stop_frequency,
    point_count=point_count,
    pump_frequency=pump_frequency,
    pump_current=pump_current,
    optional_hb_kwargs=optional_hb_kwargs,
)

# ╔═╡ 673a74d5-d030-42e7-81f8-ce062d1d8fbb
md"""
## EngineeringGraph Inspection

The graph shows the human-facing model: one external port and two shunt relations to ground.
"""

# ╔═╡ 61666273-7670-441e-98d9-3ea04bd38ca6
example.graph.ports

# ╔═╡ f80ead68-9277-47a0-bf3f-a916dfe99a27
example.graph.relations

# ╔═╡ 57595d3d-7f52-4887-82a7-fc8d54fd0bc4
md"""
## Compiled Solver Representation

The compiler lowers the port, reference resistor, shunt capacitor, and shunt inductor into JosephsonCircuits rows.
"""

# ╔═╡ e048d733-bcc6-4ab9-9953-8e7101a8e4ae
example.compiled.netlist

# ╔═╡ da63ed47-cf58-4027-a58c-1830afb6e1af
example.compiled.component_values

# ╔═╡ 59f1b851-a8f2-4266-99f7-b86395c97afe
md"""
## HBProblemSpec And Real Solver Output

Pump-off HB still declares a pump axis and source slot. The source current is bound to `0.0`; the solver path is still real.
"""

# ╔═╡ b8a6e98a-0633-49fb-8bd4-309ac58c7661
hb_problem = example.hb_problem

# ╔═╡ f9ef4311-9296-4da2-8d4a-1fbf6fb2db44
(
    frequencies_hz=hb_problem.frequencies_hz,
    wp=hb_problem.wp,
    sources=hb_problem.sources,
    controls=hb_problem.controls,
)

# ╔═╡ 24e55e1c-594d-41c6-a46f-89bf9381a255
result = run_hb_problem(hb_problem)

# ╔═╡ f3dd44ef-bab5-4db5-a312-c923368645d7
keys(result.traces)

# ╔═╡ b6e1fb3c-22da-4db0-86cf-c6aa3d0df32b
begin
    frequencies_ghz = result.frequencies_hz ./ 1e9
    s11 = zero_mode_s(result, 1, 1)
    z11 = zero_mode_z(result, 1, 1)
end

# ╔═╡ 057f6279-1ad2-4050-8de1-5781f6a933b9
(
    nearest_f0_ghz=frequencies_ghz[argmin(abs.(result.frequencies_hz .- f0_estimate))],
    s11_near_unit_magnitude=abs(abs(s11[argmin(abs.(result.frequencies_hz .- f0_estimate))]) - 1) < 0.25,
    z11_imag_crosses_zero=minimum(imag.(z11)) <= 0 <= maximum(imag.(z11)),
)

# ╔═╡ 5133f75f-6a53-4300-ac41-84f2963cc172
s_parameter_magnitude_figure(
    result.frequencies_hz,
    ["S11" => s11];
    title="Grounded LC Reflection Magnitude",
    config=figure_config,
)

# ╔═╡ 458de99d-89e9-46fd-9813-d083fd864d8a
s_parameter_phase_figure(
    result.frequencies_hz,
    ["S11" => s11];
    title="Grounded LC Reflection Phase",
    config=figure_config,
)

# ╔═╡ c437e4c6-8083-4264-a4d6-9353e58384b6
z_trace_figure(
    result.frequencies_hz,
    ["Z11" => z11];
    title="Grounded LC Input Impedance",
    config=figure_config,
)

# ╔═╡ Cell order:
# ╠═2a35f7a7-4bf1-4b18-8e06-8709ff044900
# ╟─8532fbc3-1b76-4a57-8fb1-6729fbf50901
# ╟─9a7f2a7d-f772-48d1-88c4-b12b440b7402
# ╠═49fc223e-0102-4cb3-a747-d05865f88755
# ╠═950c83dd-31d4-4546-8f91-34c1d75c76e2
# ╠═4dd73542-6d50-4f02-aaf5-ffcf67e6516e
# ╟─c421ced1-bc7d-4265-aef9-51e153086981
# ╠═6037c548-7e6b-4295-9ef3-387bb26dfe51
# ╟─673a74d5-d030-42e7-81f8-ce062d1d8fbb
# ╠═61666273-7670-441e-98d9-3ea04bd38ca6
# ╠═f80ead68-9277-47a0-bf3f-a916dfe99a27
# ╟─57595d3d-7f52-4887-82a7-fc8d54fd0bc4
# ╠═e048d733-bcc6-4ab9-9953-8e7101a8e4ae
# ╠═da63ed47-cf58-4027-a58c-1830afb6e1af
# ╟─59f1b851-a8f2-4266-99f7-b86395c97afe
# ╠═b8a6e98a-0633-49fb-8bd4-309ac58c7661
# ╠═f9ef4311-9296-4da2-8d4a-1fbf6fb2db44
# ╠═24e55e1c-594d-41c6-a46f-89bf9381a255
# ╠═f3dd44ef-bab5-4db5-a312-c923368645d7
# ╠═b6e1fb3c-22da-4db0-86cf-c6aa3d0df32b
# ╠═057f6279-1ad2-4050-8de1-5781f6a933b9
# ╠═5133f75f-6a53-4300-ac41-84f2963cc172
# ╠═458de99d-89e9-46fd-9813-d083fd864d8a
# ╠═c437e4c6-8083-4264-a4d6-9353e58384b6
