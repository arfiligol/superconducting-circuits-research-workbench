function build_plot(traces, title, xaxis_title, yaxis_title; legend_title="Legend")
    @eval using PlotlyJS
    return PlotlyJS.plot(
        traces,
        PlotlyJS.Layout(
            title=title,
            xaxis=PlotlyJS.attr(title=xaxis_title),
            yaxis=PlotlyJS.attr(title=yaxis_title),
            legend=PlotlyJS.attr(title=PlotlyJS.attr(text=legend_title)),
        ),
    )
end
