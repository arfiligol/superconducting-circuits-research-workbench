# This focused test freezes the reduced floating-qubit topology, private-input
# validation, and two-table/trace output contract without running HB or using
# design-specific capacitance values.

using LinearAlgebra
using Test
using SuperconductingCircuitsCore

const JSON3 = SuperconductingCircuitsCore.JSON3
const D3_ROOT = joinpath(@__DIR__, "..", "..", "notebooks", "pluto", "D3 Intrinsic Purcell Filter Design")
include(joinpath(D3_ROOT, "d3_purcell_common.jl"))
include(joinpath(D3_ROOT, "d3_floating_qubit_nominal_comparison.jl"))
using .D3FloatingQubitNominalComparison
include(joinpath(D3_ROOT, "d3_coupled_evaluator.jl"))

function write_test_json(path, value)
    open(path, "w") do io
        JSON3.write(io, value)
        write(io, '\n')
    end
end

function synthetic_input()
    return Dict(
        "schema_version" => "d3-floating-qubit-nominal.v1",
        "model_id" => "synthetic-structural-test",
        "capacitance_source_id" => "synthetic-positive-branches",
        "C01_fF" => 60.0,
        "C02_fF" => 70.0,
        "C12_fF" => 30.0,
        "Cr1_fF" => 10.0,
        "Cr2_fF" => 1.0,
        "L_J_per_junction_nH" => 24.0,
    )
end

@testset "D3 reduced floating-qubit nominal contract" begin
    mktempdir() do root
        input_path = joinpath(root, "private-qubit.json")
        write_test_json(input_path, synthetic_input())
        loaded = load_floating_qubit_nominal_input(input_path, D3FloatingQubitNominal)
        @test loaded.model.L_J_per_junction_nH == 24.0
        @test occursin(r"^[0-9a-f]{64}$", loaded.input_sha256)
        expected_cg1 = (60.0 + 10.0) * 1e-15
        expected_cg2 = (70.0 + 1.0) * 1e-15
        expected_ceff = 30.0e-15 + expected_cg1 * expected_cg2 / (expected_cg1 + expected_cg2)
        expected_frequency = 1 / (2π * sqrt(12e-9 * expected_ceff))
        @test floating_qubit_coupling_off_frequency_hz(loaded.model) ≈ expected_frequency
        @test _linearized_g_hz(5.0e9, 4.99e9, 5.81e9) ≈ 90e6
        @test_throws D3CandidateRejected _linearized_g_hz(5.0e9, 5.01e9, 5.81e9)

        plan = CircuitPlan("synthetic-floating-qubit")
        readout_open_tail = external_node("readout_open_tail")
        nodes = add_floating_qubit_nominal!(plan, readout_open_tail, loaded.model)
        @test nodes.readout_attachment == readout_open_tail
        @test count(relation -> relation isa ShuntCapacitor, plan.relations) == 2
        @test count(relation -> relation isa CapacitiveCoupling, plan.relations) == 3
        @test count(relation -> relation isa SeriesInductor, plan.relations) == 2
        @test count(relation -> relation isa SeriesInductor && isapprox(relation.inductance, 24e-9), plan.relations) == 2
        @test any(
            relation -> relation isa CapacitiveCoupling &&
                (relation.from == readout_open_tail || relation.to == readout_open_tail),
            plan.relations,
        )

        case = (
            single_l_per_m_h = 4.0e-7,
            single_c_per_m_f = 1.6e-10,
            mtl_l_matrix_h_per_m = [4.0e-7 5.0e-8; 5.0e-8 4.0e-7],
            mtl_c_matrix_f_per_m = [1.6e-10 -2.0e-11; -2.0e-11 1.6e-10],
        )
        design = (
            id = :synthetic_pair,
            lr_total_um = 600.0,
            lp_total_um = 600.0,
            lr_short_um = 200.0,
            lp_short_um = 200.0,
            lc_um = 100.0,
            filter_to_line_capacitance_fF = 20.0,
        )
        feedline = D3FeedlineRLGC(
            source = "synthetic",
            extraction_frequency_hz = 6e9,
            l_per_m_h = 2.5e-7,
            c_per_m_f = 1.0e-10,
            r_per_m_ohm = 0.0,
            g_per_m_s = 0.0,
            r_status = "unavailable_in_source",
            g_status = "unavailable_in_source",
            loss_assumption = "r_and_g_assumed_zero_for_lossless_exploration_only",
            target_impedance_ohm = 50.0,
            max_abs_impedance_error_ohm = 0.25,
            max_abs_impedance_error_role = "mismatch_screening_only",
        )
        hb_settings = D3HBSettings(100e-6, 50.0, 20e9, 0.0, 1, 1, Dict{Symbol,Any}())
        baseline_plan = build_single_pair_feedline_plan(
            case,
            design;
            capacitance_fF = design.filter_to_line_capacitance_fF,
            feedline_length_um = 1000.0,
            feedline = feedline,
            hb_settings = hb_settings,
        )
        variant_plan = build_single_pair_feedline_plan(
            case,
            design;
            capacitance_fF = design.filter_to_line_capacitance_fF,
            feedline_length_um = 1000.0,
            feedline = feedline,
            hb_settings = hb_settings,
            floating_qubit_nominal = loaded.model,
        )
        @test count(relation -> hasproperty(relation, :id) && startswith(relation.id, "floating_qubit_nominal_1_"), baseline_plan.relations) == 0
        @test count(relation -> hasproperty(relation, :id) && startswith(relation.id, "floating_qubit_nominal_1_"), variant_plan.relations) == 7
        intrinsic_plan = build_intrinsic_pair_plan(
            case,
            design;
            hb_settings = hb_settings,
            floating_qubit_nominal = loaded.model,
        )
        @test count(relation -> hasproperty(relation, :id) && startswith(relation.id, "floating_qubit_nominal_intrinsic_1_"), intrinsic_plan.relations) == 7

        invalid = synthetic_input()
        invalid["unexpected"] = true
        write_test_json(input_path, invalid)
        @test_throws ErrorException load_floating_qubit_nominal_input(input_path, D3FloatingQubitNominal)
        @test_throws ErrorException D3FloatingQubitNominal(
            model_id = "invalid",
            capacitance_source_id = "synthetic",
            C01_fF = 0.0,
            C02_fF = 1.0,
            C12_fF = 1.0,
            Cr1_fF = 1.0,
            Cr2_fF = 1.0,
            L_J_per_junction_nH = 24.0,
        )

        output = joinpath(root, "comparison")
        frequencies = [5.0e9, 5.1e9]
        reference = ComplexF64[1 + 0im, 1 + 0im]
        baseline = ComplexF64[0.9 + 0.1im, 0.8 + 0.2im]
        variant = ComplexF64[0.85 + 0.12im, 0.75 + 0.25im]
        model_rows = [Dict(
            "id" => "C01",
            "no_qubit" => nothing,
            "with_qubit" => 60.0,
            "unit" => "fF",
            "meaning" => "synthetic branch",
            "source" => "synthetic",
        )]
        metric_rows = [Dict(
            "id" => "synthetic_shift_hz",
            "no_qubit" => 5.0e9,
            "with_qubit" => 5.1e9,
            "signed_delta" => 1.0e8,
            "unit" => "Hz",
            "quantity_scope" => "synthetic",
            "extraction" => "synthetic",
        )]
        write_comparison_outputs(
            output;
            manifest = Dict("schema_version" => "synthetic"),
            model_rows = model_rows,
            metric_rows = metric_rows,
            frequencies_hz = frequencies,
            reference_s21 = reference,
            no_qubit_s21 = baseline,
            with_qubit_s21 = variant,
            extraction_details = Dict("status" => "synthetic"),
        )
        @test Set(readdir(output)) == COMPARISON_OUTPUT_FILES
        status = JSON3.read(read(joinpath(output, "status.json"), String), Dict{String,Any})
        @test status["state"] == "completed"
        @test length(readlines(joinpath(output, "s21_traces.csv"))) == 3
        @test_throws ErrorException write_comparison_outputs(
            output;
            manifest = Dict(),
            model_rows = model_rows,
            metric_rows = metric_rows,
            frequencies_hz = frequencies,
            reference_s21 = reference,
            no_qubit_s21 = baseline,
            with_qubit_s21 = variant,
            extraction_details = Dict(),
        )
    end
end
