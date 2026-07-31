### A Pluto.jl notebook ###
# v1.0.2

#> [frontmatter]
#> title = "D3 Exact-N S21 Explorer"
#> tags = ["pluto", "d3", "exact-n", "s21", "rwa"]
#> description = "Interactive Exact-12 and RWA-6 S21 comparison for one D3 Stage-2 Equivalent Circuit candidate."

using Markdown
using InteractiveUtils

# This Pluto notebook uses @bind for interactivity. When running this notebook outside of Pluto, the following 'mock version' of @bind gives bound variables a default value (instead of an error).
macro bind(def, element)
    #! format: off
    return quote
        local iv = try Base.loaded_modules[Base.PkgId(Base.UUID("6e696c72-6542-2067-7265-42206c756150"), "AbstractPlutoDingetjes")].Bonds.initial_value catch; b -> missing; end
        local el = $(esc(element))
        global $(esc(def)) = Core.applicable(Base.get, el) ? Base.get(el) : iv(el)
        el
    end
    #! format: on
end

# ╔═╡ 631fa8d5-acde-4583-ae83-acde6b604baa
begin
    import Pkg
    Pkg.activate(joinpath(first(DEPOT_PATH), "environments", "v1.12"); io=devnull)

    using LinearAlgebra
    using SHA
    using PlutoUI
    using SuperconductingCircuitsCore
    using SuperconductingCircuitsVisualizer

    JSON3 = SuperconductingCircuitsCore.JSON3
    PlotlyJS = SuperconductingCircuitsVisualizer.PlotlyJS

    include(joinpath(@__DIR__, "d3_circuit_plans.jl"))
    include(joinpath(@__DIR__, "d3_exact_n_response.jl"))
    include(joinpath(@__DIR__, "d3_idc_input.jl"))
    include(joinpath(@__DIR__, "d3_floating_qubit_input.jl"))
    include(joinpath(@__DIR__, "d3_stage_models.jl"))

    using .D3FloatingQubitInput
    using .D3IDCInput

    figure_config = PlotlyFigureConfig(
        display_height_px=560,
        download_filename=splitext(basename(@__FILE__))[1],
    )
    wide_figure_cell = WideCell(;
        max_width=max(1000, something(figure_config.display_width_px, 1000) + 80),
    )
end

# ╔═╡ 81517dbe-033b-44af-b32e-4e226b2906ca
TableOfContents()

# ╔═╡ 22e155ea-e5c1-4395-ba84-55137123eaa8
md"""
# D3 Exact-``N`` ``S_{21}`` Explorer

This notebook starts from one complete D3 Stage-2 Equivalent Circuit candidate,
rebuilds its physical-node ``\mathbf C`` and ``\mathbf K_\Phi``, and evaluates
the project-convention response

```math
S_{21}^{\mathrm{Exact}}(\omega)
```

with the existing Exact-12 open state-space implementation. The RWA-6 trace is
shown beside it as a diagnostic approximation; it is not substituted for the
Exact-12 result.

The default seed is the 6.00 GHz zero-detuning pass-2 receipt. The receipt and
its private electrostatic inputs remain local files and are not copied into
this notebook.
"""

# ╔═╡ 2a675bf8-25e0-4541-aa57-7ee294f58cf5
begin
    # Repoint this path to explore another Stage-2 run receipt.
    workbench_root = normpath(joinpath(@__DIR__, "..", "..", ".."))
    run_json_path = joinpath(
        workbench_root,
        "build",
        "research",
        "d3_stage2_detuning0_joint",
        "slot_6000",
        "pass_2",
        "run.json",
    )

    # Edit the displayed frequency window and interactive parameter spans here.
    frequency_start_ghz = 5.90
    frequency_stop_ghz = 6.10
    frequency_points = 1201
    idc_gap_um = 8.0
    lc_half_span_fraction = 0.15
    notch_half_span_fraction = 0.20
    slider_points = 101
end

# ╔═╡ 036c98e0-1234-49df-afaf-161bc36f8cda
begin
    isfile(run_json_path) || error(
        "Missing Stage-2 receipt: $(run_json_path). Set run_json_path to an existing run.json.",
    )
    run_receipt = JSON3.read(read(run_json_path, String))

    resolve_input_path(path) = isabspath(String(path)) ?
        String(path) :
        joinpath(workbench_root, String(path))

    idc_mapping_path = resolve_input_path(run_receipt.inputs.idc_mapping_path)
    qubit_input_path = resolve_input_path(run_receipt.inputs.qubit_input_path)
    isfile(idc_mapping_path) || error("Missing IDC mapping: $(idc_mapping_path)")
    isfile(qubit_input_path) || error("Missing qubit input: $(qubit_input_path)")

    idc_mapping = load_d3_idc_mapping(idc_mapping_path; gap_um=idc_gap_um)
    qubit_input = load_floating_qubit_nominal_input(
        qubit_input_path,
        (; kwargs...) -> (; kwargs...);
        gap_um=idc_gap_um,
    )
    qubit_model = qubit_input.model

    fixed_model = (
        c0r_f=qubit_model.C0r_fF * 1e-15,
        c01_f=qubit_model.C01_fF * 1e-15,
        c02_f=qubit_model.C02_fF * 1e-15,
        c12_qubit_f=qubit_model.C12_fF * 1e-15,
        cr1_f=qubit_model.Cr1_fF * 1e-15,
        cr2_f=qubit_model.Cr2_fF * 1e-15,
        l_j_per_junction_h=qubit_model.L_J_per_junction_nH * 1e-9,
        feedline_length_m=1e-3,
        feedline_l_per_m_h=D3_DEFAULT_FEEDLINE_L_PER_M_H,
        feedline_c_per_m_f=D3_DEFAULT_FEEDLINE_C_PER_M_F,
        port_resistance_ohm=50.0,
    )

    receipt_candidate = run_receipt.candidate
    seed_candidate = (
        Cr_fF=Float64(receipt_candidate.Cr_f) * 1e15,
        Lr_nH=Float64(receipt_candidate.Lr_h) * 1e9,
        Cp_fF=Float64(receipt_candidate.Cp_f) * 1e15,
        Lp_nH=Float64(receipt_candidate.Lp_h) * 1e9,
        Cn_fF=Float64(receipt_candidate.Cn_f) * 1e15,
        Ln_nH=Float64(receipt_candidate.Ln_h) * 1e9,
        u_IDC_um=Float64(receipt_candidate.u_IDC),
    )
end

# ╔═╡ bbb0b9de-32e3-47f6-9299-d38c2f02a980
begin
    parameter_ranges = (
        Cr_fF=range(
            seed_candidate.Cr_fF * (1 - lc_half_span_fraction),
            seed_candidate.Cr_fF * (1 + lc_half_span_fraction);
            length=slider_points,
        ),
        Lr_nH=range(
            seed_candidate.Lr_nH * (1 - lc_half_span_fraction),
            seed_candidate.Lr_nH * (1 + lc_half_span_fraction);
            length=slider_points,
        ),
        Cp_fF=range(
            seed_candidate.Cp_fF * (1 - lc_half_span_fraction),
            seed_candidate.Cp_fF * (1 + lc_half_span_fraction);
            length=slider_points,
        ),
        Lp_nH=range(
            seed_candidate.Lp_nH * (1 - lc_half_span_fraction),
            seed_candidate.Lp_nH * (1 + lc_half_span_fraction);
            length=slider_points,
        ),
        Cn_fF=range(
            seed_candidate.Cn_fF * (1 - notch_half_span_fraction),
            seed_candidate.Cn_fF * (1 + notch_half_span_fraction);
            length=slider_points,
        ),
        Ln_nH=range(
            seed_candidate.Ln_nH * (1 - notch_half_span_fraction),
            seed_candidate.Ln_nH * (1 + notch_half_span_fraction);
            length=slider_points,
        ),
        u_IDC_um=sort(unique(vcat(
            collect(range(
                idc_mapping.valid_length_range_um[1],
                idc_mapping.valid_length_range_um[2];
                length=slider_points,
            )),
            seed_candidate.u_IDC_um,
        ))),
    )
end

# ╔═╡ 8a1558ed-6600-4d35-bbc4-d62d1089ef2f
@bind reset_to_receipt Button("Reset all sliders to receipt seed")

# ╔═╡ c7833984-8a56-4d86-a1fa-ec5d8dc7e17a
begin
    reset_to_receipt
    candidate_control_panel = PlutoUI.ExperimentalLayout.Div(
        [
            md"""**``C_r`` (fF)**  
            $(@bind Cr_fF Slider(parameter_ranges.Cr_fF; default=seed_candidate.Cr_fF, show_value=true))""",
            md"""**``L_r`` (nH)**  
            $(@bind Lr_nH Slider(parameter_ranges.Lr_nH; default=seed_candidate.Lr_nH, show_value=true))""",
            md"""**``C_p`` (fF)**  
            $(@bind Cp_fF Slider(parameter_ranges.Cp_fF; default=seed_candidate.Cp_fF, show_value=true))""",
            md"""**``L_p`` (nH)**  
            $(@bind Lp_nH Slider(parameter_ranges.Lp_nH; default=seed_candidate.Lp_nH, show_value=true))""",
            md"""**``C_n`` (fF)**  
            $(@bind Cn_fF Slider(parameter_ranges.Cn_fF; default=seed_candidate.Cn_fF, show_value=true))""",
            md"""**``L_n`` (nH)**  
            $(@bind Ln_nH Slider(parameter_ranges.Ln_nH; default=seed_candidate.Ln_nH, show_value=true))""",
            md"""**``u_{\mathrm{IDC}}`` (µm)**  
            $(@bind u_IDC_um Slider(parameter_ranges.u_IDC_um; default=seed_candidate.u_IDC_um, show_value=true))""",
        ];
        style=Dict(
            "display" => "grid",
            "grid-template-columns" => "repeat(auto-fit, minmax(240px, 1fr))",
            "gap" => "0.75rem 1.5rem",
            "align-items" => "end",
        ),
    )
end |> wide_figure_cell

# ╔═╡ c09506cd-510f-4901-bba5-79a679bd2046
begin
    live_candidate = (
        Cr_f=Cr_fF * 1e-15,
        Lr_h=Lr_nH * 1e-9,
        Cp_f=Cp_fF * 1e-15,
        Lp_h=Lp_nH * 1e-9,
        Cn_f=Cn_fF * 1e-15,
        Ln_h=Ln_nH * 1e-9,
        u_IDC=u_IDC_um,
    )

    stage2_model = d3_response_equivalent_model_from_lc(
        live_candidate,
        fixed_model,
        idc_mapping,
    )
    exact_n_model = d3_exact_n_compiled_model(stage2_model.built)
    frequency_hz = collect(range(
        frequency_start_ghz * 1e9,
        frequency_stop_ghz * 1e9;
        length=frequency_points,
    ))
    response_closure = d3_exact_n_response_closure(
        exact_n_model,
        frequency_hz,
    )

    exact_s21 = response_closure.analytical.exact.s21
    rwa_s21 = response_closure.analytical.rwa.s21
end

# ╔═╡ 14ac2465-c6c5-44b9-a2cc-a05340d3895e
begin
    s_parameter_abs_magnitude_figure(
        frequency_hz,
        [
            "Exact-12 S21" => exact_s21,
            "RWA-6 S21" => rwa_s21,
        ];
        title="D3 Exact-N S21 Magnitude",
        config=figure_config,
    )
end |> wide_figure_cell

# ╔═╡ 5735277e-a0a0-40a9-ace7-122dc20edb91
begin
    s_parameter_phase_figure(
        frequency_hz,
        [
            "Exact-12 S21" => exact_s21,
            "RWA-6 S21" => rwa_s21,
        ];
        title="D3 Exact-N S21 Phase",
        unit=:deg,
        config=figure_config,
    )
end |> wide_figure_cell

# ╔═╡ b8733016-3a46-4198-a36a-6bccbe929d1e
begin
    format_value(value; digits=6) = string(round(value; digits=digits))

    pole_data = response_closure.direct.poles
    visible_pole_indices = findall(eachindex(pole_data.frequencies_hz)) do index
        frequency_ghz = real(pole_data.frequencies_hz[index]) / 1e9
        frequency_start_ghz <= frequency_ghz <= frequency_stop_ghz
    end
    visible_pole_rows = isempty(visible_pole_indices) ?
        "| — | No open pole lies inside the displayed window | — |" :
        join(
            [
                "| $(index) | $(format_value(real(pole_data.frequencies_hz[index]) / 1e9; digits=9)) | $(format_value(pole_data.linewidths_hz[index] / 1e6; digits=6)) |"
                for index in visible_pole_indices
            ],
            "\n",
        )

    md"""
    ## Current Exact-``N`` result

    | Pole | Frequency (GHz) | Full linewidth (MHz) |
    |---:|---:|---:|
    $(visible_pole_rows)

    | Numerical check | Value |
    |---|---:|
    | ``\max|S_{21}^{\mathrm{Exact}}-S_{21}^{C/K}|`` | $(format_value(response_closure.residuals.max_abs_exact_s21; digits=12)) |
    | ``\max|S_{21}^{\mathrm{RWA}}-S_{21}^{\mathrm{Exact}}|`` | $(format_value(maximum(abs.(rwa_s21 .- exact_s21)); digits=6)) |
    | Exact maximum unitarity defect | $(format_value(response_closure.analytical.passivity.exact_max_unitarity_defect; digits=12)) |

    Exact-12 closure status: **$(response_closure.exact_closure_status)**.
    The RWA difference is reported as approximation error, not treated as an
    Exact-``N`` failure.
    """
end

# ╔═╡ 56c3a762-076e-4750-8a5c-209670c18efe
begin
    parameter_scatter_figure(
        [
            "Exact open poles" => (
                x=[
                    real(pole_data.frequencies_hz[index]) / 1e9
                    for index in visible_pole_indices
                ],
                y=[
                    pole_data.linewidths_hz[index] / 1e6
                    for index in visible_pole_indices
                ],
                marker_color="#009E73",
                marker_size=16,
                text=[
                    "κ=$(round(pole_data.linewidths_hz[index] / 1e6; digits=4)) MHz"
                    for index in visible_pole_indices
                ],
                mode="markers+text",
            ),
        ];
        title="Exact Open-Pole Frequencies And Linewidths",
        xaxis_title="Pole frequency (GHz)",
        yaxis_title="Full linewidth κ (MHz)",
        config=figure_config,
        x_range=(frequency_start_ghz, frequency_stop_ghz),
    )
end |> wide_figure_cell

# ╔═╡ 1ae5dd15-dc51-40ae-8553-1d058a3f4afa
exact_n_sanity = (
    finite_exact=all(isfinite, exact_s21),
    finite_rwa=all(isfinite, rwa_s21),
    frequency_ordered=issorted(frequency_hz),
    exact_matches_direct=response_closure.residuals.max_abs_exact_s21 <= 1e-9,
    exact_passive=response_closure.analytical.passivity.exact_max_unitarity_defect <= 1e-9,
)

# ╔═╡ a842311c-5f91-4f7a-a96e-af7cf3cca35f
md"""
## Interpretation boundary

- **Exact-12** retains both the number-conserving block ``\mathbf h`` and the
  pairing block ``\mathbf\Delta`` generated by the same physical-node circuit.
- **RWA-6** drops the pairing sector and is shown only to reveal where that
  approximation changes the response.
- The direct physical-node ``C/K`` trace is not drawn because it closes against
  Exact-12 to numerical precision; its maximum residual is reported above.
- Moving a slider changes one complete Equivalent Circuit candidate and then
  rebuilds every derived matrix. The notebook does not independently tune
  entries of ``\mathbf h`` or ``\mathbf\Delta``.
- This is an interactive diagnostic. It does not promote or overwrite a design
  receipt.
"""

# ╔═╡ Cell order:
# ╠═631fa8d5-acde-4583-ae83-acde6b604baa
# ╠═81517dbe-033b-44af-b32e-4e226b2906ca
# ╟─22e155ea-e5c1-4395-ba84-55137123eaa8
# ╠═2a675bf8-25e0-4541-aa57-7ee294f58cf5
# ╠═036c98e0-1234-49df-afaf-161bc36f8cda
# ╠═bbb0b9de-32e3-47f6-9299-d38c2f02a980
# ╠═c09506cd-510f-4901-bba5-79a679bd2046
# ╟─8a1558ed-6600-4d35-bbc4-d62d1089ef2f
# ╟─c7833984-8a56-4d86-a1fa-ec5d8dc7e17a
# ╟─14ac2465-c6c5-44b9-a2cc-a05340d3895e
# ╟─5735277e-a0a0-40a9-ace7-122dc20edb91
# ╟─56c3a762-076e-4750-8a5c-209670c18efe
# ╠═b8733016-3a46-4198-a36a-6bccbe929d1e
# ╠═1ae5dd15-dc51-40ae-8553-1d058a3f4afa
# ╟─a842311c-5f91-4f7a-a96e-af7cf3cca35f
