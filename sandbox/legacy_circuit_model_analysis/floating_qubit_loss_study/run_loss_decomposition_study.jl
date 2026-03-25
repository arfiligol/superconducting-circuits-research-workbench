using JosephsonCircuits
using Printf
using CSV
using DataFrames
using Base.Threads

include(joinpath(@__DIR__, "..", "Reusable Component", "ReusableComponents.jl"))
using .ReusableComponents

include(joinpath(@__DIR__, "progress_helpers.jl"))
include(joinpath(@__DIR__, "common.jl"))

# =============================================================================
# 1. User-Editable Study Targets
# =============================================================================

# Target qubit frequency for the XY-only baseline reference.
const BASELINE_TARGET_F_GHZ = 4.00
# Preferred readout-only / XY-only loss ratio for the candidate-selection step.
const READOUT_RATIO_COMPARISON_TARGET = 0.20
# Minimum acceptable readout-only / XY-only loss ratio during candidate selection.
const READOUT_RATIO_ACCEPTABLE_MIN = 0.15
# Maximum acceptable readout-only / XY-only loss ratio during candidate selection.
const READOUT_RATIO_ACCEPTABLE_MAX = 0.30
# Fine Lq sweep half-window used after the coarse XY-only matched search.
const XY_MATCH_FINE_HALF_WINDOW_H = 0.50 * nH
# Fine Lq sweep step used after the coarse XY-only matched search.
const XY_MATCH_FINE_STEP_H = 0.02 * nH
# Whether the RO-only candidate sweep should parallelize across Julia threads.
const USE_THREADED_CANDIDATE_SWEEP = true
# Keep the script alive after plotting so the temporary PlotlyJS server does not disappear immediately.
const HOLD_AFTER_PLOTTING = true

# Pad-1 to ground capacitance of the floating qubit.
const C_G1_F = 102.38399 * fF
# Pad-2 to ground capacitance of the floating qubit.
const C_G2_F = 102.33597 * fF
# Pad-to-pad differential capacitance of the floating qubit.
const C_Q_F = 59.25219 * fF
# XY coupling capacitance from the XY node to qubit pad 1.
const XY_C_XY1_F = 2.5 * fF
# XY coupling capacitance from the XY node to qubit pad 2.
const XY_C_XY2_F = 2.3 * fF

# Uncoupled readout-line / PF / QWR per-unit-length series inductance.
const COMMON_L_PER_M_H = 404.313e-9
# Uncoupled readout-line / PF / QWR per-unit-length shunt capacitance.
const COMMON_C_PER_M_F = 179.86e-12
# Uncoupled readout-line / PF / QWR per-unit-length series resistance.
const COMMON_R_PER_M_OHM = 0.0
# Uncoupled readout-line / PF / QWR per-unit-length shunt conductance.
const COMMON_G_PER_M_S = 0.0

# Artificial probe-port termination on qubit pad 1 and pad 2 before PTC.
const QUBIT_PORT_RES_OHM = 50.0
# Termination on the XY environment port.
const XY_PORT_RES_OHM = 50.0
# Termination on the two readout-line ports.
const READOUT_PORT_RES_OHM = 50.0

# Readout-line physical length before the Purcell filter.
const LEFT_READOUT_LENGTH_M = 3462.732 * um
# Half-wave Purcell-filter physical length.
const PURCELL_FILTER_LENGTH_M = 9900.32 * um
# Readout-line physical length after the Purcell filter.
const RIGHT_READOUT_LENGTH_M = 3462.732 * um
# Hanging quarter-wave resonator physical length.
const QWR_LENGTH_M = 4731.6735 * um
# Coupling capacitor between the input readout line and the Purcell filter.
const PF_COUPLING_CAP_IN_F = 41.06185 * fF
# Coupling capacitor between the Purcell filter and the output readout line.
const PF_COUPLING_CAP_OUT_F = 125.2587 * fF
# Start position of the PF-QWR coupled window along the Purcell filter.
const PF_WINDOW_START_M = 2200.0 * um
# Start position of the PF-QWR coupled window along the QWR, measured from the QWR open end.
const QWR_WINDOW_START_M = 10.0 * um

# Discretization target Δz for the left readout line.
const LEFT_READOUT_TARGET_DZ_M = 150.0 * um
# Discretization target Δz for the Purcell filter.
const PURCELL_FILTER_TARGET_DZ_M = 150.0 * um
# Discretization target Δz for the right readout line.
const RIGHT_READOUT_TARGET_DZ_M = 150.0 * um
# Discretization target Δz for the QWR.
const QWR_TARGET_DZ_M = 150.0 * um
# Discretization target Δz for the coupled window.
const COUPLED_WINDOW_TARGET_DZ_M = 15.0 * um

# Coupled-window parameterization mode.
const COUPLED_WINDOW_INPUT_MODE = :q2d_rlgc
# Even-mode impedance if the modal parameterization is used.
const COUPLED_WINDOW_ZEVEN_OHM = 56.0
# Odd-mode impedance if the modal parameterization is used.
const COUPLED_WINDOW_ZODD_OHM = 44.0
# Even-mode index if the modal parameterization is used.
const COUPLED_WINDOW_NEVEN = 2.45
# Odd-mode index if the modal parameterization is used.
const COUPLED_WINDOW_NODD = 2.60

# Q2D L11 per unit length for the coupled window.
const Q2D_L11_PER_M_H = 410.86374e-9
# Q2D L22 per unit length for the coupled window.
const Q2D_L22_PER_M_H = 410.85454e-9
# Q2D mutual inductance per unit length for the coupled window.
const Q2D_M_PER_M_H = 19.08527e-9
# Q2D Maxwell C11 per unit length for the coupled window.
const Q2D_C11_MAXWELL_PER_M_F = 170.29805e-12
# Q2D Maxwell C22 per unit length for the coupled window.
const Q2D_C22_MAXWELL_PER_M_F = 170.29538e-12
# Q2D Maxwell C12 per unit length for the coupled window.
const Q2D_C12_MAXWELL_PER_M_F = -8.09678e-12
# Q2D Maxwell C21 per unit length for the coupled window.
const Q2D_C21_MAXWELL_PER_M_F = -8.09678e-12
# Optional Q2D per-unit-length resistance for line 1.
const Q2D_R11_PER_M_OHM = 0.0
# Optional Q2D per-unit-length resistance for line 2.
const Q2D_R22_PER_M_OHM = 0.0
# Optional Q2D per-unit-length conductance for line 1.
const Q2D_G11_PER_M_S = 0.0
# Optional Q2D per-unit-length conductance for line 2.
const Q2D_G22_PER_M_S = 0.0

# Coupled-window lengths to sweep while keeping PF and QWR resonant lengths fixed.
const COUPLED_WINDOW_LENGTH_CANDIDATES_M = [
    150.0 * um,
    200.0 * um,
    250.0 * um,
    300.0 * um,
    350.0 * um,
    400.0 * um,
    450.0 * um,
    500.0 * um,
    550.0 * um,
    600.0 * um,
]

# Explicit qubit-readout coupling-capacitance candidates.
const READOUT_COUPLING_CANDIDATES = [
    (label="rq_2p5_2p3", c_rq1_f=2.5 * fF, c_rq2_f=2.3 * fF),
    (label="rq_5p0_4p6", c_rq1_f=5.0 * fF, c_rq2_f=4.6 * fF),
    (label="rq_7p5_6p9", c_rq1_f=7.5 * fF, c_rq2_f=6.9 * fF),
    (label="rq_10p0_9p2", c_rq1_f=10.0 * fF, c_rq2_f=9.2 * fF),
    (label="rq_12p5_11p5", c_rq1_f=12.5 * fF, c_rq2_f=11.5 * fF),
    (label="rq_15p0_13p8", c_rq1_f=15.0 * fF, c_rq2_f=13.8 * fF),
    (label="rq_17p5_16p1", c_rq1_f=17.5 * fF, c_rq2_f=16.1 * fF),
    (label="rq_20p0_18p4", c_rq1_f=20.0 * fF, c_rq2_f=18.4 * fF),
    (label="rq_22p5_20p7", c_rq1_f=22.5 * fF, c_rq2_f=20.7 * fF),
    (label="rq_25p0_23p0", c_rq1_f=25.0 * fF, c_rq2_f=23.0 * fF),
    (label="rq_27p5_25p3", c_rq1_f=27.5 * fF, c_rq2_f=25.3 * fF),
    (label="rq_30p0_27p6", c_rq1_f=30.0 * fF, c_rq2_f=27.6 * fF),
    (label="rq_35p0_32p2", c_rq1_f=35.0 * fF, c_rq2_f=32.2 * fF),
    (label="rq_40p0_36p8", c_rq1_f=40.0 * fF, c_rq2_f=36.8 * fF),
    (label="rq_50p0_46p0", c_rq1_f=50.0 * fF, c_rq2_f=46.0 * fF),
    (label="rq_60p0_55p2", c_rq1_f=60.0 * fF, c_rq2_f=55.2 * fF),
    (label="rq_80p0_73p6", c_rq1_f=80.0 * fF, c_rq2_f=73.6 * fF),
    (label="rq_100p0_92p0", c_rq1_f=100.0 * fF, c_rq2_f=92.0 * fF),
]

# Candidate Lq values used when matching the extracted qubit resonance to a target frequency.
const LQ_SWEEP_VALUES_H = collect(10.0:0.25:28.0) .* nH

# Frequency sweep used for the qubit-admittance extraction.
const QUBIT_SWEEP_START_GHZ = 3.0
const QUBIT_SWEEP_STOP_GHZ = 4.6
const QUBIT_SWEEP_STEP_GHZ = 0.002

# Frequency sweep used for the readout-line S21 / vector-fitting analysis.
const READOUT_S21_SWEEP_START_GHZ = 4.4
const READOUT_S21_SWEEP_STOP_GHZ = 7.0
const READOUT_S21_SWEEP_STEP_GHZ = 0.002

# Vector-fitting setup for the readout-line S21 model.
const VF_EXPECTED_RESONATORS = 2
const VF_BACKGROUND_POLES = 2

base_cfg = StudyConfig(
    c_g1_f=C_G1_F,
    c_g2_f=C_G2_F,
    c_q_f=C_Q_F,
    c_xy1_f=XY_C_XY1_F,
    c_xy2_f=XY_C_XY2_F,
    c_rq1_f=0.0,
    c_rq2_f=0.0,
    common_l_per_m_h=COMMON_L_PER_M_H,
    common_c_per_m_f=COMMON_C_PER_M_F,
    common_r_per_m_ohm=COMMON_R_PER_M_OHM,
    common_g_per_m_s=COMMON_G_PER_M_S,
    left_readout_length_m=LEFT_READOUT_LENGTH_M,
    purcell_filter_length_m=PURCELL_FILTER_LENGTH_M,
    right_readout_length_m=RIGHT_READOUT_LENGTH_M,
    qwr_length_m=QWR_LENGTH_M,
    left_readout_target_dz_m=LEFT_READOUT_TARGET_DZ_M,
    purcell_filter_target_dz_m=PURCELL_FILTER_TARGET_DZ_M,
    right_readout_target_dz_m=RIGHT_READOUT_TARGET_DZ_M,
    qwr_target_dz_m=QWR_TARGET_DZ_M,
    coupled_window_target_dz_m=COUPLED_WINDOW_TARGET_DZ_M,
    pf_coupling_cap_in_f=PF_COUPLING_CAP_IN_F,
    pf_coupling_cap_out_f=PF_COUPLING_CAP_OUT_F,
    coupled_window_input_mode=COUPLED_WINDOW_INPUT_MODE,
    coupled_window_length_m=first(COUPLED_WINDOW_LENGTH_CANDIDATES_M),
    pf_window_start_m=PF_WINDOW_START_M,
    qwr_window_start_m=QWR_WINDOW_START_M,
    coupled_window_zeven_ohm=COUPLED_WINDOW_ZEVEN_OHM,
    coupled_window_zodd_ohm=COUPLED_WINDOW_ZODD_OHM,
    coupled_window_neven=COUPLED_WINDOW_NEVEN,
    coupled_window_nodd=COUPLED_WINDOW_NODD,
    q2d_l11_per_m_h=Q2D_L11_PER_M_H,
    q2d_l22_per_m_h=Q2D_L22_PER_M_H,
    q2d_m_per_m_h=Q2D_M_PER_M_H,
    q2d_c11_maxwell_per_m_f=Q2D_C11_MAXWELL_PER_M_F,
    q2d_c22_maxwell_per_m_f=Q2D_C22_MAXWELL_PER_M_F,
    q2d_c12_maxwell_per_m_f=Q2D_C12_MAXWELL_PER_M_F,
    q2d_c21_maxwell_per_m_f=Q2D_C21_MAXWELL_PER_M_F,
    q2d_r11_per_m_ohm=Q2D_R11_PER_M_OHM,
    q2d_r22_per_m_ohm=Q2D_R22_PER_M_OHM,
    q2d_g11_per_m_s=Q2D_G11_PER_M_S,
    q2d_g22_per_m_s=Q2D_G22_PER_M_S,
    qubit_port_res_ohm=QUBIT_PORT_RES_OHM,
    xy_port_res_ohm=XY_PORT_RES_OHM,
    readout_port_res_ohm=READOUT_PORT_RES_OHM,
    sweep_start_ghz=QUBIT_SWEEP_START_GHZ,
    sweep_stop_ghz=QUBIT_SWEEP_STOP_GHZ,
    sweep_step_ghz=QUBIT_SWEEP_STEP_GHZ,
)

# =============================================================================
# 2. Helper Functions
# =============================================================================

function config_with_readout_coupling(cfg::StudyConfig, coupling_candidate)
    return updated_config(
        cfg;
        c_rq1_f=coupling_candidate.c_rq1_f,
        c_rq2_f=coupling_candidate.c_rq2_f,
    )
end

function config_with_coupled_window_length(cfg::StudyConfig, coupled_window_length_m)
    return updated_config(cfg; coupled_window_length_m=coupled_window_length_m)
end

function config_without_xy(cfg::StudyConfig)
    return updated_config(cfg; c_xy1_f=0.0, c_xy2_f=0.0)
end

function simulate_best_near_target(
    base_cfg::StudyConfig,
    target_f_ghz;
    lq_values_h,
    label_prefix,
    progress_name::AbstractString="",
    progress_parentid=ROOT_PROGRESS_PARENT,
)
    sweep_df = scan_lq_values(
        base_cfg,
        lq_values_h;
        label_prefix=label_prefix,
        progress_name=progress_name,
        progress_parentid=progress_parentid,
    )
    best_row = select_nearest_frequency(sweep_df, target_f_ghz)
    cfg = updated_config(base_cfg; l_q_h=best_row.lq_nh * nH)
    result = simulate_case(cfg; label=label_prefix)
    return (result=result, sweep_df=sweep_df, best_row=best_row)
end

function build_readout_candidate_specs()
    specs = NamedTuple[]
    candidate_index = 0
    for coupled_window_length_m in COUPLED_WINDOW_LENGTH_CANDIDATES_M
        for coupling_candidate in READOUT_COUPLING_CANDIDATES
            candidate_index += 1
            push!(
                specs,
                (
                    candidate_index=candidate_index,
                    coupled_window_length_m=coupled_window_length_m,
                    coupling_candidate=coupling_candidate,
                ),
            )
        end
    end
    return specs
end

function simulate_ro_only_candidate_row(
    base_cfg::StudyConfig,
    candidate_spec,
    baseline_lq_h,
    g_xy_baseline_s,
)
    coupled_window_length_m = candidate_spec.coupled_window_length_m
    coupling_candidate = candidate_spec.coupling_candidate
    window_cfg = config_with_coupled_window_length(base_cfg, coupled_window_length_m)
    readout_cfg = config_with_readout_coupling(window_cfg, coupling_candidate)

    ro_only_cfg = updated_config(config_without_xy(readout_cfg); l_q_h=baseline_lq_h)
    ro_only_case = simulate_case(
        ro_only_cfg;
        label="readout_only_window_$(coupled_window_length_m / um)_$(coupling_candidate.label)",
    )

    return (
        candidate_index=candidate_spec.candidate_index,
        window_label=@sprintf("window_%.0f_um", coupled_window_length_m / um),
        coupling_label=String(coupling_candidate.label),
        coupled_window_length_um=coupled_window_length_m / um,
        c_rq1_ff=coupling_candidate.c_rq1_f / fF,
        c_rq2_ff=coupling_candidate.c_rq2_f / fF,
        baseline_lq_nh=baseline_lq_h / nH,
        readout_only_fq_ghz=ro_only_case.crossed ? ro_only_case.fq_ghz : NaN,
        readout_only_re_y_s=ro_only_case.crossed ? ro_only_case.G_resonance_s : NaN,
        readout_to_xy_ratio=ro_only_case.crossed ? ro_only_case.G_resonance_s / g_xy_baseline_s : NaN,
        readout_only_crossed=ro_only_case.crossed,
    )
end

function run_readout_candidate_sweep(
    base_cfg::StudyConfig,
    baseline_lq_h,
    g_xy_baseline_s;
    use_threaded::Bool=USE_THREADED_CANDIDATE_SWEEP,
)
    candidate_specs = build_readout_candidate_specs()
    total_candidates = length(candidate_specs)
    candidate_rows = Vector{Any}(undef, total_candidates)
    completed_count = Atomic{Int}(0)
    threaded_mode = use_threaded && nthreads() > 1

    with_progress_scope("Readout candidate sweep") do candidate_progress_id
        if threaded_mode
            @threads for spec_index in eachindex(candidate_specs)
                candidate_spec = candidate_specs[spec_index]
                row = simulate_ro_only_candidate_row(
                    base_cfg,
                    candidate_spec,
                    baseline_lq_h,
                    g_xy_baseline_s,
                )
                candidate_rows[spec_index] = row
                finished = atomic_add!(completed_count, 1) + 1
                update_progress!(
                    candidate_progress_id,
                    finished,
                    total_candidates;
                    name=@sprintf(
                        "window = %.0f um | coupling = %s",
                        candidate_spec.coupled_window_length_m / um,
                        candidate_spec.coupling_candidate.label,
                    ),
                )
            end
        else
            for spec_index in eachindex(candidate_specs)
                candidate_spec = candidate_specs[spec_index]
                candidate_rows[spec_index] = simulate_ro_only_candidate_row(
                    base_cfg,
                    candidate_spec,
                    baseline_lq_h,
                    g_xy_baseline_s,
                )
                finished = atomic_add!(completed_count, 1) + 1
                update_progress!(
                    candidate_progress_id,
                    finished,
                    total_candidates;
                    name=@sprintf(
                        "window = %.0f um | coupling = %s",
                        candidate_spec.coupled_window_length_m / um,
                        candidate_spec.coupling_candidate.label,
                    ),
                )
            end
        end
    end

    candidate_df = DataFrame(candidate_rows)
    sort!(candidate_df, :candidate_index)
    return candidate_df
end

function choose_best_candidate(df::DataFrame)
    ratio_score = abs.(df.readout_to_xy_ratio .- READOUT_RATIO_COMPARISON_TARGET)
    ordered_indices = sortperm(
        eachindex(ratio_score);
        by=i -> (ratio_score[i], df.coupled_window_length_um[i], df.c_rq1_ff[i], df.c_rq2_ff[i]),
    )
    return df[first(ordered_indices), :]
end

function build_fine_lq_values(
    coarse_best_lq_h;
    coarse_lq_values_h,
    half_window_h,
    step_h,
)
    lower_bound_h = maximum((minimum(coarse_lq_values_h), coarse_best_lq_h - half_window_h))
    upper_bound_h = minimum((maximum(coarse_lq_values_h), coarse_best_lq_h + half_window_h))
    fine_values_h = collect(lower_bound_h:step_h:upper_bound_h)
    if isempty(fine_values_h) || last(fine_values_h) < upper_bound_h
        push!(fine_values_h, upper_bound_h)
    end
    if !(coarse_best_lq_h in fine_values_h)
        push!(fine_values_h, coarse_best_lq_h)
        sort!(fine_values_h)
    end
    return unique(fine_values_h)
end

function simulate_best_near_target_two_stage(
    base_cfg::StudyConfig,
    target_f_ghz;
    coarse_lq_values_h,
    fine_half_window_h,
    fine_step_h,
    label_prefix,
    coarse_progress_name::AbstractString="",
    fine_progress_name::AbstractString="",
)
    coarse_result = simulate_best_near_target(
        base_cfg,
        target_f_ghz;
        lq_values_h=coarse_lq_values_h,
        label_prefix="$(label_prefix)_coarse",
        progress_name=coarse_progress_name,
    )
    fine_lq_values_h = build_fine_lq_values(
        coarse_result.best_row.lq_nh * nH;
        coarse_lq_values_h=coarse_lq_values_h,
        half_window_h=fine_half_window_h,
        step_h=fine_step_h,
    )
    fine_result = simulate_best_near_target(
        base_cfg,
        target_f_ghz;
        lq_values_h=fine_lq_values_h,
        label_prefix=label_prefix,
        progress_name=fine_progress_name,
    )
    return (
        result=fine_result.result,
        best_row=fine_result.best_row,
        coarse_sweep_df=coarse_result.sweep_df,
        fine_sweep_df=fine_result.sweep_df,
    )
end

function run_vector_fitting_helper(raw_csv_path, model_csv_path, resonance_csv_path)
    helper_path = joinpath(@__DIR__, "fit_readout_s21_vector_fitting.py")
    cmd = `uv run python $helper_path --input-csv $raw_csv_path --model-csv $model_csv_path --resonance-csv $resonance_csv_path --resonators $(VF_EXPECTED_RESONATORS) --bg-poles $(VF_BACKGROUND_POLES)`
    run(cmd)
end

function run_loss_decomposition_study()
    println("============================================================")
    println("Floating-Qubit Loss Decomposition Study")
    println("============================================================")
    println("PTC -> CT -> Kron reduction is always applied on the qubit ports only.")
    println("PF and QWR resonant lengths are fixed; only coupled-window length and C_rq1/C_rq2 are swept on the readout side.")
    println()
    @printf(
        "Threaded candidate sweep: %s (Julia threads available: %d)\n\n",
        USE_THREADED_CANDIDATE_SWEEP && nthreads() > 1 ? "enabled" : "disabled",
        nthreads(),
    )

    xy_only_cfg = updated_config(base_cfg; c_rq1_f=0.0, c_rq2_f=0.0)
    println("Stage 1/6: XY-only baseline reference sweep")
    xy_baseline = simulate_best_near_target(
        xy_only_cfg,
        BASELINE_TARGET_F_GHZ;
        lq_values_h=LQ_SWEEP_VALUES_H,
        label_prefix="xy_only_baseline",
        progress_name="XY-only baseline Lq sweep",
    )
    xy_baseline.result.crossed || error("XY-only baseline sweep did not find an Im(Ydm)=0 crossing near the requested target.")

    G_xy_baseline = xy_baseline.result.G_resonance_s
    LQ_BASELINE_H = xy_baseline.result.config.l_q_h
    baseline_fq_ghz = xy_baseline.result.fq_ghz

    @printf(
        "XY-only baseline  : Lq = %.3f nH, fq = %.6f GHz, Re(Ydm) = %.6e S\n",
        LQ_BASELINE_H / nH,
        baseline_fq_ghz,
        G_xy_baseline,
    )
    println()

    println("Stage 2/6: RO-only candidate sweep at the XY-only baseline Lq")
    candidate_df = run_readout_candidate_sweep(
        base_cfg,
        LQ_BASELINE_H,
        G_xy_baseline;
        use_threaded=USE_THREADED_CANDIDATE_SWEEP,
    )
    valid_candidate_mask = candidate_df.readout_only_crossed .& .!isnan.(candidate_df.readout_to_xy_ratio)
    any(valid_candidate_mask) || error("No RO-only candidate produced a valid Im(Ydm)=0 crossing at the XY-only baseline Lq.")
    valid_candidate_df = candidate_df[valid_candidate_mask, :]
    ratio_mask = (READOUT_RATIO_ACCEPTABLE_MIN .<= valid_candidate_df.readout_to_xy_ratio) .&
                 (valid_candidate_df.readout_to_xy_ratio .<= READOUT_RATIO_ACCEPTABLE_MAX)

    if any(ratio_mask)
        selected_row = choose_best_candidate(valid_candidate_df[ratio_mask, :])
        selection_note = "ratio window satisfied"
    else
        selected_row = choose_best_candidate(valid_candidate_df)
        selection_note = "closest readout/XY ratio overall"
    end

    selected_coupling = only(filter(c -> c.label == selected_row.coupling_label, READOUT_COUPLING_CANDIDATES))
    selected_base_cfg = config_with_readout_coupling(
        config_with_coupled_window_length(base_cfg, selected_row.coupled_window_length_um * um),
        selected_coupling,
    )

    println("Readout-candidate sweep summary:")
    @printf("  selected coupled-window     = %.1f um\n", selected_row.coupled_window_length_um)
    @printf("  selected coupling candidate = %s\n", selected_row.coupling_label)
    @printf("  selection rule              = %s\n", selection_note)
    @printf("  readout-only / xy-only      = %.4f\n", selected_row.readout_to_xy_ratio)
    @printf("  selected C_rq1, C_rq2       = %.3f fF, %.3f fF\n", selected_row.c_rq1_ff, selected_row.c_rq2_ff)
    println()

    println("Stage 3/6: Selected RO-only and XY + Readout at the same baseline Lq")
    readout_selected = simulate_case(
        updated_config(config_without_xy(selected_base_cfg); l_q_h=LQ_BASELINE_H);
        label="readout_only_selected",
    )
    full_shift = simulate_case(
        updated_config(selected_base_cfg; l_q_h=LQ_BASELINE_H);
        label="full_coupled_baseline_lq",
    )
    readout_selected.crossed || error("The selected RO-only case does not produce an Im(Ydm)=0 crossing at the baseline Lq.")
    full_shift.crossed || error("The selected XY + Readout case does not produce an Im(Ydm)=0 crossing at the baseline Lq.")

    G_readout = readout_selected.G_resonance_s
    G_full_shift = full_shift.G_resonance_s
    target_full_shift_f_ghz = full_shift.fq_ghz

    @printf(
        "Selected RO-only  : Lq = %.3f nH, fq = %.6f GHz, Re(Ydm) = %.6e S\n",
        LQ_BASELINE_H / nH,
        readout_selected.fq_ghz,
        G_readout,
    )
    @printf(
        "Selected XY+RO    : Lq = %.3f nH, fq = %.6f GHz, Re(Ydm) = %.6e S\n",
        LQ_BASELINE_H / nH,
        target_full_shift_f_ghz,
        G_full_shift,
    )
    @printf(
        "Shift from XY base: Δfq = %.3f MHz\n",
        (target_full_shift_f_ghz - baseline_fq_ghz) * 1e3,
    )
    println()

    println("Stage 4/6: XY-only retuned to the selected XY + Readout shifted frequency")
    xy_matched = simulate_best_near_target_two_stage(
        xy_only_cfg,
        target_full_shift_f_ghz;
        coarse_lq_values_h=LQ_SWEEP_VALUES_H,
        fine_half_window_h=XY_MATCH_FINE_HALF_WINDOW_H,
        fine_step_h=XY_MATCH_FINE_STEP_H,
        label_prefix="xy_only_matched_to_full_shift",
        coarse_progress_name="XY-only matched coarse Lq sweep",
        fine_progress_name="XY-only matched fine Lq sweep",
    )

    G_xy_matched = xy_matched.result.G_resonance_s
    ideal_additive_G = G_xy_matched + G_readout
    cross_shift_G = G_full_shift - ideal_additive_G

    @printf(
        "XY-only matched   : Lq = %.3f nH, fq = %.6f GHz, Re(Ydm) = %.6e S\n",
        xy_matched.result.config.l_q_h / nH,
        xy_matched.result.fq_ghz,
        G_xy_matched,
    )
    println()

    summary_rows = [
        make_case_summary_row(
            xy_baseline.result;
            normalized_loss=1.0,
            note="reference XY-only at the baseline target frequency",
            window_label="xy_only",
            coupling_label="xy_only",
        ),
        make_case_summary_row(
            readout_selected;
            normalized_loss=G_readout / G_xy_baseline,
            note="readout-only contribution at the same bare baseline Lq",
            window_label=selected_row.window_label,
            coupling_label=selected_row.coupling_label,
        ),
        make_case_summary_row(
            full_shift;
            normalized_loss=G_full_shift / G_xy_baseline,
            note="XY + Readout using the same bare baseline Lq",
            window_label=selected_row.window_label,
            coupling_label=selected_row.coupling_label,
        ),
        make_case_summary_row(
            xy_matched.result;
            normalized_loss=G_xy_matched / G_xy_baseline,
            note="XY-only retuned to the XY + Readout shifted frequency",
            window_label="xy_only",
            coupling_label="xy_only",
        ),
        (
            case="ideal_additive_reference",
            lq_nh=NaN,
            c_xy1_ff=xy_matched.result.config.c_xy1_f / fF,
            c_xy2_ff=xy_matched.result.config.c_xy2_f / fF,
            c_rq1_ff=selected_row.c_rq1_ff,
            c_rq2_ff=selected_row.c_rq2_ff,
            coupled_window_length_um=selected_row.coupled_window_length_um,
            qwr_length_um=QWR_LENGTH_M / um,
            pf_length_um=PURCELL_FILTER_LENGTH_M / um,
            window_label=selected_row.window_label,
            coupling_label=selected_row.coupling_label,
            fq_ghz=target_full_shift_f_ghz,
            re_y_dm_s=ideal_additive_G,
            normalized_loss=ideal_additive_G / G_xy_baseline,
            crossed=true,
            note="G_xy_matched + G_readout_only at the shifted XY+RO frequency",
        ),
        (
            case="cross_term_full_shift",
            lq_nh=LQ_BASELINE_H / nH,
            c_xy1_ff=xy_matched.result.config.c_xy1_f / fF,
            c_xy2_ff=xy_matched.result.config.c_xy2_f / fF,
            c_rq1_ff=selected_row.c_rq1_ff,
            c_rq2_ff=selected_row.c_rq2_ff,
            coupled_window_length_um=selected_row.coupled_window_length_um,
            qwr_length_um=QWR_LENGTH_M / um,
            pf_length_um=PURCELL_FILTER_LENGTH_M / um,
            window_label=selected_row.window_label,
            coupling_label=selected_row.coupling_label,
            fq_ghz=target_full_shift_f_ghz,
            re_y_dm_s=cross_shift_G,
            normalized_loss=cross_shift_G / G_xy_baseline,
            crossed=true,
            note="G_full_shift - G_xy_matched - G_readout_only",
        ),
    ]
    summary_df = DataFrame(summary_rows)

    println("Stage 5/6: Diagnostic sweeps")
    xy_lq_sweep_df = scan_lq_values(
        xy_only_cfg,
        LQ_SWEEP_VALUES_H;
        label_prefix="xy_only_curve",
        progress_name="Diagnostic XY-only Lq sweep",
    )
    xy_lq_sweep_df[!, :setup] .= "XY only"

    full_lq_sweep_df = scan_lq_values(
        selected_base_cfg,
        LQ_SWEEP_VALUES_H;
        label_prefix="full_selected_curve",
        progress_name="Diagnostic XY + Readout Lq sweep",
    )
    full_lq_sweep_df[!, :setup] .= "XY + Readout"

    window_length_rows = NamedTuple[]
    total_window_lengths = length(COUPLED_WINDOW_LENGTH_CANDIDATES_M)
    with_progress_scope("Diagnostic coupled-window sweep") do window_progress_id
        for (window_index, coupled_window_length_m) in enumerate(COUPLED_WINDOW_LENGTH_CANDIDATES_M)
            cfg = config_with_readout_coupling(
                config_with_coupled_window_length(base_cfg, coupled_window_length_m),
                selected_coupling,
            )
            window_case = simulate_case(
                updated_config(cfg; l_q_h=LQ_BASELINE_H);
                label="window_length_curve_$(coupled_window_length_m / um)",
            )
            push!(
                window_length_rows,
                (
                    coupled_window_length_um=coupled_window_length_m / um,
                    lq_nh=LQ_BASELINE_H / nH,
                    fq_ghz=window_case.fq_ghz,
                    re_y_dm_s=window_case.G_resonance_s,
                ),
            )
            update_progress!(
                window_progress_id,
                window_index,
                total_window_lengths;
                name=@sprintf(
                    "window = %.0f um",
                    coupled_window_length_m / um,
                ),
            )
        end
    end
    window_length_df = DataFrame(window_length_rows)

    println("Stage 6/6: Readout-line S21 vector fitting")
    readout_characterization_cfg = config_without_xy(
        updated_config(selected_base_cfg; c_rq1_f=0.0, c_rq2_f=0.0),
    )

    selected_readout_response = simulate_readout_sparameters(
        readout_characterization_cfg;
        sweep_start_ghz=READOUT_S21_SWEEP_START_GHZ,
        sweep_stop_ghz=READOUT_S21_SWEEP_STOP_GHZ,
        sweep_step_ghz=READOUT_S21_SWEEP_STEP_GHZ,
    )

    output_dir = @__DIR__
    readout_s21_raw_csv_path = joinpath(output_dir, "selected_readout_s21_raw.csv")
    readout_s21_model_csv_path = joinpath(output_dir, "selected_readout_s21_vf_model.csv")
    readout_s21_resonance_csv_path = joinpath(output_dir, "selected_readout_s21_vf_resonances.csv")

    readout_s21_raw_df = DataFrame(
        frequency_hz=selected_readout_response.freqs_ghz .* GHz,
        frequency_ghz=selected_readout_response.freqs_ghz,
        S21_real=real.(selected_readout_response.s21),
        S21_imag=imag.(selected_readout_response.s21),
        S21_mag=abs.(selected_readout_response.s21),
        S11_real=real.(selected_readout_response.s11),
        S11_imag=imag.(selected_readout_response.s11),
        S11_mag=abs.(selected_readout_response.s11),
    )
    CSV.write(readout_s21_raw_csv_path, readout_s21_raw_df)

    run_vector_fitting_helper(
        readout_s21_raw_csv_path,
        readout_s21_model_csv_path,
        readout_s21_resonance_csv_path,
    )

    readout_s21_model_df = CSV.read(readout_s21_model_csv_path, DataFrame)
    readout_s21_resonance_df = CSV.read(readout_s21_resonance_csv_path, DataFrame)

    candidate_csv_path = joinpath(output_dir, "readout_candidate_sweep_summary.csv")
    summary_csv_path = joinpath(output_dir, "selected_loss_decomposition_summary.csv")
    lq_sweep_csv_path = joinpath(output_dir, "selected_setup_lq_sweep_summary.csv")
    window_length_csv_path = joinpath(output_dir, "selected_coupled_window_length_sweep_summary.csv")

    CSV.write(candidate_csv_path, candidate_df)
    CSV.write(summary_csv_path, summary_df)
    CSV.write(lq_sweep_csv_path, vcat(xy_lq_sweep_df, full_lq_sweep_df; cols=:union))
    CSV.write(window_length_csv_path, window_length_df)

    readout_s21_vf_plot = build_plot(
            [
                scatter(
                    mode="markers",
                    x=readout_s21_raw_df.frequency_ghz,
                    y=readout_s21_raw_df.S21_mag,
                    name="Readout S21 raw",
                ),
                scatter(
                    mode="lines",
                    x=readout_s21_model_df.frequency_ghz,
                    y=readout_s21_model_df.S21_model_mag,
                    name="Vector fitting model",
                ),
            ],
            "Readout Line S21 With Vector Fitting",
            "Frequency (GHz)",
            "|S21|";
            legend_title="Trace",
        )

        lq_sweep_plot = build_plot(
            [
                scatter(
                    mode="lines+markers",
                    x=xy_lq_sweep_df.lq_nh,
                    y=xy_lq_sweep_df.g_resonance_s,
                    text=[@sprintf("fq = %.6f GHz", fq) for fq in xy_lq_sweep_df.fq_ghz],
                    hovertemplate="Setup: XY only<br>Lq: %{x:.3f} nH<br>Re(Ydm): %{y:.6e} S<br>%{text}<extra></extra>",
                    name="XY only",
                ),
                scatter(
                    mode="lines+markers",
                    x=full_lq_sweep_df.lq_nh,
                    y=full_lq_sweep_df.g_resonance_s,
                    text=[@sprintf("fq = %.6f GHz", fq) for fq in full_lq_sweep_df.fq_ghz],
                    hovertemplate="Setup: XY + Readout<br>Lq: %{x:.3f} nH<br>Re(Ydm): %{y:.6e} S<br>%{text}<extra></extra>",
                    name="XY + Readout",
                ),
            ],
            "Sweep Lq: Re(Ydm,in) For Two Setups",
            "Lq (nH)",
            "Re(Ydm,in) (S)";
            legend_title="Setup",
        )

        window_length_plot = build_plot(
            [
                scatter(
                    mode="lines+markers",
                    x=window_length_df.coupled_window_length_um,
                    y=window_length_df.re_y_dm_s,
                    text=[@sprintf("fq = %.6f GHz, Lq = %.3f nH", row.fq_ghz, row.lq_nh) for row in eachrow(window_length_df)],
                    hovertemplate="Setup: XY + Readout<br>Coupled window: %{x:.1f} um<br>Re(Ydm): %{y:.6e} S<br>%{text}<extra></extra>",
                    name="XY + Readout",
                ),
            ],
            "XY + Readout: Re(Ydm,in) vs Coupled Window Length",
            "Coupled Window Length (um)",
            "Re(Ydm,in) (S)";
            legend_title="Setup",
        )

    selected_yin_plot = build_plot(
            [
                scatter(
                    mode="markers+text",
                    x=[
                        xy_baseline.result.fq_ghz,
                        readout_selected.fq_ghz,
                        full_shift.fq_ghz,
                        xy_matched.result.fq_ghz,
                        target_full_shift_f_ghz,
                    ],
                    y=[
                        xy_baseline.result.G_resonance_s,
                        readout_selected.G_resonance_s,
                        full_shift.G_resonance_s,
                        xy_matched.result.G_resonance_s,
                        ideal_additive_G,
                    ],
                    text=[
                        "XY baseline",
                        "RO only",
                        "Full shift",
                        "XY matched",
                        "Ideal additive",
                    ],
                    textposition="top center",
                    marker=attr(size=12),
                    name="Re(Ydm) at extracted resonance",
                ),
            ],
            "Selected Cases: Re(Ydm,in) At Extracted Resonance",
            "Extracted Qubit Resonance Frequency (GHz)",
            "Re(Ydm,in) (S)";
            legend_title="Case",
        )

    display(readout_s21_vf_plot)
    display(lq_sweep_plot)
    display(window_length_plot)
    display(selected_yin_plot)

    if HOLD_AFTER_PLOTTING
        println()
        println("Plots are being served from a temporary local PlotlyJS server.")
        println("Press Enter to end the script after you finish viewing the plots...")
        readline()
    end

    println("Vector-fitting resonance summary:")
    for row in eachrow(readout_s21_resonance_df)
        @printf(
            "  %-18s fr = %.6f GHz | Ql = %.3f | BW = %.3f MHz\n",
            row.role,
            row.fr_ghz,
            row.Ql,
            row.bw_mhz,
        )
    end
    println()

    println("Selected-case summary:")
    @printf(
        "  selected coupled window = %.1f um | selected coupling = %s\n",
        selected_row.coupled_window_length_um,
        selected_row.coupling_label,
    )
    for row in eachrow(summary_df)
        @printf(
            "  %-26s fq = %7.4f GHz | Re(Ydm) = % .6e S | normalized = % .4f | window = %5.1f um | C_rq = (%5.2f, %5.2f) fF | %s\n",
            row.case,
            row.fq_ghz,
            row.re_y_dm_s,
            row.normalized_loss,
            row.coupled_window_length_um,
            row.c_rq1_ff,
            row.c_rq2_ff,
            row.note,
        )
    end

    println()
    println("Saved outputs:")
    println("  ", candidate_csv_path)
    println("  ", summary_csv_path)
    println("  ", lq_sweep_csv_path)
    println("  ", window_length_csv_path)
    println("  ", readout_s21_raw_csv_path)
    println("  ", readout_s21_model_csv_path)
    println("  ", readout_s21_resonance_csv_path)
end

with_terminal_logger() do
    run_loss_decomposition_study()
end
