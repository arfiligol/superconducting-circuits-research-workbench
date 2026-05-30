module SuperconductingCircuitsVisualizer

using PlotlyJS

export PlotlyFigureConfig,
    default_layout,
    frequency_ghz,
    multi_curve_figure,
    plotly_display_config,
    s_parameter_magnitude_figure,
    s_parameter_phase_figure,
    unwrap_phase_trace,
    y_trace_figure,
    z_trace_figure

const DEFAULT_FONT_FAMILY = "Arial, Helvetica, sans-serif"
const DEFAULT_COLORS = (
    "#0072B2",
    "#D55E00",
    "#009E73",
    "#CC79A7",
    "#E69F00",
    "#56B4E9",
    "#4B5563",
)

Base.@kwdef struct PlotlyFigureConfig
    display_width_px::Union{Nothing,Int} = 1200
    display_height_px::Union{Nothing,Int} = 780
    download_width_px::Int = 1200
    download_height_px::Int = 780
    download_scale::Int = 3
    download_format::String = "png"
    download_filename::String = "superconducting_circuits_plot"
    font_family::String = DEFAULT_FONT_FAMILY
    font_scale::Float64 = 1.0
    title_font_size_px::Int = 30
    axis_title_font_size_px::Int = 26
    tick_font_size_px::Int = 21
    legend_font_size_px::Int = 20
    axis_title_standoff_px::Int = 14
    line_width_px::Float64 = 2.4
    marker_size_px::Int = 10
    margin_left_px::Int = 95
    margin_right_px::Int = 340
    margin_top_px::Int = 110
    margin_bottom_px::Int = 85
    legend_orientation::String = "v"
    legend_x::Float64 = 1.02
    legend_y::Float64 = 1.0
    show_x_grid::Bool = false
    show_y_grid::Bool = true
    x_range_ghz::Any = nothing
    y_range::Any = nothing
    text_color::String = "#111827"
    grid_color::String = "#E5E7EB"
    axis_line_color::String = "#111827"
    background_color::String = "#FFFFFF"
    colors::Any = DEFAULT_COLORS
    display_mode_bar::Bool = true
    display_logo::Bool = false
    responsive::Bool = true
end

function _scaled_size(config::PlotlyFigureConfig, base_size::Integer)
    config.font_scale > 0 || throw(ArgumentError("font_scale must be positive."))
    return max(1, round(Int, base_size * config.font_scale))
end

function _positive_integer(value::Integer, name::AbstractString)
    value > 0 || throw(ArgumentError("$(name) must be positive."))
    return Int(value)
end

function _optional_positive_integer(value::Union{Nothing,Integer}, name::AbstractString)
    isnothing(value) && return nothing
    return _positive_integer(value, name)
end

function _range_vector(value, name::AbstractString)
    isnothing(value) && return nothing
    values = collect(value)
    length(values) == 2 || throw(ArgumentError("$(name) must contain exactly two values."))
    lower, upper = Float64(values[1]), Float64(values[2])
    lower < upper || throw(ArgumentError("$(name) lower bound must be less than upper bound."))
    return [lower, upper]
end

function _effective_range(call_range, config_range, name::AbstractString)
    return _range_vector(isnothing(call_range) ? config_range : call_range, name)
end

function _font(config::PlotlyFigureConfig, size::Integer)
    return Dict(
        :family => config.font_family,
        :size => _scaled_size(config, size),
        :color => config.text_color,
    )
end

function _axis_kwargs(config::PlotlyFigureConfig; title, showgrid::Bool, range=nothing)
    axis = Dict{Symbol,Any}(
        :title => Dict(
            :text => title,
            :font => _font(config, config.axis_title_font_size_px),
            :standoff => config.axis_title_standoff_px,
        ),
        :tickfont => _font(config, config.tick_font_size_px),
        :showgrid => showgrid,
        :gridcolor => config.grid_color,
        :gridwidth => 1,
        :zeroline => false,
        :showline => true,
        :linecolor => config.axis_line_color,
        :linewidth => 1,
        :mirror => true,
        :ticks => "outside",
        :tickcolor => config.axis_line_color,
    )
    if !isnothing(range)
        axis[:range] = range
    end
    return axis
end

function default_layout(;
    title,
    xaxis_title,
    yaxis_title,
    config::PlotlyFigureConfig=PlotlyFigureConfig(),
    x_range_ghz=nothing,
    y_range=nothing,
)
    display_width = _optional_positive_integer(config.display_width_px, "display_width_px")
    display_height = _optional_positive_integer(config.display_height_px, "display_height_px")
    x_range = _effective_range(x_range_ghz, config.x_range_ghz, "x_range_ghz")
    y_axis_range = _effective_range(y_range, config.y_range, "y_range")

    layout = Dict{Symbol,Any}(
        :title => Dict(
            :text => title,
            :x => 0.01,
            :xanchor => "left",
            :font => _font(config, config.title_font_size_px),
        ),
        :xaxis => _axis_kwargs(config; title=xaxis_title, showgrid=config.show_x_grid, range=x_range),
        :yaxis => _axis_kwargs(config; title=yaxis_title, showgrid=config.show_y_grid, range=y_axis_range),
        :font => _font(config, config.tick_font_size_px),
        :legend => Dict(
            :orientation => config.legend_orientation,
            :x => config.legend_x,
            :xanchor => "left",
            :y => config.legend_y,
            :yanchor => "top",
            :font => _font(config, config.legend_font_size_px),
        ),
        :margin => Dict(
            :l => config.margin_left_px,
            :r => config.margin_right_px,
            :t => config.margin_top_px,
            :b => config.margin_bottom_px,
        ),
        :template => "plotly_white",
        :hovermode => "closest",
        :paper_bgcolor => config.background_color,
        :plot_bgcolor => config.background_color,
    )
    !isnothing(display_width) && (layout[:width] = display_width)
    !isnothing(display_height) && (layout[:height] = display_height)

    return Layout(; layout...)
end

function plotly_display_config(config::PlotlyFigureConfig=PlotlyFigureConfig())
    return PlotConfig(
        displayModeBar=config.display_mode_bar,
        displaylogo=config.display_logo,
        responsive=config.responsive,
        toImageButtonOptions=Dict(
            :format => config.download_format,
            :filename => config.download_filename,
            :width => _positive_integer(config.download_width_px, "download_width_px"),
            :height => _positive_integer(config.download_height_px, "download_height_px"),
            :scale => _positive_integer(config.download_scale, "download_scale"),
        ),
    )
end

frequency_ghz(frequencies_hz) = collect(Float64.(frequencies_hz)) ./ 1e9

function _named_pairs(named_traces)
    pairs = collect(named_traces)
    isempty(pairs) && throw(ArgumentError("named traces must contain at least one trace."))
    return pairs
end

_trace_name(pair) = string(first(pair))
_trace_values(pair) = collect(last(pair))

function _trace_color(config::PlotlyFigureConfig, index::Integer)
    isempty(config.colors) && return "#4B5563"
    return config.colors[mod1(index, length(config.colors))]
end

function _line_trace(x, y, name::AbstractString, index::Integer, config::PlotlyFigureConfig; mode="lines")
    length(x) == length(y) || throw(ArgumentError("Trace '$(name)' length $(length(y)) does not match frequency length $(length(x))."))
    color = _trace_color(config, index)
    return scatter(
        x=x,
        y=collect(y),
        mode=mode,
        name=name,
        line=attr(color=color, width=config.line_width_px),
        marker=attr(color=color, size=config.marker_size_px),
    )
end

function multi_curve_figure(
    frequencies_hz,
    curves;
    title,
    yaxis_title,
    xaxis_title="Frequency (GHz)",
    mode="lines",
    config::PlotlyFigureConfig=PlotlyFigureConfig(),
    x_range_ghz=nothing,
    y_range=nothing,
)
    x = frequency_ghz(frequencies_hz)
    curve_pairs = _named_pairs(curves)
    traces = [
        _line_trace(x, _trace_values(pair), _trace_name(pair), index, config; mode=mode)
        for (index, pair) in enumerate(curve_pairs)
    ]

    return Plot(
        traces,
        default_layout(
            title=title,
            xaxis_title=xaxis_title,
            yaxis_title=yaxis_title,
            config=config,
            x_range_ghz=x_range_ghz,
            y_range=y_range,
        );
        config=plotly_display_config(config),
    )
end

function _db20(values)
    return 20 .* log10.(abs.(values))
end

function s_parameter_magnitude_figure(
    frequencies_hz,
    named_traces;
    title,
    config::PlotlyFigureConfig=PlotlyFigureConfig(),
    x_range_ghz=nothing,
    y_range=nothing,
)
    curves = [_trace_name(pair) => _db20(_trace_values(pair)) for pair in _named_pairs(named_traces)]
    return multi_curve_figure(
        frequencies_hz,
        curves;
        title=title,
        yaxis_title="Magnitude (dB)",
        config=config,
        x_range_ghz=x_range_ghz,
        y_range=y_range,
    )
end

function _phase_values(values, unit::Symbol)
    phase_rad = angle.(values)
    unit == :rad && return phase_rad
    unit == :deg && return rad2deg.(phase_rad)
    throw(ArgumentError("phase unit must be :deg or :rad."))
end

function s_parameter_phase_figure(
    frequencies_hz,
    named_traces;
    title,
    unit::Symbol=:deg,
    config::PlotlyFigureConfig=PlotlyFigureConfig(),
    x_range_ghz=nothing,
    y_range=nothing,
)
    curves = [_trace_name(pair) => _phase_values(_trace_values(pair), unit) for pair in _named_pairs(named_traces)]
    yaxis_title = unit == :rad ? "Phase (rad)" : unit == :deg ? "Phase (deg)" : throw(ArgumentError("phase unit must be :deg or :rad."))
    return multi_curve_figure(
        frequencies_hz,
        curves;
        title=title,
        yaxis_title=yaxis_title,
        config=config,
        x_range_ghz=x_range_ghz,
        y_range=y_range,
    )
end

function _phase_input_to_radians(values, unit::Symbol)
    collected = collect(values)
    if eltype(collected) <: Complex
        return angle.(collected)
    elseif unit == :deg
        return deg2rad.(Float64.(collected))
    elseif unit == :rad
        return Float64.(collected)
    end
    throw(ArgumentError("phase unit must be :deg or :rad."))
end

function _unwrap_radians(phase_rad)
    values = collect(Float64.(phase_rad))
    isempty(values) && return values
    unwrapped = similar(values)
    unwrapped[1] = values[1]
    offset = 0.0
    previous = values[1]
    for index in 2:length(values)
        delta = values[index] - previous
        if delta > π
            offset -= 2π
        elseif delta < -π
            offset += 2π
        end
        unwrapped[index] = values[index] + offset
        previous = values[index]
    end
    return unwrapped
end

function unwrap_phase_trace(values; unit::Symbol=:deg)
    unwrapped = _unwrap_radians(_phase_input_to_radians(values, unit))
    unit == :rad && return unwrapped
    unit == :deg && return rad2deg.(unwrapped)
    throw(ArgumentError("phase unit must be :deg or :rad."))
end

function _complex_component_curves(named_traces, prefix::AbstractString)
    curves = Pair{String,Vector{Float64}}[]
    for pair in _named_pairs(named_traces)
        name = _trace_name(pair)
        values = _trace_values(pair)
        push!(curves, "real($(name))" => Float64.(real.(values)))
        push!(curves, "imag($(name))" => Float64.(imag.(values)))
    end
    isempty(curves) && throw(ArgumentError("$(prefix) traces must contain at least one trace."))
    return curves
end

function z_trace_figure(
    frequencies_hz,
    named_z_traces;
    title,
    config::PlotlyFigureConfig=PlotlyFigureConfig(),
    x_range_ghz=nothing,
    y_range=nothing,
)
    return multi_curve_figure(
        frequencies_hz,
        _complex_component_curves(named_z_traces, "Z");
        title=title,
        yaxis_title="Impedance (ohm)",
        config=config,
        x_range_ghz=x_range_ghz,
        y_range=y_range,
    )
end

function y_trace_figure(
    frequencies_hz,
    named_y_traces;
    title,
    config::PlotlyFigureConfig=PlotlyFigureConfig(),
    x_range_ghz=nothing,
    y_range=nothing,
)
    return multi_curve_figure(
        frequencies_hz,
        _complex_component_curves(named_y_traces, "Y");
        title=title,
        yaxis_title="Admittance (S)",
        config=config,
        x_range_ghz=x_range_ghz,
        y_range=y_range,
    )
end

end
