using SuperconductingCircuitsVisualizer
using Test

function layout_fields(plot)
    return getfield(plot.layout, :fields)
end

function trace_fields(plot, index::Integer)
    return getfield(plot.data[index], :fields)
end

@testset "PlotlyFigureConfig" begin
    config = PlotlyFigureConfig()
    @test config.display_width_px == 1200
    @test config.display_height_px == 780

    custom = PlotlyFigureConfig(
        download_width_px=1800,
        download_height_px=1000,
        download_scale=4,
        download_filename="custom_export",
    )
    display_config = plotly_display_config(custom)
    @test display_config.displayModeBar
    @test !display_config.displaylogo
    @test display_config.toImageButtonOptions[:width] == 1800
    @test display_config.toImageButtonOptions[:height] == 1000
    @test display_config.toImageButtonOptions[:scale] == 4
    @test display_config.toImageButtonOptions[:filename] == "custom_export"
end

@testset "layout ranges and font scale" begin
    config = PlotlyFigureConfig(font_scale=1.5, x_range_ghz=(4.0, 5.0), y_range=(0.0, 1.0))
    layout = default_layout(
        title="Scaled Layout",
        xaxis_title="Frequency (GHz)",
        yaxis_title="Magnitude",
        config=config,
    )
    fields = getfield(layout, :fields)
    @test fields[:width] == 1200
    @test fields[:height] == 780
    @test fields[:xaxis][:range] == [4.0, 5.0]
    @test fields[:yaxis][:range] == [0.0, 1.0]
    @test fields[:title][:font][:size] == 45
    @test fields[:xaxis][:title][:font][:size] == 39
    @test fields[:xaxis][:tickfont][:size] == 32
    @test fields[:legend][:font][:size] == 30
end

@testset "S-parameter figures" begin
    frequencies = [4.0e9, 4.5e9, 5.0e9]
    s11 = ComplexF64[1 + 0im, 0.5 + 0im, 0 - 1im]

    db_magnitude = s_parameter_db_magnitude_figure(
        frequencies,
        ["S11" => s11];
        title="S magnitude",
        y_range=(-40.0, 1.0),
    )
    @test length(db_magnitude.data) == 1
    @test trace_fields(db_magnitude, 1)[:name] == "S11"
    @test trace_fields(db_magnitude, 1)[:y] ≈ [0.0, -6.020599913279624, 0.0]
    @test layout_fields(db_magnitude)[:yaxis][:title][:text] == "Magnitude (dB)"
    @test layout_fields(db_magnitude)[:yaxis][:range] == [-40.0, 1.0]

    abs_magnitude = s_parameter_abs_magnitude_figure(
        frequencies,
        ["S11" => s11];
        title="S abs",
        y_range=(0.0, 1.0),
    )
    @test length(abs_magnitude.data) == 1
    @test trace_fields(abs_magnitude, 1)[:name] == "S11"
    @test trace_fields(abs_magnitude, 1)[:y] ≈ [1.0, 0.5, 1.0]
    @test layout_fields(abs_magnitude)[:yaxis][:title][:text] == "|Magnitude|"
    @test layout_fields(abs_magnitude)[:yaxis][:range] == [0.0, 1.0]

    phase_deg = s_parameter_phase_figure(frequencies, ["S11" => s11]; title="S phase deg", unit=:deg)
    @test trace_fields(phase_deg, 1)[:y] ≈ [0.0, 0.0, -90.0]
    @test layout_fields(phase_deg)[:yaxis][:title][:text] == "Phase (deg)"

    phase_rad = s_parameter_phase_figure(frequencies, ["S11" => s11]; title="S phase rad", unit=:rad)
    @test trace_fields(phase_rad, 1)[:y] ≈ [0.0, 0.0, -π / 2]
    @test layout_fields(phase_rad)[:yaxis][:title][:text] == "Phase (rad)"
end

@testset "phase unwrap helper" begin
    wrapped_deg = [170.0, -170.0, -160.0]
    @test unwrap_phase_trace(wrapped_deg; unit=:deg) ≈ [170.0, 190.0, 200.0]

    complex_trace = cis.(deg2rad.([170.0, -170.0, -160.0]))
    @test unwrap_phase_trace(complex_trace; unit=:deg) ≈ [170.0, 190.0, 200.0]

    wrapped_rad = deg2rad.([170.0, -170.0, -160.0])
    @test unwrap_phase_trace(wrapped_rad; unit=:rad) ≈ deg2rad.([170.0, 190.0, 200.0])
end

@testset "Z and Y real-imag traces" begin
    frequencies = [4.0e9, 5.0e9]
    z11 = ComplexF64[50 + 1im, 55 - 2im]
    y11 = ComplexF64[0.02 - 0.001im, 0.018 + 0.002im]

    zfig = z_trace_figure(frequencies, ["Z11" => z11]; title="Z")
    @test length(zfig.data) == 2
    @test trace_fields(zfig, 1)[:name] == "real(Z11)"
    @test trace_fields(zfig, 1)[:y] == [50.0, 55.0]
    @test trace_fields(zfig, 2)[:name] == "imag(Z11)"
    @test trace_fields(zfig, 2)[:y] == [1.0, -2.0]
    @test layout_fields(zfig)[:yaxis][:title][:text] == "Impedance (ohm)"

    yfig = y_trace_figure(frequencies, ["Y11" => y11]; title="Y")
    @test length(yfig.data) == 2
    @test trace_fields(yfig, 1)[:name] == "real(Y11)"
    @test trace_fields(yfig, 2)[:name] == "imag(Y11)"
    @test layout_fields(yfig)[:yaxis][:title][:text] == "Admittance (S)"
end
