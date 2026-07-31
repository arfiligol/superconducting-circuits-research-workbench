### A Pluto.jl notebook ###
# v1.0.2

#> [frontmatter]
#> title = "Two-Mode Non-Hermitian Pole Explorer"
#> tags = ["pluto", "non-hermitian", "coupled-modes", "linewidth"]
#> description = "Interactive analytical explorer for two coupled open resonators, their complex poles, and linewidth sharing."

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

# ╔═╡ 4eb8da56-246a-4f8c-91fa-2ce3ed34c1e1
begin
    import Pkg
    Pkg.activate(joinpath(first(DEPOT_PATH), "environments", "v1.12"); io=devnull)

    using PlutoUI
    using SuperconductingCircuitsVisualizer

    PlotlyJS = SuperconductingCircuitsVisualizer.PlotlyJS
    figure_config = PlotlyFigureConfig(
        display_height_px=620,
        download_filename=splitext(basename(@__FILE__))[1],
    )
    wide_figure_cell = WideCell(;
        max_width=max(1000, something(figure_config.display_width_px, 1000) + 80),
    )
end

# ╔═╡ 684691d8-80ae-4da5-ba2f-009855db10f7
TableOfContents()

# ╔═╡ 4745a468-a2d3-46ed-af74-03ec76087175
md"""
# Two-Mode Non-Hermitian Pole Explorer

This notebook evaluates the analytical open poles of a readout resonator ``r``
coherently coupled to a lossy filter resonator ``p``:

```math
\mathbf H_{\mathrm{eff}}=
\begin{pmatrix}
f_r-i\kappa_r/2 & J\\
J & f_p-i\kappa_p/2
\end{pmatrix}.
```

All entries in the calculation use ordinary-frequency units after division by
``2\pi``: frequencies, ``J``, and ``\kappa`` are expressed in MHz, except for
the displayed center frequency in GHz.

The reusable interpretation is owned by
[Resonator Decay, Linewidth, and Quality Factor](https://github.com/arfiligol/SCQ_Design/blob/main/docs/knowledge/network-modeling/resonator-decay-linewidth-and-quality-factor.qmd)
and the
[D3 Full-QRP Complex Response Fit](https://github.com/arfiligol/SCQ_Design/blob/main/docs/knowledge/worked-examples/d3-full-qrp-complex-response-fit.qmd).
This notebook is an analytical diagnostic, not a D3 promotion artifact.
"""

# ╔═╡ d1c29efe-e323-4785-ae30-872a5164b886
md"""
## Analytical solution

With

```math
\delta=f_r-f_p,
\qquad
\Delta\kappa=\kappa_r-\kappa_p,
```

the two poles are

```math
\widetilde f_\pm
=
\frac{f_r+f_p}{2}
-i\frac{\kappa_r+\kappa_p}{4}
\pm
\sqrt{
J^2+
\left(
\frac{\delta}{2}
-i\frac{\Delta\kappa}{4}
\right)^2
},
```

and their positive full linewidths are

```math
\kappa_\pm=-2\,\operatorname{Im}\widetilde f_\pm.
```
"""

# ╔═╡ 1371276f-ab3f-4ceb-9a36-1110e3becf83
begin
    # Edit these ranges, then use the sliders in the next cell.
    parameter_ranges = (
        center_frequency_ghz=5.50:0.01:6.50,
        detuning_mhz=-20.0:0.1:20.0,
        coupling_mhz=0.0:0.1:40.0,
        kappa_r_mhz=0.0:0.1:40.0,
        kappa_p_mhz=0.0:0.1:40.0,
    )
end

# ╔═╡ 60a025d2-4672-44dc-b97a-8c99cec3c72d
function two_mode_open_poles(
    center_frequency_ghz,
    detuning_mhz,
    coupling_mhz,
    kappa_r_mhz,
    kappa_p_mhz,
)
    center_mhz = 1000.0 * center_frequency_ghz
    delta_kappa_mhz = kappa_r_mhz - kappa_p_mhz
    discriminant = complex(
        coupling_mhz^2 +
        (detuning_mhz / 2 - im * delta_kappa_mhz / 4)^2,
    )
    root = sqrt(discriminant)
    mean_pole = center_mhz - im * (kappa_r_mhz + kappa_p_mhz) / 4
    poles_mhz = (minus=mean_pole - root, plus=mean_pole + root)
    linewidths_mhz = (
        minus=-2 * imag(poles_mhz.minus),
        plus=-2 * imag(poles_mhz.plus),
    )
    total_linewidth_mhz = linewidths_mhz.minus + linewidths_mhz.plus
    shares = if total_linewidth_mhz > 0
        (
            minus=linewidths_mhz.minus / total_linewidth_mhz,
            plus=linewidths_mhz.plus / total_linewidth_mhz,
        )
    else
        (minus=NaN, plus=NaN)
    end

    return (
        f_r_mhz=center_mhz + detuning_mhz / 2,
        f_p_mhz=center_mhz - detuning_mhz / 2,
        delta_kappa_mhz=delta_kappa_mhz,
        zero_detuning_ep_mhz=abs(delta_kappa_mhz) / 4,
        poles_mhz=poles_mhz,
        linewidths_mhz=linewidths_mhz,
        total_linewidth_mhz=total_linewidth_mhz,
        shares=shares,
        gate_30_70=(
            isfinite(shares.minus) &&
            min(shares.minus, shares.plus) >= 0.30
        ),
        passive=(
            linewidths_mhz.minus >= -1e-10 &&
            linewidths_mhz.plus >= -1e-10
        ),
    )
end

# ╔═╡ 30c14c0d-9823-4326-82da-e01208f7266f
begin
    control_panel = PlutoUI.ExperimentalLayout.Div(
        [
            md"""**Center frequency (GHz)**  
            $(@bind center_frequency_ghz Slider(parameter_ranges.center_frequency_ghz; default=6.00, show_value=true))""",
            md"""**Detuning ``\delta`` (MHz)**  
            $(@bind detuning_mhz Slider(parameter_ranges.detuning_mhz; default=-4.0, show_value=true))""",
            md"""**Coupling ``J`` (MHz)**  
            $(@bind coupling_mhz Slider(parameter_ranges.coupling_mhz; default=5.0, show_value=true))""",
            md"""**Readout linewidth ``\kappa_r`` (MHz)**  
            $(@bind kappa_r_mhz Slider(parameter_ranges.kappa_r_mhz; default=0.0, show_value=true))""",
            md"""**Filter linewidth ``\kappa_p`` (MHz)**  
            $(@bind kappa_p_mhz Slider(parameter_ranges.kappa_p_mhz; default=20.0, show_value=true))""",
            md"""**Horizontal sweep**  
            $(@bind scan_parameter Select(["coupling_mhz" => "J", "detuning_mhz" => "δ"]; default="coupling_mhz"))""",
        ];
        style=Dict(
            "display" => "grid",
            "grid-template-columns" => "repeat(auto-fit, minmax(240px, 1fr))",
            "gap" => "0.75rem 1.5rem",
            "align-items" => "end",
        ),
    )
end |> wide_figure_cell

# ╔═╡ 2538e3b1-3f26-42cb-854a-c6153152c953
current = two_mode_open_poles(
    center_frequency_ghz,
    detuning_mhz,
    coupling_mhz,
    kappa_r_mhz,
    kappa_p_mhz,
)

# ╔═╡ 0a7af8ba-7d55-484e-9ea5-0f8e690f82b4
begin
    scan_values = collect(getproperty(parameter_ranges, Symbol(scan_parameter)))
    scan_results = [
        two_mode_open_poles(
            center_frequency_ghz,
            scan_parameter == "detuning_mhz" ? value : detuning_mhz,
            scan_parameter == "coupling_mhz" ? value : coupling_mhz,
            kappa_r_mhz,
            kappa_p_mhz,
        )
        for value in scan_values
    ]
    current_scan_value = scan_parameter == "coupling_mhz" ?
        coupling_mhz :
        detuning_mhz
    scan_label = scan_parameter == "coupling_mhz" ? "J (MHz)" : "δ (MHz)"
end

# ╔═╡ d8b87055-906d-4017-bbb7-1771c51c1fbb
begin
    frequency_minus = [
        real(result.poles_mhz.minus) - 1000 * center_frequency_ghz
        for result in scan_results
    ]
    frequency_plus = [
        real(result.poles_mhz.plus) - 1000 * center_frequency_ghz
        for result in scan_results
    ]
    linewidth_minus = [result.linewidths_mhz.minus for result in scan_results]
    linewidth_plus = [result.linewidths_mhz.plus for result in scan_results]
    linewidth_floor = 0.30 * current.total_linewidth_mhz
    linewidth_ceiling = 0.70 * current.total_linewidth_mhz

    PlotlyJS.Plot(
        [
            PlotlyJS.scatter(
                x=scan_values,
                y=frequency_minus,
                mode="lines",
                name="Re(f̃₋) - center",
                line=PlotlyJS.attr(color="#0072B2", width=3),
                hovertemplate="%{x:.3f}<br>frequency offset=%{y:.6f} MHz<extra></extra>",
            ),
            PlotlyJS.scatter(
                x=scan_values,
                y=frequency_plus,
                mode="lines",
                name="Re(f̃₊) - center",
                line=PlotlyJS.attr(color="#D55E00", width=3),
                hovertemplate="%{x:.3f}<br>frequency offset=%{y:.6f} MHz<extra></extra>",
            ),
            PlotlyJS.scatter(
                x=scan_values,
                y=linewidth_minus,
                mode="lines",
                name="κ₋",
                yaxis="y2",
                line=PlotlyJS.attr(color="#56B4E9", width=2, dash="dash"),
                hovertemplate="%{x:.3f}<br>κ₋=%{y:.6f} MHz<extra></extra>",
            ),
            PlotlyJS.scatter(
                x=scan_values,
                y=linewidth_plus,
                mode="lines",
                name="κ₊",
                yaxis="y2",
                line=PlotlyJS.attr(color="#E69F00", width=2, dash="dash"),
                hovertemplate="%{x:.3f}<br>κ₊=%{y:.6f} MHz<extra></extra>",
            ),
        ],
        PlotlyJS.Layout(
            autosize=true,
            height=something(figure_config.display_height_px, 620),
            title="Two-Mode Complex Poles And Linewidth Sharing",
            xaxis=PlotlyJS.attr(title=scan_label),
            yaxis=PlotlyJS.attr(title="Pole frequency offset from center (MHz)"),
            yaxis2=PlotlyJS.attr(
                title="Pole linewidth κ (MHz)",
                overlaying="y",
                side="right",
                rangemode="tozero",
            ),
            legend=PlotlyJS.attr(orientation="h", y=-0.20),
            margin=PlotlyJS.attr(l=80, r=90, t=70, b=110),
            shapes=[
                PlotlyJS.attr(
                    type="rect",
                    xref="x",
                    yref="y2",
                    x0=first(scan_values),
                    x1=last(scan_values),
                    y0=linewidth_floor,
                    y1=linewidth_ceiling,
                    fillcolor="rgba(0, 158, 115, 0.10)",
                    line=PlotlyJS.attr(width=0),
                    layer="below",
                ),
                PlotlyJS.attr(
                    type="line",
                    xref="x",
                    yref="paper",
                    x0=current_scan_value,
                    x1=current_scan_value,
                    y0=0,
                    y1=1,
                    line=PlotlyJS.attr(color="#CC79A7", width=2, dash="dot"),
                ),
            ],
        ),
        config=PlotlyJS.PlotConfig(
            responsive=true,
            toImageButtonOptions=Dict(
                "filename" => figure_config.download_filename,
            ),
        ),
    )
end |> wide_figure_cell

# ╔═╡ 412542e4-5eb4-453f-b4b5-a3b29a1a5d7c
begin
    display_number(value; digits=6) = isfinite(value) ?
        string(round(value; digits=digits)) :
        "undefined"

    gate_label = current.gate_30_70 ? "PASS" : "FAIL"
    passivity_label = current.passive ? "passive" : "negative linewidth"

    md"""
    ## Current poles and linewidths

    | Quantity | Minus pole | Plus pole |
    |---|---:|---:|
    | ``\operatorname{Re}\widetilde f_\pm`` (GHz) | $(display_number(real(current.poles_mhz.minus) / 1000; digits=9)) | $(display_number(real(current.poles_mhz.plus) / 1000; digits=9)) |
    | ``\operatorname{Im}\widetilde f_\pm`` (MHz) | $(display_number(imag(current.poles_mhz.minus))) | $(display_number(imag(current.poles_mhz.plus))) |
    | ``\kappa_\pm=-2\operatorname{Im}\widetilde f_\pm`` (MHz) | $(display_number(current.linewidths_mhz.minus)) | $(display_number(current.linewidths_mhz.plus)) |
    | Linewidth share | $(display_number(100 * current.shares.minus; digits=3))% | $(display_number(100 * current.shares.plus; digits=3))% |

    Loaded-bare frequencies:
    ``f_r=$(display_number(current.f_r_mhz / 1000; digits=9))`` GHz and
    ``f_p=$(display_number(current.f_p_mhz / 1000; digits=9))`` GHz.

    Zero-detuning exceptional-point scale:
    ``|\Delta\kappa|/4=$(display_number(current.zero_detuning_ep_mhz; digits=3))`` MHz.

    **30/70 gate: $(gate_label). Open-system check: $(passivity_label).**
    """
end

# ╔═╡ 5cfe06b7-5829-4b48-bd04-8a61e240a0e4
sanity = (
    pole_trace= isapprox(
        current.poles_mhz.minus + current.poles_mhz.plus,
        2000 * center_frequency_ghz -
        im * (kappa_r_mhz + kappa_p_mhz) / 2;
        atol=1e-10,
    ),
    linewidth_sum=isapprox(
        current.total_linewidth_mhz,
        kappa_r_mhz + kappa_p_mhz;
        atol=1e-10,
    ),
    finite_scan=all(
        result -> (
            isfinite(result.poles_mhz.minus) &&
            isfinite(result.poles_mhz.plus)
        ),
        scan_results,
    ),
)

# ╔═╡ f52289c1-a71e-4f56-909a-f2e146ba5558
md"""
## Interpretation boundary

- The shaded region is the 30/70 linewidth gate: both ``\kappa_-`` and
  ``\kappa_+`` must lie between 30% and 70% of their fixed sum.
- The vertical dotted line is the current slider value.
- Equal linewidths do not by themselves prove two distinct, well-resolved
  modes; inspect the real pole splitting too.
- This two-mode model omits the qubit, feedline coordinates,
  frequency-dependent self-energy, and dissipative off-diagonal coupling.
- A complete ``S_{21}`` trace additionally requires port input/output
  projections, residues, and the direct path. Those quantities are not
  invented here.
"""

# ╔═╡ Cell order:
# ╠═4eb8da56-246a-4f8c-91fa-2ce3ed34c1e1
# ╠═684691d8-80ae-4da5-ba2f-009855db10f7
# ╟─4745a468-a2d3-46ed-af74-03ec76087175
# ╟─d1c29efe-e323-4785-ae30-872a5164b886
# ╠═1371276f-ab3f-4ceb-9a36-1110e3becf83
# ╠═60a025d2-4672-44dc-b97a-8c99cec3c72d
# ╠═2538e3b1-3f26-42cb-854a-c6153152c953
# ╠═0a7af8ba-7d55-484e-9ea5-0f8e690f82b4
# ╟─30c14c0d-9823-4326-82da-e01208f7266f
# ╟─d8b87055-906d-4017-bbb7-1771c51c1fbb
# ╠═412542e4-5eb4-453f-b4b5-a3b29a1a5d7c
# ╠═5cfe06b7-5829-4b48-bd04-8a61e240a0e4
# ╟─f52289c1-a71e-4f56-909a-f2e146ba5558
