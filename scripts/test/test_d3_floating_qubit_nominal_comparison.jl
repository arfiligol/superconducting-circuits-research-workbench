# This focused test freezes the full-Maxwell Coupler-pad reduction, reduced
# floating-qubit topology, private-input validation, and output contract without
# running HB or using design-specific capacitance values.

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
    cff = Matrix(Diagonal([10.0, 11.0, 12.0, 13.0]))
    crf = [-1.0 -2.0 -1.0 -2.0; -2.0 -1.0 -2.0 -1.0; -0.5 -0.5 -0.5 -0.5]
    reduced = [90.0 -30.0 -10.0; -30.0 101.0 -1.0; -10.0 -1.0 200.0]
    crr = reduced + crf * (cff \ transpose(crf))
    matrix = zeros(8, 8)
    matrix[1:4, 1:4] = cff
    matrix[1:4, 6:8] = transpose(crf)
    matrix[6:8, 1:4] = crf
    matrix[6:8, 6:8] = crr
    matrix[5, 5] = 300.0
    return Dict(
        "schema_version" => "d3-floating-qubit-maxwell.v1",
        "model_id" => "synthetic-structural-test",
        "capacitance_source_id" => "synthetic-full-maxwell",
        "capacitance_unit" => "fF",
        "conductor_labels" => ["pad_a", "pad_b", "pad_c", "pad_d", "ground", "island_a", "island_b", "readout"],
        "maxwell_capacitance_matrix_fF" => [collect(row) for row in eachrow(matrix)],
        "role_mapping" => Dict(
            "reference_conductor" => "ground",
            "floating_coupler_pads" => ["pad_a", "pad_b", "pad_c", "pad_d"],
            "qubit_island_1" => "island_a",
            "qubit_island_2" => "island_b",
            "readout_attachment" => "readout",
        ),
        "readout_self_capacitance_ownership" => "distributed_resonator_owns_self_capacitance",
        "L_J_per_junction_nH" => 23.0,
    )
end

@testset "D3 reduced floating-qubit nominal contract" begin
    mktempdir() do root
        input_path = joinpath(root, "private-qubit.json")
        write_test_json(input_path, synthetic_input())
        loaded = load_floating_qubit_nominal_input(input_path, D3FloatingQubitNominal)
        @test loaded.model.L_J_per_junction_nH == 23.0
        @test occursin(r"^[0-9a-f]{64}$", loaded.input_sha256)
        @test loaded.model.electrostatic_reduction.reduced_maxwell_matrix_fF ≈ [
            [90.0, -30.0, -10.0], [-30.0, 101.0, -1.0], [-10.0, -1.0, 200.0],
        ]
        @test loaded.model.C01_fF ≈ 50.0
        @test loaded.model.C02_fF ≈ 70.0
        @test loaded.model.C12_fF ≈ 30.0
        @test loaded.model.Cr1_fF ≈ 10.0
        @test loaded.model.Cr2_fF ≈ 1.0
        expected_cg1 = (50.0 + 10.0) * 1e-15
        expected_cg2 = (70.0 + 1.0) * 1e-15
        expected_ceff = 30.0e-15 + expected_cg1 * expected_cg2 / (expected_cg1 + expected_cg2)
        expected_frequency = 1 / (2π * sqrt(11.5e-9 * expected_ceff))
        @test floating_qubit_coupling_off_frequency_hz(loaded.model) ≈ expected_frequency
        physics = floating_qubit_physics_diagnostics(loaded.model; f01_target_hz = 4.7e9)
        @test physics.effective_differential_coupling_off_capacitance_fF ≈ expected_ceff * 1e15
        @test physics.first_order_transmon_f01_hz == physics.linearized_lc_frequency_hz - physics.ec_over_h_hz
        @test physics.first_order_transmon_f01_residual_hz == physics.first_order_transmon_f01_hz - 4.7e9
        evidence = floating_qubit_reduction_evidence(
            loaded.model;
            f01_target_hz = 4.7e9,
            expected_L_J_per_junction_nH = 23.0,
            target_contract_id = "synthetic-target",
            target_contract_sha256 = repeat("a", 64),
        )
        @test evidence["readout_diagonal_instantiated"] === false
        @test evidence["readout_self_capacitance_ownership"] == "distributed_resonator_owns_self_capacitance"
        @test_throws ErrorException floating_qubit_reduction_evidence(
            loaded.model;
            f01_target_hz = 4.7e9,
            expected_L_J_per_junction_nH = 24.0,
            target_contract_id = "synthetic-target",
            target_contract_sha256 = repeat("a", 64),
        )
        @test _linearized_g_hz(5.0e9, 4.99e9, 5.81e9) ≈ 90e6
        @test_throws D3CandidateRejected _linearized_g_hz(5.0e9, 5.01e9, 5.81e9)

        plan = CircuitPlan("synthetic-floating-qubit")
        readout_open_tail = external_node("readout_open_tail")
        nodes = add_floating_qubit_nominal!(plan, readout_open_tail, loaded.model)
        @test nodes.readout_attachment == readout_open_tail
        @test count(relation -> relation isa ShuntCapacitor, plan.relations) == 2
        @test count(relation -> relation isa CapacitiveCoupling, plan.relations) == 3
        @test count(relation -> relation isa SeriesInductor, plan.relations) == 2
        @test count(relation -> relation isa SeriesInductor && isapprox(relation.inductance, 23e-9), plan.relations) == 2
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
        invalid = synthetic_input()
        invalid["readout_self_capacitance_ownership"] = "instantiate_as_shunt"
        write_test_json(input_path, invalid)
        @test_throws ErrorException load_floating_qubit_nominal_input(input_path, D3FloatingQubitNominal)
        invalid = synthetic_input()
        invalid["maxwell_capacitance_matrix_fF"][1][1] = 0.0
        invalid["maxwell_capacitance_matrix_fF"][2][2] = 0.0
        invalid["maxwell_capacitance_matrix_fF"][3][3] = 0.0
        invalid["maxwell_capacitance_matrix_fF"][4][4] = 0.0
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
            L_J_per_junction_nH = 23.0,
            electrostatic_reduction = nothing,
        )

        frequencies = collect(4.48e9:10e6:4.54e9)
        reference_values = [0.0, 1.0, 2.0, 3.0, 4.0, 5.0, 6.0]
        reference_notch = _owned_reference_notch_zero(frequencies, reference_values, 4.5e9, 40e6, 0.01)
        loaded_values = [-1.0, 1.0, -1.0, 1.0, 2.0, 3.0, 4.0]
        loaded_notch = _owned_loaded_notch_zero(
            frequencies, loaded_values, 4.5e9, 40e6, 1.0,
            reference_notch.frequency_hz, 1e6,
        )
        @test length(loaded_notch.all_roots) == 3
        @test loaded_notch.frequency_hz == 4.485e9
        @test_throws D3CandidateRejected _owned_loaded_notch_zero(
            frequencies, loaded_values, 4.5e9, 40e6, 1.0,
            4.49e9, 1e6,
        )

        output = joinpath(root, "comparison")
        frequencies = [5.0e9, 5.1e9]
        reference = ComplexF64[1 + 0im, 1 + 0im]
        baseline = ComplexF64[0.9 + 0.1im, 0.8 + 0.2im]
        variant = ComplexF64[0.85 + 0.12im, 0.75 + 0.25im]
        model_rows = [Dict(
            "id" => "C01",
            "no_qubit" => nothing,
            "with_qubit" => 50.0,
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
