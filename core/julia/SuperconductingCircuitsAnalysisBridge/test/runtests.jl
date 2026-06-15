function repo_root_for_analysis_bridge_tests()
    if haskey(ENV, "SC_WORKBENCH_ROOT")
        return normpath(expanduser(ENV["SC_WORKBENCH_ROOT"]))
    end
    return normpath(joinpath(@__DIR__, "..", "..", "..", ".."))
end

function repo_python_for_analysis_bridge_tests(root::AbstractString)
    if Sys.iswindows()
        return joinpath(root, ".venv", "Scripts", "python.exe")
    end
    return joinpath(root, ".venv", "bin", "python")
end

if !haskey(ENV, "JULIA_PYTHONCALL_EXE")
    repo_python = repo_python_for_analysis_bridge_tests(repo_root_for_analysis_bridge_tests())
    isfile(repo_python) || error(
        "SuperconductingCircuitsAnalysisBridge tests require the repo Python " *
        "environment. Run `uv sync --all-packages` first, or set " *
        "`SC_WORKBENCH_ROOT` / `JULIA_PYTHONCALL_EXE` explicitly.",
    )
    ENV["JULIA_PYTHONCALL_EXE"] = repo_python
end

if !haskey(ENV, "JULIA_CONDAPKG_BACKEND")
    ENV["JULIA_CONDAPKG_BACKEND"] = "Null"
end

using SuperconductingCircuitsAnalysisBridge
using Test

function synthetic_notch_s21(
    frequencies_hz;
    fr_hz,
    ql,
    qc_real,
    qc_imag,
    amplitude,
    phase_rad,
    delay_s,
)
    qc = qc_real + im * qc_imag
    return [
        begin
            x = (frequency - fr_hz) / fr_hz
            baseline = amplitude * exp(im * phase_rad) * exp(-2im * pi * frequency * delay_s)
            dip = 1 - (ql / qc) / (1 + 2im * ql * x)
            baseline * dip
        end
        for frequency in frequencies_hz
    ]
end

function synthetic_transmission_s21(
    frequencies_hz;
    fr_hz,
    ql,
    amplitude,
    phase_rad,
    delay_s,
)
    return [
        begin
            x = (frequency - fr_hz) / fr_hz
            baseline = exp(im * phase_rad) * exp(-2im * pi * frequency * delay_s)
            peak = amplitude / (1 + 2im * ql * x)
            baseline * peak
        end
        for frequency in frequencies_hz
    ]
end

@testset "bridge status" begin
    status = analysis_bridge_status()
    @test status isa BridgeStatus
    @test status.python_executable isa String
    @test status.message isa String
end

@testset "S21 fitting wrappers" begin
    frequencies_hz = collect(range(4.98e9, 5.02e9; length=401))
    s21 = synthetic_notch_s21(
        frequencies_hz;
        fr_hz=5.0e9,
        ql=3000.0,
        qc_real=4500.0,
        qc_imag=300.0,
        amplitude=0.9,
        phase_rad=0.1,
        delay_s=1.0e-10,
    )
    initial_guess = Dict(
        "fr_hz" => 5.0e9,
        "ql" => 3000.0,
        "qc_real" => 4500.0,
        "qc_imag" => 300.0,
        "amplitude" => 0.9,
        "phase_rad" => 0.1,
        "delay_s" => 1.0e-10,
    )

    notch = fit_notch_s21(frequencies_hz, s21; initial_guess=initial_guess)
    @test notch isa AbstractDict
    @test notch["status"] == "success"
    @test notch["params"]["fr_hz"] == 5.0e9
    @test length(notch["fit_curve"]["frequency_hz"]) == length(frequencies_hz)

    bad = fit_notch_s21([1.0e9, 2.0e9], [1.0 + 0im])
    @test bad["status"] == "failed"
    @test occursin("same length", bad["reason"])
end

@testset "transmission and vector wrappers" begin
    frequencies_hz = collect(range(5.7e9, 6.5e9; length=401))
    broad = synthetic_transmission_s21(
        frequencies_hz;
        fr_hz=6.05e9,
        ql=60.0,
        amplitude=0.7,
        phase_rad=0.0,
        delay_s=0.0,
    )
    narrow = synthetic_transmission_s21(
        frequencies_hz;
        fr_hz=6.30e9,
        ql=800.0,
        amplitude=0.8,
        phase_rad=0.0,
        delay_s=0.0,
    )
    s21 = broad .+ 0.4 .* narrow .+ 0.02

    vector = fit_vector_s21(frequencies_hz, s21; n_resonators=2, bg_poles=2)
    @test vector["status"] == "success"
    @test length(vector["model_trace"]["frequency_hz"]) == length(frequencies_hz)
    @test round.(getindex.(vector["resonances"], "fr_hz") ./ 1e9; digits=2) == [6.05, 6.3]

    transmission_frequencies_hz = collect(range(4.95e9, 5.05e9; length=401))
    transmission_s21 = synthetic_transmission_s21(
        transmission_frequencies_hz;
        fr_hz=5.0e9,
        ql=800.0,
        amplitude=0.8,
        phase_rad=0.2,
        delay_s=2.0e-10,
    )
    transmission = fit_transmission_s21(
        transmission_frequencies_hz,
        transmission_s21;
        initial_guess=Dict(
            "fr_hz" => 5.0e9,
            "ql" => 800.0,
            "amplitude" => 0.8,
            "phase_rad" => 0.2,
            "delay_s" => 2.0e-10,
        ),
    )
    @test transmission["status"] == "success"
    @test transmission["params"]["fr_hz"] == 5.0e9
end
