function build_plot(traces, title, xaxis_title, yaxis_title; legend_title="Legend")
    return plot(
        traces,
        Layout(
            title=title,
            xaxis=attr(title=xaxis_title),
            yaxis=attr(title=yaxis_title),
            legend=attr(title=attr(text=legend_title)),
        ),
    )
end
