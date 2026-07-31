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
using JSON3
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
    filter_off_reference_linewidth_hz = 12.0e6
    readout_off_reference_linewidth_hz = 0.0
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
            a_p = filter_off_reference_linewidth_hz / 2 + im * phasor_sign * (frequency - fp_hz)
            direct_path[index] + residue_hz / a_p
        end for (index, frequency) in enumerate(frequencies_hz)
    ]
    pair_s21 = [
        begin
            a_p = filter_off_reference_linewidth_hz / 2 + im * phasor_sign * (frequency - fp_hz)
            a_r = readout_off_reference_linewidth_hz / 2 + im * phasor_sign * (frequency - fr_hz)
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
        filter_off_reference_linewidth_hz=12.0e6,
        linear_ls_rcond=1.0e-12,
        min_reference_magnitude=0.5,
        min_complex_r2=0.99,
        min_abs_r2=0.99,
        max_phase_rmse_rad=0.03,
        min_phase_magnitude=0.0,
        provenance=Dict(
            "calibration_id" => "synthetic-channel-calibration",
            "reference_contract_id" => "synthetic-reference-contract",
            "filter_off_reference_trace_id" => "synthetic-filter-off-reference-trace",
            "empty_feedline_trace_id" => "synthetic-empty-feedline",
            "filter_off_reference_id" => "synthetic-filter-off-reference",
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
        filter_off_reference_linewidth_hz=12.0e6,
        readout_off_reference_linewidth_hz=0.0,
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
            "filter_off_reference_id" => "synthetic-filter-off-reference",
            "common_readout_off_reference_id" => "synthetic-readout-off-reference",
            "pair_assignment_id" => "slot-6ghz",
            "port_plane" => "synthetic-device-feedline-plane",
        ),
    )
    return calibration, result
end

function fit_synthetic_d3_system_a()
    truth = Dict(
        "c_q_eff_system_a_on_f" => 85.0e-15,
        "f_r_lb_system_a_on_hz" => 6.00e9,
        "g_system_a_on_hz" => 90.0e6,
    )
    observations = []
    for (index, lj_h) in enumerate([14.0e-9, 17.0e-9, 20.0e-9, 23.0e-9, 26.0e-9, 29.0e-9])
        fq_hz = 1 / (2pi * sqrt((lj_h / 2) * truth["c_q_eff_system_a_on_f"]))
        midpoint = (fq_hz + truth["f_r_lb_system_a_on_hz"]) / 2
        half_splitting = sqrt(
            ((fq_hz - truth["f_r_lb_system_a_on_hz"]) / 2)^2 +
            truth["g_system_a_on_hz"]^2,
        )
        push!(
            observations,
            Dict(
                "trace_id" => "system-a-response-$(index)",
                "lj_per_junction_h" => lj_h,
                "lower_frequency_hz" => midpoint - half_splitting,
                "upper_frequency_hz" => midpoint + half_splitting,
                "lower_response_parameter" => "S",
                "lower_extraction_method" => "synthetic_complex_s21_pole_fit",
                "lower_source_trace_id" => "system-a-s21-$(index)",
                "upper_response_parameter" => "Y",
                "upper_extraction_method" => "synthetic_processed_ydiff_root",
                "upper_source_trace_id" => "system-a-ydiff-$(index)",
                "candidate_id" => "synthetic-candidate",
                "reference_contract_id" => "synthetic-reference-contract",
                "topology_id" => "q-r-feedline-system-a",
                "port_plane" => "synthetic-device-plane",
            ),
        )
    end
    bounds = Dict(
        "c_q_eff_system_a_on_f" => [70.0e-15, 100.0e-15],
        "f_r_lb_system_a_on_hz" => [5.80e9, 6.20e9],
        "g_system_a_on_hz" => [50.0e6, 140.0e6],
    )
    seeds = [
        Dict(
            "c_q_eff_system_a_on_f" => truth["c_q_eff_system_a_on_f"] * scale,
            "f_r_lb_system_a_on_hz" => truth["f_r_lb_system_a_on_hz"] +
                                           (scale - 1.0) * 100.0e6,
            "g_system_a_on_hz" => truth["g_system_a_on_hz"] * scale,
        ) for scale in (0.94, 0.97, 1.0, 1.03, 1.06)
    ]
    return fit_d3_system_a_lj_sweep(
        observations;
        physical_bounds=bounds,
        physical_seeds=seeds,
        numerical_tolerances=Dict(
            "frequency_residual_scale_hz" => 1.0e6,
            "least_squares_max_nfev" => 1000,
            "least_squares_ftol" => 1.0e-12,
            "least_squares_xtol" => 1.0e-12,
            "least_squares_gtol" => 1.0e-12,
            "least_squares_diff_step" => 1.0e-6,
            "jacobian_rank_rtol" => 1.0e-10,
        ),
        gates=Dict(
            "min_trace_count" => 5,
            "max_frequency_rmse_hz" => 1.0e3,
            "max_frequency_error_hz" => 2.0e3,
            "min_frequency_r2" => 0.999999,
            "min_normalized_bound_margin" => 0.02,
            "min_successful_seed_count" => 3,
            "min_successful_seed_fraction" => 0.6,
            "near_optimal_cost_ratio" => 1.1,
            "near_optimal_cost_absolute_tolerance" => 1.0e-8,
            "min_winning_seed_count" => 2,
            "max_seed_spread_normalized" => 1.0e-5,
            "min_jacobian_rank" => 3,
            "min_jacobian_singular_ratio" => 1.0e-8,
        ),
        provenance=Dict(
            "fit_id" => "synthetic-system-a-fit",
            "candidate_id" => "synthetic-candidate",
            "reference_contract_id" => "synthetic-reference-contract",
            "topology_id" => "q-r-feedline-system-a",
            "port_plane" => "synthetic-device-plane",
        ),
    )
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
        max_iterations=200,
        min_q=2.0,
        fit_window_hz=[5.72e9, 6.48e9],
    )
    @test vector["status"] == "success"
    @test vector["schema_version"] == "scalar-s21-vector-fit.v2"
    @test vector["model"] == "scalar_s21_vector"
    @test vector["fit_settings"]["min_q"] == 2.0
    @test vector["fit_settings"]["max_iterations"] == 200
    @test vector["fit_diagnostics"]["max_iterations"] == 200
    @test vector["fit_settings"]["fit_constant"] == true
    @test vector["fit_settings"]["fit_proportional"] == false
    @test vector["fit_window_hz"] == [5.72e9, 6.48e9]
    @test vector["requested_fit_window_hz"] == [5.72e9, 6.48e9]
    @test length(vector["model_trace"]["frequency_hz"]) == 381
    @test round.(getindex.(vector["resonances"], "fr_hz") ./ 1e9; digits=2) == [6.05, 6.3]
    @test vector["rational_model"]["stored_pole_count"] ==
          length(vector["rational_model"]["poles"])
    @test length(vector["complex_residual_trace"]["frequency_hz"]) == 381
    @test all(haskey(mode, "pole_real_rad_per_s") for mode in vector["resonances"])
    @test all(!haskey(mode, "pole_real") for mode in vector["resonances"])
    @test JSON3.read(JSON3.write(vector))["rational_model"]["final_model_order"] ==
          vector["rational_model"]["final_model_order"]
    @test_throws ErrorException SuperconductingCircuitsAnalysisBridge._require_vector_fit_v2(
        Dict(
            "status" => "success",
            "model" => "scalar_s21_vector",
        ),
    )
    @test_throws ErrorException SuperconductingCircuitsAnalysisBridge._require_vector_fit_v2(
        Dict(
            "status" => "success",
            "schema_version" => "unexpected-schema",
            "model" => "scalar_s21_vector",
        ),
    )
    @test_throws ErrorException SuperconductingCircuitsAnalysisBridge._require_vector_fit_v2(
        Dict(
            "status" => "pending",
            "schema_version" => "scalar-s21-vector-fit.v2",
            "model" => "scalar_s21_vector",
        ),
    )

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
        @test calibration["fit_method"] ==
              "d3_filter_off_reference_complex_channel_residue_linear_ls"
        @test Set(keys(calibration["provenance"])) == Set([
            "calibration_id",
            "reference_contract_id",
            "filter_off_reference_trace_id",
            "empty_feedline_trace_id",
            "filter_off_reference_id",
            "port_plane",
        ])
        @test result["status"] == "success"
        @test abs(result["params"]["j_hz"] - 25.0e6) < 1.0e5
        @test Set(keys(result["params"])) == Set(["j_hz"])
        @test result["metrics"]["complex_r2"] > 0.99
        @test result["metrics"]["abs_r2"] > 0.99
        @test length(result["derived_poles"]) == 2
        @test result["fixed_references"]["readout_off_reference_linewidth_hz"] == 0.0
        @test Set(keys(result["provenance"])) == Set([
            "reference_contract_id",
            "measured_trace_id",
            "empty_feedline_trace_id",
            "filter_off_reference_id",
            "common_readout_off_reference_id",
            "pair_assignment_id",
            "port_plane",
        ])
        @test result["model_convention"]["free_complex_residue"] == false
        @test result["model_convention"]["simultaneous_j_residue_fit"] == false
        @test result["model_convention"]["off_reference_diagonal_frequencies_fixed"] == true
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

@testset "D3 System-A response-frequency L_J-sweep wrapper" begin
    result = fit_synthetic_d3_system_a()
    @test result["status"] == "success"
    @test result["schema"] == "d3_system_a_frequency_lj_sweep_fit.v1"
    @test result["params"]["c_q_eff_system_a_on_f"] ≈ 85.0e-15 rtol = 1.0e-8
    @test result["params"]["f_r_lb_system_a_on_hz"] ≈ 6.00e9 rtol = 1.0e-8
    @test result["params"]["g_system_a_on_hz"] ≈ 90.0e6 rtol = 1.0e-8
    @test result["params"]["g_system_a_on_hz"] >= 0.0
    @test result["trace_provenance"][1]["lower_branch"]["response_parameter"] == "S"
    @test result["trace_provenance"][1]["upper_branch"]["response_parameter"] == "Y"
    @test result["per_lj"][1]["lower_branch_provenance"]["source_trace_id"] ==
          "system-a-s21-1"
    @test result["per_lj"][1]["upper_branch_provenance"]["source_trace_id"] ==
          "system-a-ydiff-1"
    replay = JSON3.read(JSON3.write(result))
    @test replay["schema"] == "d3_system_a_frequency_lj_sweep_fit.v1"
    @test replay["params"]["g_system_a_on_hz"] >= 0.0
end

