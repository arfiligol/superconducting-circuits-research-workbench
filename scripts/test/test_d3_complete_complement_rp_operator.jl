using LinearAlgebra
using Test

const WORKBENCH_ROOT = normpath(joinpath(@__DIR__, "..", ".."))
include(joinpath(
    WORKBENCH_ROOT,
    "notebooks",
    "pluto",
    "D3 Intrinsic Purcell Filter Design",
    "d3_exact_n_response.jl",
))

function synthetic_d3_model(;
    q_coupling_rad_s=0.0,
    direct_exchange_hz=5.0e6,
    open_selector=:feedline,
)
    coordinate_order = [:q, :r, :p, :f1, :fc, :f2]
    frequency_hz = [8.0e9, 5.0e9, 6.0e9, 11.0e9, 13.0e9, 15.0e9]
    angular_frequency = 2π .* frequency_hz
    capacitance = Matrix{Float64}(I, 6, 6)
    stiffness = Matrix(Diagonal(angular_frequency .^ 2))
    direct_exchange_rad_s = 2π * direct_exchange_hz
    stiffness[2, 3] = stiffness[3, 2] =
        2 * sqrt(angular_frequency[2] * angular_frequency[3]) *
        direct_exchange_rad_s
    if !iszero(q_coupling_rad_s)
        stiffness[1, 2] = stiffness[2, 1] =
            2 * sqrt(angular_frequency[1] * angular_frequency[2]) *
            q_coupling_rad_s
        stiffness[1, 3] = stiffness[3, 1] =
            2 * sqrt(angular_frequency[1] * angular_frequency[3]) *
            q_coupling_rad_s
    end
    selector = zeros(Float64, 6, 2)
    if open_selector == :feedline
        selector[4, 1] = 1.0
        selector[6, 2] = 1.0
    elseif open_selector == :rp
        selector[2, 1] = 1.0
        selector[3, 2] = 1.0
    else
        error("Unsupported synthetic open-selector placement.")
    end
    digest = repeat("0", 64)
    return (
        capacitance=capacitance,
        inverse_inductance=stiffness,
        selector=selector,
        reference_impedance_ohm=[50.0, 50.0],
        coordinate_order=coordinate_order,
        anchored_coordinate_indices=(q=1, r=2, p=3, f1=4, fc=5, f2=6),
        provenance=(
            circuit_plan_sha256=digest,
            capacitance_sha256=digest,
            inverse_inductance_sha256=digest,
            selector_sha256=digest,
        ),
    )
end

@testset "D3 exact-open unordered RP subspace" begin
    model = synthetic_d3_model(; direct_exchange_hz=0.0, open_selector=:rp)
    handoff = d3_numerical_cqed_handoff(model)
    state_order = copy(handoff.port_response.exact.state_order.doubled)
    state_count = length(state_order)
    reference(identity) = begin
        vector = zeros(ComplexF64, state_count)
        vector[getproperty(model.anchored_coordinate_indices, identity)] = 1
        vector
    end
    identity = _d3_exact_n_source_model_identity(model)
    references = (
        vectors=(q=reference(:q), r=reference(:r), p=reference(:p)),
        state_order=state_order,
        construction="synthetic_anchored_coordinate_unit_vectors",
        source_model_identity=identity,
        embedded_target_model_identity=identity,
    )
    metric = d3_exact_open_energy_metric(model; cqed_handoff=handoff)
    assignment = d3_exact_open_unordered_rp_subspace_assignment(
        model,
        references,
        metric;
        minimum_q_reference_overlap=0.5,
        minimum_each_rp_subspace_overlap=0.5,
        minimum_unordered_set_assignment_margin=0.05,
        cqed_handoff=handoff,
    )
    @test assignment.provenance.identity_rule ==
        :q_complete_complement_plus_unordered_rp_subspace
    @test assignment.provenance.frequency_rank_assignment == :forbidden
    @test length(assignment.assignment.unordered_rp_pole_indices) == 2
    @test assignment.assignment.selected_q_overlap ≈ 1.0
    @test length(assignment.selected_simple_poles) == 3
    @test all(
        pole -> pole.nearest_pole_separation_per_s >
            pole.algebraic_resolution_per_s &&
            pole.reciprocal_eigenvalue_condition >
            pole.minimum_reciprocal_condition,
        assignment.selected_simple_poles,
    )
    @test all(isapprox.(
        assignment.assignment.selected_rp_subspace_overlaps,
        (1.0, 1.0),
    ))
    @test assignment.unordered_rp_linewidth.linewidth_sum_hz > 0
    @test assignment.unordered_rp_linewidth.linewidth_fraction_min <= 0.5
    @test assignment.unordered_rp_linewidth.linewidth_fraction_max >= 0.5
    @test assignment.unordered_rp_linewidth.linewidth_fraction_min +
        assignment.unordered_rp_linewidth.linewidth_fraction_max ≈ 1.0

    swapped = merge(references, (
        vectors=(q=references.vectors.q, r=references.vectors.p, p=references.vectors.r),
    ))
    swapped_assignment = d3_exact_open_unordered_rp_subspace_assignment(
        model,
        swapped,
        metric;
        minimum_q_reference_overlap=0.5,
        minimum_each_rp_subspace_overlap=0.5,
        minimum_unordered_set_assignment_margin=0.05,
        cqed_handoff=handoff,
    )
    @test swapped_assignment.assignment.unordered_rp_raw_state_indices ==
        assignment.assignment.unordered_rp_raw_state_indices
    @test swapped_assignment.unordered_rp_linewidth.linewidth_sum_hz ≈
        assignment.unordered_rp_linewidth.linewidth_sum_hz
    diagnostic_assignment = d3_exact_open_unordered_rp_subspace_assignment(
        model,
        references,
        metric;
        minimum_q_reference_overlap=1.0e300,
        minimum_each_rp_subspace_overlap=-1.0e300,
        minimum_unordered_set_assignment_margin=1.0e300,
        cqed_handoff=handoff,
    )
    @test diagnostic_assignment.assignment.unordered_rp_raw_state_indices ==
        assignment.assignment.unordered_rp_raw_state_indices
    @test diagnostic_assignment.unordered_rp_linewidth.linewidth_sum_hz ==
        assignment.unordered_rp_linewidth.linewidth_sum_hz
    @test diagnostic_assignment.assignment.minimum_q_reference_overlap ==
        1.0e300
    @test diagnostic_assignment.assignment.minimum_each_rp_subspace_overlap ==
        -1.0e300
    @test diagnostic_assignment.assignment.minimum_unordered_set_assignment_margin ==
        1.0e300
    @test diagnostic_assignment.assignment.numeric_control_disposition == (
        status=:proposed_inactive,
        role=:diagnostic_only,
    )
    wrong_source = merge(references, (
        source_model_identity=merge(identity, (
            selector_sha256=repeat("1", 64),
        )),
    ))
    @test_throws ErrorException d3_exact_open_unordered_rp_subspace_assignment(
        model,
        wrong_source,
        metric;
        minimum_q_reference_overlap=0.5,
        minimum_each_rp_subspace_overlap=0.5,
        minimum_unordered_set_assignment_margin=0.05,
        cqed_handoff=handoff,
    )

    degenerate_model = synthetic_d3_model(;
        direct_exchange_hz=0.0,
        open_selector=:rp,
    )
    degenerate_model.inverse_inductance[3, 3] =
        degenerate_model.inverse_inductance[2, 2]
    degenerate_handoff = d3_numerical_cqed_handoff(degenerate_model)
    degenerate_metric = d3_exact_open_energy_metric(
        degenerate_model;
        cqed_handoff=degenerate_handoff,
    )
    @test_throws ErrorException d3_exact_open_unordered_rp_subspace_assignment(
        degenerate_model,
        references,
        degenerate_metric;
        minimum_q_reference_overlap=0.5,
        minimum_each_rp_subspace_overlap=0.5,
        minimum_unordered_set_assignment_margin=0.05,
        cqed_handoff=degenerate_handoff,
    )
end

@testset "D3 intrinsic-pair cofactor notch anchor" begin
    target_hz = 6.0e9
    capacitance = [2.0 -0.5; -0.5 2.0] .* 1.0e-12
    stiffness = Matrix(Diagonal(fill(
        (2π * 8.0e9)^2 * 2.0e-12,
        2,
    )))
    stiffness[1, 2] = stiffness[2, 1] =
        (2π * target_hz)^2 * capacitance[2, 1]
    model = (
        capacitance=capacitance,
        inverse_inductance=stiffness,
        port_indices=[1, 2],
        provenance=(circuit_plan_sha256=repeat("2", 64),),
    )
    receipt = _d3_intrinsic_pair_notch_from_model(
        model,
        (4.9e9, 5.1e9),
    )
    @test receipt.frequency_hz ≈ target_hz rtol=1.0e-12
    @test receipt.selection_anchor_hz == 5.0e9
    @test !receipt.selected_zero_inside_bracket
    @test receipt.zero_candidates.nearest_finite_spectrum_separation >
        receipt.zero_candidates.finite_spectrum_resolution
    @test receipt.conservative_poles.nearest_selected_zero_separation_hz >
        receipt.conservative_poles.zero_pole_resolution_hz
    @test abs(receipt.z21_ohm) <= 1.0e-12

    extreme = _d3_intrinsic_pair_notch_from_model(
        model,
        (4.9e9, 5.1e9);
        frequency_tolerance_hz=-1.0e300,
        relative_frequency_tolerance=1.0e300,
        max_iterations=-1,
        max_abs_real_z21_ohm=-1.0e300,
        max_abs_imag_z21_ohm=1.0e300,
        max_abs_complex_z21_ohm=-1.0e300,
    )
    @test extreme.frequency_hz == receipt.frequency_hz
    @test extreme.z21_ohm == receipt.z21_ohm
    @test extreme.residual_tolerances_ohm == (
        real=-1.0e300,
        imag=1.0e300,
        complex=-1.0e300,
    )
    @test extreme.numeric_control_disposition.residual_tolerances ==
        :proposed_inactive

    missing_zero_model = merge(model, (
        capacitance=Matrix{Float64}(I, 2, 2),
        inverse_inductance=[2.0 0.5; 0.5 2.0],
    ))
    @test_throws ErrorException _d3_intrinsic_pair_notch_from_model(
        missing_zero_model,
        (4.9e9, 5.1e9),
    )

    degenerate_model = merge(model, (
        inverse_inductance=(2π * target_hz)^2 .* capacitance,
    ))
    @test_throws ErrorException _d3_intrinsic_pair_notch_from_model(
        degenerate_model,
        (4.9e9, 5.1e9),
    )
end

const TEST_GATE_POLICY = (
    maximum_elimination_condition_number=1.0e12,
    maximum_relative_elimination_solve_residual=1.0e-11,
    maximum_relative_reciprocity_error=1.0e-12,
    maximum_relative_passivity_violation=1.0e-12,
    maximum_relative_root_residual=1.0e-10,
    maximum_root_growth_rate_hz=1.0e-3,
    minimum_normalized_residue_slope=1.0e-4,
    maximum_relative_coupling_spread=1.0e-8,
    maximum_relative_determinant_closure_error=1.0e-10,
)

@testset "D3 complete-complement RP operator" begin
    model = synthetic_d3_model()
    receipt = d3_complete_complement_rp_metrics(
        model;
        readout_root_band_hz=(4.9e9, 5.1e9),
        filter_root_band_hz=(5.9e9, 6.1e9),
        gate_policy=TEST_GATE_POLICY,
    )
    @test receipt.retained_coordinates == [:r, :p]
    @test receipt.eliminated_coordinates == [:q, :f1, :fc, :f2]
    @test receipt.readout.frequency_hz ≈ 5.0e9 rtol=1.0e-12
    @test receipt.filter.frequency_hz ≈ 6.0e9 rtol=1.0e-12
    @test receipt.readout.selection_anchor_hz == 5.0e9
    @test receipt.filter.selection_anchor_hz == 6.0e9
    @test receipt.readout.selected_root_inside_band
    @test receipt.filter.selected_root_inside_band
    @test receipt.readout.simple_root.nearest_pole_separation_per_s >
        receipt.readout.simple_root.algebraic_resolution_per_s
    @test receipt.filter.simple_root.nearest_pole_separation_per_s >
        receipt.filter.simple_root.algebraic_resolution_per_s
    @test receipt.coherent_exchange_hz ≈ 5.0e6 rtol=1.0e-12
    @test receipt.total_exchange_hz ≈ 5.0e6 rtol=1.0e-12
    @test abs(receipt.dissipative_cross_coupling_hz) <= 1.0e-6
    @test receipt.relative_coupling_spread <= 1.0e-12
    @test receipt.determinant_closure.relative_error <= 1.0e-12
    @test receipt.numeric_control_disposition == (
        status=:proposed_inactive,
        role=:diagnostic_only,
        fields=D3_COMPLETE_COMPLEMENT_RP_GATE_FIELDS,
    )
    @test receipt.context_validation.machine_relative_resolution ==
        4096 * length(model.coordinate_order) * eps(Float64)

    extreme_policy = (
        maximum_elimination_condition_number=-1.0e300,
        maximum_relative_elimination_solve_residual=-1.0e300,
        maximum_relative_reciprocity_error=-1.0e300,
        maximum_relative_passivity_violation=-1.0e300,
        maximum_relative_root_residual=-1.0e300,
        maximum_root_growth_rate_hz=-1.0e300,
        minimum_normalized_residue_slope=1.0e300,
        maximum_relative_coupling_spread=-1.0e300,
        maximum_relative_determinant_closure_error=-1.0e300,
    )
    extreme_receipt = d3_complete_complement_rp_metrics(
        model;
        readout_root_band_hz=(4.9e9, 5.1e9),
        filter_root_band_hz=(5.9e9, 6.1e9),
        gate_policy=extreme_policy,
    )
    @test extreme_receipt.gate_policy == extreme_policy
    @test extreme_receipt.readout.frequency_hz == receipt.readout.frequency_hz
    @test extreme_receipt.filter.frequency_hz == receipt.filter.frequency_hz
    @test extreme_receipt.effective_exchange_rad_s ==
        receipt.effective_exchange_rad_s

    extended = merge(model, (
        capacitance=Matrix{Float64}(I, 7, 7),
        inverse_inductance=Matrix(Diagonal(vcat(
            diag(model.inverse_inductance),
            (2π * 17.0e9)^2,
        ))),
        selector=vcat(model.selector, zeros(Float64, 1, 2)),
        coordinate_order=vcat(model.coordinate_order, :distributed_internal),
    ))
    extended.inverse_inductance[2, 3] =
        extended.inverse_inductance[3, 2] = model.inverse_inductance[2, 3]
    extended_receipt = d3_complete_complement_rp_metrics(
        extended;
        readout_root_band_hz=(4.9e9, 5.1e9),
        filter_root_band_hz=(5.9e9, 6.1e9),
        gate_policy=TEST_GATE_POLICY,
    )
    @test :distributed_internal in extended_receipt.eliminated_coordinates
    @test extended_receipt.readout.frequency_hz ≈ receipt.readout.frequency_hz
    @test extended_receipt.filter.frequency_hz ≈ receipt.filter.frequency_hz
    @test extended_receipt.coherent_exchange_hz ≈ receipt.coherent_exchange_hz

    legacy = d3_feedline_downfolded_loaded_bare_roots(
        model,
        (4.9e9, 6.1e9),
    )
    @test receipt.readout.root_hz ≈ legacy.readout.root_hz rtol=1.0e-12
    @test receipt.filter.root_hz ≈ legacy.filter.root_hz rtol=1.0e-12

    outside_band_receipt = d3_complete_complement_rp_metrics(
        model;
        readout_root_band_hz=(5.55e9, 5.65e9),
        filter_root_band_hz=(5.55e9, 5.65e9),
        gate_policy=TEST_GATE_POLICY,
    )
    @test outside_band_receipt.readout.frequency_hz ≈ 5.0e9 rtol=1.0e-12
    @test outside_band_receipt.readout.selection_anchor_hz == 5.6e9
    @test !outside_band_receipt.readout.selected_root_inside_band
    @test outside_band_receipt.filter.frequency_hz ≈ 6.0e9 rtol=1.0e-12
    @test outside_band_receipt.filter.selection_anchor_hz == 5.6e9
    @test !outside_band_receipt.filter.selected_root_inside_band

    context =
        _d3_complete_complement_rp_context(model, TEST_GATE_POLICY)
    sample_omega = receipt.midpoint_angular_frequency_rad_s
    sample =
        _d3_complete_complement_rp_operator(context, sample_omega)
    derivative_step = 1.0e-5 * real(sample_omega)
    lower = _d3_complete_complement_rp_operator(
        context,
        sample_omega - derivative_step,
    )
    upper = _d3_complete_complement_rp_operator(
        context,
        sample_omega + derivative_step,
    )
    finite_difference =
        (upper.effective_dynamic_stiffness -
         lower.effective_dynamic_stiffness) /
        (2 * derivative_step)
    @test sample.effective_dynamic_stiffness_derivative ≈
        finite_difference rtol=2.0e-10
end

@testset "D3 q-mediated exchange and fail-closed gates" begin
    mediated_model = synthetic_d3_model(
        q_coupling_rad_s=2π * 30.0e6,
        direct_exchange_hz=0.0,
    )
    relaxed_spread_policy = merge(
        TEST_GATE_POLICY,
        (maximum_relative_coupling_spread=10.0,),
    )
    receipt = d3_complete_complement_rp_metrics(
        mediated_model;
        readout_root_band_hz=(4.9e9, 5.1e9),
        filter_root_band_hz=(5.9e9, 6.1e9),
        gate_policy=relaxed_spread_policy,
    )
    @test receipt.coherent_exchange_hz > 0
    @test iszero(
        d3_stage2_matrix_metrics(mediated_model).
        J_circuit_h_rp_pre_downfold_report_only_hz,
    )

    ambiguous_model = synthetic_d3_model()
    ambiguous_model.inverse_inductance[1, 1] =
        ambiguous_model.inverse_inductance[2, 2]
    ambiguous_context = _d3_complete_complement_rp_context(
        ambiguous_model,
        TEST_GATE_POLICY,
    )
    ambiguous_error = try
        _d3_complete_complement_rp_diagonal_root(
            ambiguous_model,
            ambiguous_context,
            :r,
            (5.55e9, 5.65e9),
        )
        nothing
    catch error
        error
    end
    @test ambiguous_error isa ErrorException
    @test occursin(
        "nearest-anchor root selection is non-unique",
        sprint(showerror, ambiguous_error),
    )
    asymmetric = synthetic_d3_model()
    asymmetric.inverse_inductance[2, 3] *= 1.01
    @test_throws ErrorException d3_complete_complement_rp_metrics(
        asymmetric;
        readout_root_band_hz=(4.9e9, 5.1e9),
        filter_root_band_hz=(5.9e9, 6.1e9),
        gate_policy=TEST_GATE_POLICY,
    )
    inactive_spread_receipt = d3_complete_complement_rp_metrics(
        mediated_model;
        readout_root_band_hz=(4.9e9, 5.1e9),
        filter_root_band_hz=(5.9e9, 6.1e9),
        gate_policy=merge(
            TEST_GATE_POLICY,
            (maximum_relative_coupling_spread=0.0,),
        ),
    )
    @test inactive_spread_receipt.coherent_exchange_hz ==
        receipt.coherent_exchange_hz
    @test inactive_spread_receipt.gate_policy.maximum_relative_coupling_spread ==
        0.0
    @test inactive_spread_receipt.relative_coupling_spread > 0
end
