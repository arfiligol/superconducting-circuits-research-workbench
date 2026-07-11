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

function synthetic_d3_s21(frequencies_hz, phasor_convention)
    fp_hz = 6.02e9
    fr_hz = 5.98e9
    filter_loaded_linewidth_hz = 12.0e6
    readout_loaded_linewidth_hz = 0.0
    j_hz = 25.0e6
    residue_hz = -4.5e6 + 2.0e6im
    phasor_sign = phasor_convention == "exp_plus_iomega_t" ? 1.0 : -1.0
    empty_feedline = [
        (0.72 + 0.13im) *
        exp(-2im * pi * phasor_sign * (frequency - 6.0e9) * 2.3e-9) for
        frequency in frequencies_hz
    ]
    direct_path = [
        begin
            x = (frequency - 6.0e9) / 10.0e9
            (0.96 + 0.08im) + (-0.06 + 0.04im) * x
        end for frequency in frequencies_hz
    ]
    filter_only_s21 = [
        begin
            a_p = filter_loaded_linewidth_hz / 2 + im * phasor_sign * (frequency - fp_hz)
            direct_path[index] + residue_hz / a_p
        end for (index, frequency) in enumerate(frequencies_hz)
    ]
    pair_s21 = [
        begin
            a_p = filter_loaded_linewidth_hz / 2 + im * phasor_sign * (frequency - fp_hz)
            a_r = readout_loaded_linewidth_hz / 2 + im * phasor_sign * (frequency - fr_hz)
            direct_path[index] + residue_hz * a_r / (a_p * a_r + j_hz^2)
        end for (index, frequency) in enumerate(frequencies_hz)
    ]
    return empty_feedline .* filter_only_s21, empty_feedline .* pair_s21, empty_feedline
end

function calibrate_synthetic_d3_channel(phasor_convention)
    frequencies_hz = collect(range(1.0e9, 11.0e9; length=10_001))
    filter_only_s21, pair_s21, empty_feedline_s21 = synthetic_d3_s21(
        frequencies_hz,
        phasor_convention,
    )
    calibration = calibrate_d3_channel_residue_s21(
        frequencies_hz,
        filter_only_s21,
        empty_feedline_s21;
        phasor_convention=phasor_convention,
        fit_window_hz=[5.70e9, 6.25e9],
        background_windows_hz=[[1.0e9, 2.0e9], [10.0e9, 11.0e9]],
        fp_hz=6.02e9,
        filter_loaded_linewidth_hz=12.0e6,
        linear_ls_rcond=1.0e-12,
        min_reference_magnitude=0.5,
        min_complex_r2=0.99,
        min_abs_r2=0.99,
        max_phase_rmse_rad=0.03,
        min_phase_magnitude=0.0,
        provenance=Dict(
            "calibration_id" => "synthetic-channel-calibration",
            "reference_contract_id" => "synthetic-reference-contract",
            "filter_only_trace_id" => "synthetic-filter-only",
            "empty_feedline_trace_id" => "synthetic-empty-feedline",
            "filter_loaded_bare_reference_id" => "synthetic-loaded-bare-filter",
            "port_plane" => "synthetic-device-feedline-plane",
        ),
    )
    return frequencies_hz, pair_s21, empty_feedline_s21, calibration
end

function fit_synthetic_d3_through_line(phasor_convention)
    frequencies_hz, measured_s21, empty_feedline_s21, calibration =
        calibrate_synthetic_d3_channel(phasor_convention)
    result = fit_d3_through_line_s21(
        frequencies_hz,
        measured_s21,
        empty_feedline_s21;
        phasor_convention=phasor_convention,
        fit_window_hz=[5.75e9, 6.25e9],
        background_windows_hz=[[1.0e9, 2.0e9], [10.0e9, 11.0e9]],
        fp_hz=6.02e9,
        fr_hz=5.98e9,
        filter_loaded_linewidth_hz=12.0e6,
        readout_loaded_linewidth_hz=0.0,
        channel_calibration=calibration,
        j_bounds_hz=[5.0e6, 60.0e6],
        j_seeds_hz=[10.0e6, 20.0e6, 24.0e6, 25.0e6, 40.0e6],
        linear_ls_rcond=1.0e-12,
        min_reference_magnitude=0.5,
        min_complex_r2=0.99,
        min_abs_r2=0.99,
        max_phase_rmse_rad=0.03,
        min_phase_magnitude=0.0,
        min_normalized_bound_margin=0.05,
        least_squares_max_nfev=200,
        least_squares_ftol=1.0e-8,
        least_squares_xtol=1.0e-8,
        least_squares_gtol=1.0e-8,
        least_squares_diff_step=1.0e-6,
        min_successful_seed_count=3,
        min_successful_seed_fraction=0.8,
        near_optimal_mse_ratio=1.05,
        near_optimal_mse_absolute_tolerance=1.0e-12,
        min_winning_seed_count=2,
        max_seed_spread_hz=1.0e5,
        provenance=Dict(
            "reference_contract_id" => "synthetic-reference-contract",
            "measured_trace_id" => "synthetic-full-feedline",
            "empty_feedline_trace_id" => "synthetic-empty-feedline",
            "filter_loaded_bare_reference_id" => "synthetic-loaded-bare-filter",
            "readout_loaded_bare_reference_id" => "synthetic-loaded-bare-readout",
            "pair_assignment_id" => "slot-6ghz",
            "port_plane" => "synthetic-device-feedline-plane",
        ),
    )
    return calibration, result
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
    @test notch["params"]["qi_status"] == "finite"
    @test Set(keys(notch["metrics"])) == Set(["complex_s21_rmse", "least_squares_cost"])
    @test notch["fit_settings"]["internal_parameterization"] == "centered_scaled_notch"
    @test notch["fit_window_hz"] == [first(frequencies_hz), last(frequencies_hz)]
    @test isnothing(notch["requested_fit_window_hz"])
    @test length(notch["fit_curve"]["frequency_hz"]) == length(frequencies_hz)

    bad = fit_notch_s21([1.0e9, 2.0e9], [1.0 + 0im])
    @test bad["status"] == "failed"
    @test occursin("same length", bad["reason"])
    @test_throws ErrorException fit_notch_s21(
        [true, false, true],
        [1.0 + 0im, 1.0 + 0im, 1.0 + 0im],
    )
    @test_throws ErrorException fit_notch_s21(
        [1.0e9, 2.0e9, 3.0e9],
        [true, false, true],
    )
    @test_throws ErrorException fit_notch_s21(
        frequencies_hz,
        s21;
        initial_guess=initial_guess,
        fit_window_hz=[false, true],
    )
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

    vector = fit_vector_s21(
        frequencies_hz,
        s21;
        n_resonators=2,
        bg_poles=2,
        min_q=2.0,
    )
    @test vector["status"] == "success"
    @test vector["model"] == "scalar_s21_vector"
    @test vector["fit_settings"]["min_q"] == 2.0
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

@testset "D3 complex through-line wrapper" begin
    for (phasor_convention, pole_sign) in (
        ("exp_plus_iomega_t", 1.0),
        ("exp_minus_iomega_t", -1.0),
    )
        calibration, result = fit_synthetic_d3_through_line(phasor_convention)
        @test calibration["status"] == "success"
        @test abs(calibration["params"]["channel_residue_real_hz"] + 4.5e6) < 1.0e5
        @test abs(calibration["params"]["channel_residue_imag_hz"] - 2.0e6) < 1.0e5
        @test calibration["diagnostics"]["linear_ls_rank"] == 3
        @test length(calibration["calibration_summary_sha256"]) == 64
        @test result["status"] == "success"
        @test abs(result["params"]["j_hz"] - 25.0e6) < 1.0e5
        @test Set(keys(result["params"])) == Set(["j_hz"])
        @test result["metrics"]["complex_r2"] > 0.99
        @test result["metrics"]["abs_r2"] > 0.99
        @test length(result["derived_poles"]) == 2
        @test result["fixed_references"]["readout_loaded_linewidth_hz"] == 0.0
        @test result["model_convention"]["free_complex_residue"] == false
        @test result["model_convention"]["simultaneous_j_residue_fit"] == false
        @test result["model_convention"]["loaded_bare_diagonal_frequencies_fixed"] == true
        @test result["model_convention"]["phasor_convention"] == phasor_convention
        @test result["model_convention"]["input_s21_conjugated"] == false
        @test !haskey(result, "effective_references")
        @test sum(pole["frequency_hz"] for pole in result["derived_poles"]) / 2 ≈ 6.0e9
        @test result["diagnostics"]["successful_seed_count"] == 5
        @test result["diagnostics"]["winning_seed_count"] >= 2
        @test all(pole_sign * pole["imaginary_hz"] > 0 for pole in result["derived_poles"])
        @test all(pole["linewidth_hz"] > 0 for pole in result["derived_poles"])
        @test result["normalization"]["exact_two_port_deembedding"] == false
    end

    @test_throws ErrorException fit_synthetic_d3_through_line("hb_native")
end
