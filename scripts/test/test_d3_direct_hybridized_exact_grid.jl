using Test

const WORKBENCH_ROOT = normpath(joinpath(@__DIR__, "..", ".."))
const D3_ROOT = joinpath(
    WORKBENCH_ROOT,
    "notebooks",
    "pluto",
    "D3 Intrinsic Purcell Filter Design",
)

include(joinpath(D3_ROOT, "d3_circuit_plans.jl"))
include(joinpath(D3_ROOT, "d3_exact_n_response.jl"))
include(joinpath(D3_ROOT, "d3_stage_models.jl"))
using .D3ResonatorInput:
    bind_d3_rev10_q2d_input, load_d3_continuous_ground_q2d_input

const EXPECTED_CORE_ENTRY = realpath(joinpath(
    WORKBENCH_ROOT,
    "core",
    "julia",
    "SuperconductingCircuitsCore",
    "src",
    "SuperconductingCircuitsCore.jl",
))
realpath(pathof(SuperconductingCircuitsCore)) == EXPECTED_CORE_ENTRY || error(
    "D3 exact-grid test must load SuperconductingCircuitsCore from this Workbench candidate.",
)

const Q2D_PATH = joinpath(D3_ROOT, "d3_continuous_ground_q2d_maxwell_lc.v4.json")

function _legacy_d3_matrix_sha256(label, matrix)
    values = Matrix{Float64}(matrix)
    buffer = IOBuffer()
    write(
        buffer,
        "d3-float64-matrix-v1|$(String(label))|rows=$(size(values, 1))|cols=$(size(values, 2))",
    )
    for row in axes(values, 1), column in axes(values, 2)
        value = iszero(values[row, column]) ? 0.0 : values[row, column]
        write(buffer, UInt8('|'))
        write(buffer, bitstring(value))
    end
    return bytes2hex(SHA.sha256(take!(buffer)))
end

@testset "D3 targeted-Schur local outputs and typed failure" begin
    candidate = (
        lr_open_m=2.0e-3,
        lr_short_m=2.0e-3,
        lc_m=300.0e-6,
        lp_open_m=2.1e-3,
        lp_short_m=2.0e-3,
        u_IDC=60.0,
    )
    feedline = (
        feedline_length_m=1.0e-3,
        feedline_n_sections=20,
        feedline_l_per_m_h=D3_DEFAULT_FEEDLINE_L_PER_M_H,
        feedline_c_per_m_f=D3_DEFAULT_FEEDLINE_C_PER_M_F,
        port_resistance_ohm=50.0,
    )
    q2d = bind_d3_rev10_q2d_input(
        load_d3_continuous_ground_q2d_input(Q2D_PATH);
        section_length_m=50.0e-6,
        mtl_section_length_m=10.0e-6,
    )
    grid_inputs = D3DirectHybridizedInputs(
        q2d,
        nothing,
        nothing,
        feedline,
        (canonical_sha256=repeat("a", 64),),
    )
    grid = d3_stage2_direct_hybridized_grid_plan(
        candidate,
        grid_inputs;
        refinement_level=0,
    )
    topology = _d3_targeted_topology(candidate, grid)

    frequencies_hz = [8.0e9, 5.0e9, 6.0e9, 11.0e9, 13.0e9, 15.0e9]
    omega = 2π .* frequencies_hz
    capacitance = Matrix{Float64}(I, 6, 6)
    stiffness = Matrix(Diagonal(omega .^ 2))
    stiffness[2, 3] = stiffness[3, 2] =
        2 * sqrt(omega[2] * omega[3]) * (2π * 5.0e6)
    selector = zeros(Float64, 6, 2)
    selector[2, 1] = 1.0
    selector[3, 2] = 1.0
    full_model = (
        capacitance=capacitance,
        inverse_inductance=stiffness,
        selector=selector,
        reference_impedance_ohm=[50.0, 50.0],
        coordinate_order=[:q, :r, :p, :f1, :fc, :f2],
        anchored_coordinate_indices=(q=1, r=2, p=3, f1=4, fc=5, f2=6),
    )
    zero_full = zeros(6, 6)
    full_kernel = (
        c0=capacitance,
        k0=stiffness,
        c_terms=NamedTuple{D3_STAGE2_VARIABLE_ORDER}(
            ntuple(_ -> zero_full, length(D3_STAGE2_VARIABLE_ORDER)),
        ),
        k_terms=NamedTuple{_D3_TARGETED_SCHUR_LENGTH_COORDINATES}(
            ntuple(_ -> zero_full, length(_D3_TARGETED_SCHUR_LENGTH_COORDINATES)),
        ),
        reference_model=full_model,
    )

    notch_capacitance = [2.0 -0.5; -0.5 2.0] .* 1.0e-12
    notch_stiffness = Matrix(Diagonal(fill(
        (2π * 8.0e9)^2 * 2.0e-12,
        2,
    )))
    notch_stiffness[1, 2] = notch_stiffness[2, 1] =
        (2π * 5.0e9)^2 * notch_capacitance[2, 1]
    zero_notch = zeros(2, 2)
    notch_model = (
        capacitance=notch_capacitance,
        inverse_inductance=notch_stiffness,
        port_indices=[1, 2],
        provenance=(circuit_plan_sha256=repeat("d", 64),),
    )
    notch_kernel = (
        c0=notch_capacitance,
        k0=notch_stiffness,
        c_terms=NamedTuple{_D3_TARGETED_SCHUR_LENGTH_COORDINATES}(
            ntuple(_ -> zero_notch, length(_D3_TARGETED_SCHUR_LENGTH_COORDINATES)),
        ),
        k_terms=NamedTuple{_D3_TARGETED_SCHUR_LENGTH_COORDINATES}(
            ntuple(_ -> zero_notch, length(_D3_TARGETED_SCHUR_LENGTH_COORDINATES)),
        ),
        reference_model=notch_model,
    )
    fixed = _d3_targeted_schur_fixed_context(full_model)
    source_identity = (canonical_sha256=repeat("e", 64),)
    context = D3TargetedSchurObjectiveContext(
        D3_TARGETED_SCHUR_CONTEXT_CONTRACT,
        "synthetic-targeted-context",
        candidate,
        nothing,
        grid,
        full_kernel,
        notch_kernel,
        fixed,
        source_identity,
        (topology_counts=topology,),
    )
    targeted_notch = _d3_targeted_cofactor_notch_from_model(
        notch_model,
        5.0e9,
    )
    @test targeted_notch.frequency_hz ≈ 5.0e9 rtol=1.0e-12
    @test targeted_notch.local_denominator.factorization_succeeded
    @test isfinite(targeted_notch.local_residual.relative_solve_residual)

    @test !isdefined(@__MODULE__, :_d3_targeted_schur_determinant_root)

    lossless = _d3_targeted_schur_outputs(
        _d3_targeted_schur_candidate_context(
            merge(fixed, (conductance=zeros(6, 6),)),
            capacitance,
            stiffness,
        );
        readout_root_anchor_hz=5.0e9,
        filter_root_anchor_hz=6.0e9,
    )
    @test lossless.kappa_hz == (r=-0.0, p=-0.0)
    @test lossless.kappa_sum_hz == 0.0
    @test !hasproperty(lossless, :linewidth_fraction_min)

    cared = d3_stage2_direct_cared_outputs(
        candidate,
        context;
        slot_hz=5.6e9,
        readout_root_anchor_hz=5.0e9,
        filter_root_anchor_hz=6.0e9,
        notch_zero_anchor_hz=5.0e9,
    )
    @test cared.f_r_eff_hz ≈ 5.0e9 rtol=1.0e-10
    @test cared.f_p_eff_hz ≈ 6.0e9 rtol=1.0e-10
    @test cared.f_n_hz ≈ 5.0e9 rtol=1.0e-12
    @test real(cared.diagonal_roots_hz.r) ≈ cared.f_r_eff_hz rtol=1.0e-10
    @test real(cared.diagonal_roots_hz.p) ≈ cared.f_p_eff_hz rtol=1.0e-10
    @test imag(cared.diagonal_roots_hz.r) <= 0
    @test imag(cared.diagonal_roots_hz.p) <= 0
    @test all(
        value -> isfinite(real(value)) && isfinite(imag(value)),
        values(cared.diagonal_residue_slopes),
    )
    @test cared.kappa_sum_anchored_bare_rp_hz ==
        sum(values(cared.kappa_anchored_bare_rp_hz))
    @test cared.kappa_anchored_bare_rp_hz.r ==
        -2 * imag(cared.diagonal_roots_hz.r)
    @test cared.kappa_anchored_bare_rp_hz.p ==
        -2 * imag(cared.diagonal_roots_hz.p)
    @test !hasproperty(cared, :linewidth_fraction_min_anchored_bare_rp)
    @test cared.extraction_profile.effective_diagonal_frequency_extraction ==
        :complete_complement_rp_anchored_bare_complex_diagonal_roots
    @test cared.extraction_profile.linewidth_sum_extraction ==
        :anchored_bare_diagonal_root_trace
    metrics = _d3_targeted_metric_record(cared)
    @test metrics.contract_id ==
        "d3-stage2-targeted-schur-candidate-metrics.v2"
    @test metrics.kappa_sum_anchored_bare_rp_hz ==
        cared.kappa_sum_anchored_bare_rp_hz
    @test !hasproperty(metrics, :linewidth_fraction_min_anchored_bare_rp)
    @test !hasproperty(metrics, :linewidth_participation_extraction)

    failure = try
        d3_stage2_direct_cared_outputs(
            merge(candidate, (u_IDC=NaN,)),
            context;
            slot_hz=5.6e9,
            readout_root_anchor_hz=5.0e9,
            filter_root_anchor_hz=6.0e9,
            notch_zero_anchor_hz=5.0e9,
        )
        nothing
    catch exception
        exception
    end
    @test failure isa D3TargetedSchurNotEvaluable
    @test failure.code == "d3_targeted_schur_invalid_candidate"
    @test_throws MethodError d3_stage2_direct_cared_outputs(
        candidate,
        context;
        slot_hz="not-a-frequency",
        readout_root_anchor_hz=5.0e9,
        filter_root_anchor_hz=6.0e9,
        notch_zero_anchor_hz=5.0e9,
    )
    @test_throws D3TargetedSchurNotEvaluable d3_stage2_direct_cared_outputs(
        candidate,
        context;
        slot_hz=5.6e9,
        readout_root_anchor_hz=NaN,
        filter_root_anchor_hz=6.0e9,
        notch_zero_anchor_hz=5.0e9,
    )
    @test length(methods(d3_stage2_direct_cared_outputs)) == 1
    @test !isdefined(@__MODULE__, :D3DirectHybridizedCaredOutput)
    @test !isdefined(@__MODULE__, :d3_stage2_candidate_metrics)
    @test !isdefined(@__MODULE__, :d3_exact_open_unordered_rp_subspace_assignment)
end

function _legacy_d3_complex_matrix_sha256(label, matrix)
    values = Matrix{ComplexF64}(matrix)
    buffer = IOBuffer()
    write(
        buffer,
        "d3-complex128-matrix-v1|$(String(label))|rows=$(size(values, 1))|cols=$(size(values, 2))",
    )
    for row in axes(values, 1), column in axes(values, 2)
        value = values[row, column]
        real_value = iszero(real(value)) ? 0.0 : Float64(real(value))
        imag_value = iszero(imag(value)) ? 0.0 : Float64(imag(value))
        write(buffer, UInt8('|'))
        write(buffer, bitstring(real_value))
        write(buffer, UInt8(','))
        write(buffer, bitstring(imag_value))
    end
    return bytes2hex(SHA.sha256(take!(buffer)))
end

@testset "D3 exact-N matrix hash canonical stream compatibility" begin
    label = "readout-β"
    real_values = [0.0 -0.0 1.5; -2.25 1 / 3 9.75]
    complex_values = ComplexF64[
        ComplexF64(0.0, -0.0) ComplexF64(-2.25, 1 / 3)
        ComplexF64(-0.0, 1.5) ComplexF64(9.75, -4.125)
    ]
    @test _d3_exact_n_matrix_sha256(label, real_values) ==
        _legacy_d3_matrix_sha256(label, real_values)
    @test _d3_exact_n_matrix_sha256(label, Matrix{Float64}(undef, 0, 2)) ==
        _legacy_d3_matrix_sha256(label, Matrix{Float64}(undef, 0, 2))
    @test _d3_exact_n_complex_matrix_sha256(label, complex_values) ==
        _legacy_d3_complex_matrix_sha256(label, complex_values)
    @test _d3_exact_n_complex_matrix_sha256(
        label,
        Matrix{ComplexF64}(undef, 2, 0),
    ) == _legacy_d3_complex_matrix_sha256(
        label,
        Matrix{ComplexF64}(undef, 2, 0),
    )
end

@testset "D3 direct-Hybridized exact grid plan" begin
    reduction = (
        input_schema="synthetic-q3d-authority.v1",
        ordered_labels=("Q1_L", "Q1_R", "read"),
        reduction_method="synthetic_test_only",
    )
    q3d_model = (
        model_id="synthetic-q3d-model",
        capacitance_source_id="synthetic-q3d-source",
        C0r_fF=1.0,
        C01_fF=2.0,
        C02_fF=3.0,
        C12_fF=4.0,
        Cr1_fF=5.0,
        Cr2_fF=6.0,
        L_J_per_junction_nH=7.0,
        electrostatic_reduction=reduction,
    )
    q3d_identity = _d3_require_same_q3d_model(q3d_model, deepcopy(q3d_model))
    @test q3d_identity.branch_values_fF_and_nH.C0r_fF == 1.0
    @test_throws ErrorException _d3_require_same_q3d_model(
        merge(q3d_model, (C0r_fF=1.1,)),
        q3d_model,
    )
    @test_throws ErrorException _d3_require_same_q3d_model(
        merge(q3d_model, (
            electrostatic_reduction=merge(reduction, (
                reduction_method="mismatched_reduction",
            )),
        )),
        q3d_model,
    )

    authority = load_d3_continuous_ground_q2d_input(Q2D_PATH)
    q2d = bind_d3_rev10_q2d_input(
        authority;
        section_length_m=50.0e-6,
        mtl_section_length_m=10.0e-6,
    )
    feedline = (
        feedline_length_m=1.0e-3,
        feedline_n_sections=20,
        feedline_l_per_m_h=D3_DEFAULT_FEEDLINE_L_PER_M_H,
        feedline_c_per_m_f=D3_DEFAULT_FEEDLINE_C_PER_M_F,
        port_resistance_ohm=50.0,
    )
    inputs = D3DirectHybridizedInputs(
        q2d,
        nothing,
        nothing,
        feedline,
        (canonical_sha256=repeat("a", 64),),
    )
    candidate = (
        lr_open_m=2.000123e-3,
        lr_short_m=2.000057e-3,
        lc_m=300.017e-6,
        lp_open_m=2.000211e-3,
        lp_short_m=2.000091e-3,
        u_IDC=60.0,
    )
    plans = [
        d3_stage2_direct_hybridized_grid_plan(
            candidate,
            inputs;
            refinement_level=level,
        )
        for level in 0:3
    ]
    @test plans[2].counts.feedline_left + plans[2].counts.feedline_right ==
        2 * feedline.feedline_n_sections
    idc_mapping = D3IDCMapping(
        8.0,
        (5.0, 10.0),
        (35.0, 75.0),
        "closed_source_support_um",
        Dict(
            "C_12_fF" => (0.5, 9.0),
            "C_1G_fF" => (0.25, 22.0),
            "C_2G_fF" => (0.24, 22.0),
        ),
        Dict{Tuple{Float64,Float64},NamedTuple}(),
        D3_SELECTED_IDC_MAPPING_ID,
        repeat("b", 64),
        "synthetic-grid-refinement",
        Dict{String,Any}("sha256" => repeat("c", 64)),
        Dict{String,Any}(),
    )
    refined_inputs = D3DirectHybridizedInputs(
        q2d,
        idc_mapping,
        (
            c0r_f=20.0e-15,
            c01_f=20.0e-15,
            c02_f=20.0e-15,
            c12_qubit_f=10.0e-15,
            cr1_f=5.0e-15,
            cr2_f=5.0e-15,
            l_j_per_junction_h=20.0e-9,
        ),
        feedline,
        inputs.source_identity,
    )
    refined_context = build_d3_stage2_targeted_schur_objective_context(
        candidate,
        refined_inputs;
        grid_plan=plans[2],
        id="d3-targeted-grid-refinement-test",
    )
    @test refined_context.grid_plan === plans[2]
    fixed_topology_counts = (
        readout_resonator=380,
        filter_resonator=380,
        mtl=196,
        feedline_left=10,
        feedline_right=10,
    )
    fixed_topology_boundaries = (
        readout_resonator_boundaries_m=_d3_targeted_line_boundaries(
            candidate.lr_short_m,
            candidate.lc_m,
            candidate.lr_open_m,
            (short=76, mtl=196, open=108),
        ),
        filter_resonator_boundaries_m=_d3_targeted_line_boundaries(
            candidate.lp_short_m,
            candidate.lc_m,
            candidate.lp_open_m,
            (short=76, mtl=196, open=108),
        ),
        feedline_left_boundaries_m=plans[1].boundaries_m.feedline_left_boundaries_m,
        feedline_right_boundaries_m=plans[1].boundaries_m.feedline_right_boundaries_m,
    )
    fixed_topology_payload = (
        contract_id="d3-rev10-direct-hybridized-grid-plan.v1",
        refinement_level=0,
        candidate=candidate,
        fixed_input_canonical_sha256=inputs.source_identity.canonical_sha256,
        counts=fixed_topology_counts,
        boundaries_m=fixed_topology_boundaries,
    )
    fixed_topology_plan = D3DirectHybridizedGridPlan(
        fixed_topology_payload.contract_id,
        fixed_topology_payload.refinement_level,
        fixed_topology_payload.candidate,
        fixed_topology_payload.fixed_input_canonical_sha256,
        fixed_topology_payload.counts,
        fixed_topology_payload.boundaries_m,
        bytes2hex(SHA.sha256(codeunits(
            SuperconductingCircuitsCore.JSON3.write(fixed_topology_payload),
        ))),
    )
    @test _d3_validate_targeted_schur_grid_plan(
        candidate,
        inputs,
        fixed_topology_plan,
    ) === fixed_topology_plan
    @test_throws ErrorException _d3_validate_stage2_direct_grid_plan(
        candidate,
        inputs,
        fixed_topology_plan,
    )
    for level in 1:3
        @test all(
            getproperty(plans[level + 1].counts, name) ==
                2 * getproperty(plans[level].counts, name)
            for name in propertynames(plans[level].counts)
        )
    end
    @test propertynames(plans[1].counts) == (
        :readout_resonator,
        :filter_resonator,
        :mtl,
        :feedline_left,
        :feedline_right,
    )
    @test propertynames(plans[1].boundaries_m) == (
        :readout_resonator_boundaries_m,
        :filter_resonator_boundaries_m,
        :feedline_left_boundaries_m,
        :feedline_right_boundaries_m,
    )
    @test all(
        length(getproperty(plans[1].boundaries_m, name)) ==
            getproperty(plans[1].counts, Symbol(replace(
                String(name),
                "_boundaries_m" => "",
            ))) + 1
        for name in propertynames(plans[1].boundaries_m)
    )

    tampered_counts = merge(
        plans[1].counts,
        (readout_resonator=plans[1].counts.readout_resonator + 1,),
    )
    tampered = D3DirectHybridizedGridPlan(
        plans[1].contract_id,
        plans[1].refinement_level,
        plans[1].candidate,
        plans[1].fixed_input_canonical_sha256,
        tampered_counts,
        plans[1].boundaries_m,
        plans[1].canonical_sha256,
    )
    @test_throws ErrorException _d3_validate_stage2_direct_grid_plan(
        candidate,
        inputs,
        tampered,
    )
    changed_readout = copy(
        plans[1].boundaries_m.readout_resonator_boundaries_m,
    )
    changed_readout[2] += 1.0e-12
    tampered_boundaries = merge(plans[1].boundaries_m, (
        readout_resonator_boundaries_m=changed_readout,
    ))
    tampered_array = D3DirectHybridizedGridPlan(
        plans[1].contract_id,
        plans[1].refinement_level,
        plans[1].candidate,
        plans[1].fixed_input_canonical_sha256,
        plans[1].counts,
        tampered_boundaries,
        plans[1].canonical_sha256,
    )
    @test_throws ErrorException _d3_validate_stage2_direct_grid_plan(
        candidate,
        inputs,
        tampered_array,
    )

    selected = _d3_selected_q2d_line_input(q2d)
    lines = _d3_hybridized_fixed_line_keywords(selected)
    grid = plans[1]
    built = build_d3_intrinsic_purcell_hybridized_circuit_plan(;
        id="d3-direct-hybridized-exact-grid-test",
        idc_filter_ground_capacitance_f=20.0e-15,
        idc_feedline_ground_capacitance_f=20.0e-15,
        idc_mutual_capacitance_f=10.0e-15,
        readout_length_m=
            candidate.lr_short_m + candidate.lc_m + candidate.lr_open_m,
        filter_length_m=
            candidate.lp_short_m + candidate.lc_m + candidate.lp_open_m,
        window_start_readout_m=candidate.lr_short_m,
        window_start_filter_m=candidate.lp_short_m,
        window_length_m=candidate.lc_m,
        mtl_section_length_m=candidate.lc_m / grid.counts.mtl,
        readout_l_per_m_h=lines.readout_l_per_m_h,
        readout_c_per_m_f=lines.readout_c_per_m_f,
        filter_l_per_m_h=lines.filter_l_per_m_h,
        filter_c_per_m_f=lines.filter_c_per_m_f,
        l_matrix_per_m_h=lines.l_matrix_per_m_h,
        c_matrix_per_m_f=lines.c_matrix_per_m_f,
        coupling_orientation=lines.coupling_orientation,
        c0r_f=20.0e-15,
        c01_f=20.0e-15,
        c02_f=20.0e-15,
        c12_qubit_f=10.0e-15,
        cr1_f=5.0e-15,
        cr2_f=5.0e-15,
        l_j_per_junction_h=20.0e-9,
        feedline...,
        feedline_n_sections=
            grid.counts.feedline_left + grid.counts.feedline_right,
        readout_breakpoints_m=
            grid.boundaries_m.readout_resonator_boundaries_m,
        filter_breakpoints_m=
            grid.boundaries_m.filter_resonator_boundaries_m,
        feedline_left_breakpoints_m=
            grid.boundaries_m.feedline_left_boundaries_m,
        feedline_right_breakpoints_m=
            grid.boundaries_m.feedline_right_boundaries_m,
    )
    actual_arrays = (
        readout_resonator_boundaries_m=
            built.component.filter.readout_resonator.line.section_boundaries_m,
        filter_resonator_boundaries_m=
            built.component.filter.filter_resonator.line.section_boundaries_m,
        feedline_left_boundaries_m=built.feedline.left.section_boundaries_m,
        feedline_right_boundaries_m=built.feedline.right.section_boundaries_m,
    )
    for name in propertynames(actual_arrays)
        actual = getproperty(actual_arrays, name)
        requested = getproperty(grid.boundaries_m, name)
        @test actual == requested
    end

    model = d3_hybridized_compiled_model(built)
    topology = _d3_targeted_topology(candidate, grid)
    function fixed_node_test_model(test_candidate)
        boundaries = _d3_targeted_candidate_boundaries(
            test_candidate,
            topology,
            grid,
        )
        test_built = build_d3_intrinsic_purcell_hybridized_circuit_plan(;
            id="d3-fixed-node-kernel-exactness-test",
            idc_filter_ground_capacitance_f=20.0e-15,
            idc_feedline_ground_capacitance_f=20.0e-15,
            idc_mutual_capacitance_f=10.0e-15,
            readout_length_m=test_candidate.lr_short_m + test_candidate.lc_m + test_candidate.lr_open_m,
            filter_length_m=test_candidate.lp_short_m + test_candidate.lc_m + test_candidate.lp_open_m,
            window_start_readout_m=test_candidate.lr_short_m,
            window_start_filter_m=test_candidate.lp_short_m,
            window_length_m=test_candidate.lc_m,
            mtl_section_length_m=test_candidate.lc_m / topology.readout.mtl,
            readout_l_per_m_h=lines.readout_l_per_m_h,
            readout_c_per_m_f=lines.readout_c_per_m_f,
            filter_l_per_m_h=lines.filter_l_per_m_h,
            filter_c_per_m_f=lines.filter_c_per_m_f,
            l_matrix_per_m_h=lines.l_matrix_per_m_h,
            c_matrix_per_m_f=lines.c_matrix_per_m_f,
            coupling_orientation=lines.coupling_orientation,
            c0r_f=20.0e-15,
            c01_f=20.0e-15,
            c02_f=20.0e-15,
            c12_qubit_f=10.0e-15,
            cr1_f=5.0e-15,
            cr2_f=5.0e-15,
            l_j_per_junction_h=20.0e-9,
            feedline...,
            feedline_n_sections=topology.feedline_left + topology.feedline_right,
            readout_breakpoints_m=boundaries.readout_resonator_boundaries_m,
            filter_breakpoints_m=boundaries.filter_resonator_boundaries_m,
            feedline_left_breakpoints_m=boundaries.feedline_left_boundaries_m,
            feedline_right_breakpoints_m=boundaries.feedline_right_boundaries_m,
        )
        return d3_hybridized_compiled_model(test_built)
    end
    trained_candidate = merge(candidate, (lr_open_m=1.1 * candidate.lr_open_m,))
    validation_candidate = merge(candidate, (lr_open_m=0.95 * candidate.lr_open_m,))
    trained_model = fixed_node_test_model(trained_candidate)
    validation_model = fixed_node_test_model(validation_candidate)
    c_term = (trained_model.capacitance - model.capacitance) /
        (trained_candidate.lr_open_m - candidate.lr_open_m)
    k_term = (trained_model.inverse_inductance - model.inverse_inductance) /
        (inv(trained_candidate.lr_open_m) - inv(candidate.lr_open_m))
    reconstructed_c = model.capacitance +
        (validation_candidate.lr_open_m - candidate.lr_open_m) .* c_term
    reconstructed_k = model.inverse_inductance +
        (inv(validation_candidate.lr_open_m) - inv(candidate.lr_open_m)) .* k_term
    @test maximum(abs, reconstructed_c - validation_model.capacitance) <=
        4096 * eps(Float64) * maximum(abs, validation_model.capacitance)
    @test maximum(abs, reconstructed_k - validation_model.inverse_inductance) <=
        4096 * eps(Float64) * maximum(abs, validation_model.inverse_inductance)

    context = _d3_complete_complement_rp_context(model, (
        maximum_elimination_condition_number=1.0e10,
        maximum_relative_elimination_solve_residual=1.0e-10,
        maximum_relative_reciprocity_error=1.0e-12,
        maximum_relative_passivity_violation=1.0e-12,
        maximum_relative_root_residual=1.0e-10,
        maximum_root_growth_rate_hz=1.0,
        minimum_normalized_residue_slope=1.0e-3,
        maximum_relative_coupling_spread=1.0e-2,
        maximum_relative_determinant_closure_error=1.0e-10,
    ))
    @test context.retained_indices == [
        model.anchored_coordinate_indices.r,
        model.anchored_coordinate_indices.p,
    ]
    @test context.coordinate_order[context.retained_indices[1]] != :r
    @test context.coordinate_order[context.retained_indices[2]] != :p
    for (coordinate, retained_index) in ((:r, 1), (:p, 2))
        principal = _d3_complete_complement_rp_principal_indices(
            context,
            coordinate,
        )
        @test first(principal) == context.retained_indices[retained_index]
        @test principal[2:end] == context.eliminated_indices
    end
    @test_throws ErrorException _d3_complete_complement_rp_principal_indices(
        context,
        :q,
    )

    cared = D3TargetedSchurCaredOutput(
        D3_TARGETED_SCHUR_CARED_OUTPUT_CONTRACT,
        :stage2_direct_hybridized,
        :hybridized_distributed_lumped,
        5.6e9,
        candidate,
        5.6e9,
        5.6e9,
        5.0e9,
        5.0e6,
        (r=5.6e9 - 10.0e6im, p=5.6e9 - 10.0e6im),
        (r=1.0 + 0.0im, p=1.0 + 0.0im),
        (r=20.0e6, p=20.0e6),
        40.0e6,
        (model_identity=(circuit_plan_sha256=repeat("b", 64),),),
        (counts=grid.counts, boundaries_m=grid.boundaries_m),
        (complement=:complete_hybridized_complement,),
        (status=:pass,),
    )
    @test all(
        getproperty(cared, name) isa Float64
        for name in (
            :slot_hz,
            :f_r_eff_hz,
            :f_p_eff_hz,
            :f_n_hz,
            :abs_real_J_eff_hz,
            :kappa_sum_anchored_bare_rp_hz,
        )
    )
end
