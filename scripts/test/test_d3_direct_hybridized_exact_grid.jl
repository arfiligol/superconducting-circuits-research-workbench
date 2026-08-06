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

@testset "D3 direct-Hybridized exact grid plan" begin
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

    cared = D3DirectHybridizedCaredOutput(
        D3_DIRECT_HYBRIDIZED_CARED_OUTPUT_CONTRACT,
        :stage2_direct_hybridized,
        :hybridized_distributed_lumped,
        5.6e9,
        candidate,
        5.6e9,
        5.6e9,
        5.0e9,
        5.0e6,
        20.0e6,
        0.5,
        0.5,
        (model_identity=(circuit_plan_sha256=repeat("b", 64),),),
        (counts=grid.counts, boundaries_m=grid.boundaries_m),
        (complement=:complete_hybridized_complement,),
        (status=:pass,),
    )
    @test propertynames(cared) == (
        :contract_id,
        :stage_id,
        :model_family,
        :slot_hz,
        :candidate,
        :f_r_eff_hz,
        :f_p_eff_hz,
        :f_n_hz,
        :abs_real_J_eff_hz,
        :unordered_rp_kappa_sum_hz,
        :unordered_rp_linewidth_fraction_min,
        :unordered_rp_linewidth_fraction_max,
        :source_profile_identity,
        :grid_identity,
        :extraction_profile,
        :validity,
    )
    @test all(
        getproperty(cared, name) isa Float64
        for name in (
            :slot_hz,
            :f_r_eff_hz,
            :f_p_eff_hz,
            :f_n_hz,
            :abs_real_J_eff_hz,
            :unordered_rp_kappa_sum_hz,
            :unordered_rp_linewidth_fraction_min,
            :unordered_rp_linewidth_fraction_max,
        )
    )
end
