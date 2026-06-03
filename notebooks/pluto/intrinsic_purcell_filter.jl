### A Pluto.jl notebook ###
# v1.0.1

using Markdown
using InteractiveUtils

# ╔═╡ 08e970fa-5f21-11f1-ba4c-33ab598452ec
begin
    import Pkg
    Pkg.activate(joinpath(first(DEPOT_PATH), "environments", "v1.12"); io=devnull)

    using Revise
    using PlutoUI
    using SuperconductingCircuitsCore
    using SuperconductingCircuitsVisualizer

    figure_config = PlotlyFigureConfig(
        download_filename=splitext(basename(@__FILE__))[1],
    )

    wide_figure_cell = WideCell(;
        max_width=max(1000, something(figure_config.display_width_px, 1000) + 80),
    )

    include(joinpath(@__DIR__, "includes", "hb_example_helpers.jl"))
    using .HBExampleHelpers: db20, zero_mode_s
end

# ╔═╡ Cell order:
# ╠═08e970fa-5f21-11f1-ba4c-33ab598452ec
