# Render mobile-readable review figures from the six-physical-variable artifact.
# The response plots deliberately use line style as well as color because the
# Exact-Six and finite Equivalent traces are expected to overlap closely.

import Pkg

const WORKBENCH_ROOT = dirname(dirname(abspath(@__DIR__)))
const CORE_PROJECT = joinpath(WORKBENCH_ROOT, "core", "julia", "SuperconductingCircuitsCore")
const VISUALIZER_PROJECT = joinpath(
    WORKBENCH_ROOT, "core", "julia", "SuperconductingCircuitsVisualizer",
)

Pkg.activate(CORE_PROJECT; io = devnull)
push!(LOAD_PATH, VISUALIZER_PROJECT)

using JSON3
using PlotlyJS
using Printf

const EXACT_COLOR = "#176B87"
const EQUIVALENT_COLOR = "#E17C05"
const DISTRIBUTED_COLOR = "#2A9D5B"
const INK_COLOR = "#263238"
const GRID_COLOR = "#E6E9ED"
const TARGET_COLOR = "#73777B"

complex_values(payload) = complex.(
    Float64.(payload["real"]),
    Float64.(payload["imag"]),
)

function response_figure(slot)
    slot_ghz = Float64(slot["slot_hz"]) / 1.0e9
    frequency_ghz = Float64.(slot["response"]["frequency_hz"]) ./ 1.0e9
    exact = complex_values(slot["exact_six_coordinate_response"]["calibrated_s21"])
    equivalent = complex_values(slot["response"]["calibrated_equivalent_s21"])
    distributed = complex_values(slot["response"]["calibrated_distributed_s21"])
    exact_residual = max.(abs.(exact .- equivalent), 1.0e-12)
    distributed_residual = max.(abs.(distributed .- equivalent), 1.0e-12)
    exact_rmse = Float64(slot["exact_six_coordinate_response"][
        "residual_vs_existing_equivalent"
    ]["calibrated_s21"]["complex_rmse"])
    distributed_rmse = sqrt(sum(abs2, distributed .- equivalent) / length(equivalent))

    figure = make_subplots(
        rows = 3,
        cols = 1,
        shared_xaxes = true,
        vertical_spacing = 0.055,
        row_heights = [0.38, 0.38, 0.24],
    )
    series = (
        (real.(exact), real.(equivalent), real.(distributed), 1),
        (imag.(exact), imag.(equivalent), imag.(distributed), 2),
    )
    for (exact_values, equivalent_values, distributed_values, row) in series
        add_trace!(figure, scatter(
            x = frequency_ghz,
            y = exact_values,
            mode = "lines",
            name = "Exact-Six",
            legendgroup = "exact",
            showlegend = row == 1,
            line = attr(color = EXACT_COLOR, width = 3.0),
        ); row = row, col = 1)
        add_trace!(figure, scatter(
            x = frequency_ghz,
            y = equivalent_values,
            mode = "lines",
            name = "Equivalent",
            legendgroup = "equivalent",
            showlegend = row == 1,
            line = attr(color = EQUIVALENT_COLOR, width = 2.2, dash = "dash"),
        ); row = row, col = 1)
        add_trace!(figure, scatter(
            x = frequency_ghz,
            y = distributed_values,
            mode = "lines",
            name = "Distributed",
            legendgroup = "distributed",
            showlegend = row == 1,
            line = attr(color = DISTRIBUTED_COLOR, width = 2.0, dash = "dot"),
        ); row = row, col = 1)
    end
    add_trace!(figure, scatter(
        x = frequency_ghz,
        y = exact_residual,
        mode = "lines",
        name = "|Exact-Six - Equivalent|",
        legendgroup = "exact_residual",
        showlegend = true,
        line = attr(color = EXACT_COLOR, width = 2.0),
    ); row = 3, col = 1)
    add_trace!(figure, scatter(
        x = frequency_ghz,
        y = distributed_residual,
        mode = "lines",
        name = "|Distributed - Equivalent|",
        legendgroup = "distributed_residual",
        showlegend = true,
        line = attr(color = DISTRIBUTED_COLOR, width = 1.8, dash = "dot"),
    ); row = 3, col = 1)

    loaded_bare = slot["selected"]["coupling_off_loaded_bare"]
    loaded_bare_ghz = [
        Float64(loaded_bare["readout_frequency_hz"]) / 1.0e9,
        Float64(loaded_bare["filter_frequency_hz"]) / 1.0e9,
    ]
    shapes = [attr(
        type = "line",
        x0 = target,
        x1 = target,
        xref = "x",
        y0 = 0,
        y1 = 1,
        yref = "paper",
        line = attr(color = TARGET_COLOR, width = 1.2, dash = "dot"),
    ) for target in loaded_bare_ghz]
    relayout!(figure,
        title = attr(
            text = "$(round(slot_ghz; digits = 2)) GHz Slot: Exact-Six, Equivalent, and Distributed" *
                "<br><sup>Calibrated complex S21 over the full sweep; vertical lines are the " *
                "optimized coupling-off loaded-bare poles; RMSE Exact/Equivalent=" *
                "$(round(exact_rmse; sigdigits = 4)), Distributed/Equivalent=" *
                "$(round(distributed_rmse; sigdigits = 4))</sup>",
            x = 0.02,
            xanchor = "left",
        ),
        template = "plotly_white",
        paper_bgcolor = "white",
        plot_bgcolor = "white",
        font = attr(family = "Arial, sans-serif", color = INK_COLOR, size = 16),
        legend = attr(
            orientation = "h",
            x = 0.5,
            xanchor = "center",
            y = 1.03,
            yanchor = "bottom",
        ),
        margin = attr(l = 105, r = 40, t = 145, b = 90),
        shapes = shapes,
        xaxis3 = attr(
            title = "Frequency (GHz)",
            gridcolor = GRID_COLOR,
            showline = true,
            linecolor = INK_COLOR,
        ),
        yaxis = attr(
            title = "Real(S21)",
            gridcolor = GRID_COLOR,
            showline = true,
            linecolor = INK_COLOR,
        ),
        yaxis2 = attr(
            title = "Imag(S21)",
            gridcolor = GRID_COLOR,
            showline = true,
            linecolor = INK_COLOR,
        ),
        yaxis3 = attr(
            title = "|Complex residual vs Equivalent|",
            type = "log",
            gridcolor = GRID_COLOR,
            showline = true,
            linecolor = INK_COLOR,
        ),
    )
    return figure
end

function in_band_poles(slot)
    slot_hz = Float64(slot["slot_hz"])
    poles = filter(slot["exact_six_coordinate_response"]["open_poles"]) do pole
        abs(Float64(pole["frequency_hz"]) - slot_hz) < 0.2e9
    end
    sort!(poles; by = pole -> Float64(pole["frequency_hz"]))
    length(poles) == 2 || error("Expected two Exact-Six resonator-band open poles.")
    return poles
end

function linewidth_figure(slots)
    slot_labels = ["$(round(Float64(slot["slot_hz"]) / 1.0e9; digits = 2))" for slot in slots]
    poles = in_band_poles.(slots)
    lower = [Float64(pair[1]["linewidth_hz"]) / 1.0e6 for pair in poles]
    upper = [Float64(pair[2]["linewidth_hz"]) / 1.0e6 for pair in poles]
    figure = Plot([
        bar(
            x = slot_labels,
            y = lower,
            name = "Lower-frequency open pole",
            marker = attr(color = EXACT_COLOR, line = attr(color = INK_COLOR, width = 0.6)),
        ),
        bar(
            x = slot_labels,
            y = upper,
            name = "Upper-frequency open pole",
            marker = attr(color = EQUIVALENT_COLOR, line = attr(color = INK_COLOR, width = 0.6)),
        ),
    ], Layout(
        title = attr(
            text = "Exact-Six Resonator-Band Open-Pole Linewidth Shares" *
                "<br><sup>Coupling-Off kappa_p,LB = 10 MHz; accepted 30/70 band is 3-7 MHz per pole</sup>",
            x = 0.02,
            xanchor = "left",
        ),
        template = "plotly_white",
        barmode = "group",
        paper_bgcolor = "white",
        plot_bgcolor = "white",
        font = attr(family = "Arial, sans-serif", color = INK_COLOR, size = 17),
        margin = attr(l = 100, r = 45, t = 130, b = 90),
        legend = attr(orientation = "h", x = 0.5, xanchor = "center", y = 1.02),
        xaxis = attr(
            title = "Slot target (GHz)",
            showline = true,
            linecolor = INK_COLOR,
        ),
        yaxis = attr(
            title = "Open-pole linewidth (MHz)",
            range = [0, 10.8],
            gridcolor = GRID_COLOR,
            showline = true,
            linecolor = INK_COLOR,
        ),
        shapes = [attr(
            type = "line", x0 = first(slot_labels), x1 = last(slot_labels), xref = "x",
            y0 = boundary, y1 = boundary, yref = "y",
            line = attr(color = TARGET_COLOR, width = 1.8, dash = "dot"),
        ) for boundary in (3.0, 7.0)],
    ))
    return figure
end

function main(arguments)
    length(arguments) == 1 || error("Usage: julia plot_d3_six_physical_review.jl REVIEW_JSON")
    review_path = abspath(only(arguments))
    artifact = JSON3.read(read(review_path, String), Dict{String,Any})
    slots = sort(artifact["slots"]; by = slot -> Float64(slot["slot_hz"]))
    output = joinpath(dirname(review_path), "figures")
    mkpath(output)
    for slot in slots
        slot_tag = replace(
            @sprintf("%.2f", Float64(slot["slot_hz"]) / 1.0e9),
            "." => "p",
        )
        savefig(
            response_figure(slot),
            joinpath(output, "exact_six_equivalent_distributed_$(slot_tag)GHz.png");
            width = 1280,
            height = 1080,
            scale = 1.5,
        )
    end
    savefig(
        linewidth_figure(slots),
        joinpath(output, "exact_six_open_pole_linewidths.png");
        width = 1280,
        height = 820,
        scale = 1.5,
    )
    println(output)
end

abspath(PROGRAM_FILE) == abspath(@__FILE__) && main(ARGS)
