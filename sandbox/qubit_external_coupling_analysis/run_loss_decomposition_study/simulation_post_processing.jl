function build_fine_lq_values(center_lq_h, half_window_h, step_h)
    step_h > 0 || error("matched_lq_fine_step_h must be positive.")
    half_window_h > 0 || error("matched_lq_fine_half_window_h must be positive.")

    lower_h = max(step_h, center_lq_h - half_window_h)
    upper_h = max(lower_h, center_lq_h + half_window_h)
    values_h = collect(lower_h:step_h:upper_h)

    if isempty(values_h)
        values_h = [lower_h, upper_h]
    else
        if values_h[1] > lower_h + (step_h * 1e-9)
            pushfirst!(values_h, lower_h)
        end
        if values_h[end] < upper_h - (step_h * 1e-9)
            push!(values_h, upper_h)
        end
    end

    return unique(sort(values_h))
end

function simulate_best_near_target(
    base_cfg::StudyConfig,
    target_f_ghz;
    lq_values_h,
    label_prefix,
    progress_label::AbstractString="",
    use_threads::Bool=false,
    max_parallel_workers::Int=Base.Threads.nthreads(),
)
    sweep_df = scan_lq_values(
        base_cfg,
        lq_values_h;
        label_prefix=label_prefix,
        progress_label=progress_label,
        use_threads=use_threads,
        max_parallel_workers=max_parallel_workers,
    )
    best_row = select_nearest_frequency(sweep_df, target_f_ghz)
    result = simulate_case(updated_config(base_cfg; l_q_h=best_row.lq_nh * nH); label=label_prefix)
    return (result=result, sweep_df=sweep_df, best_row=best_row)
end

function simulate_best_near_target_refined(
    base_cfg::StudyConfig,
    target_f_ghz;
    coarse_lq_values_h,
    fine_half_window_h,
    fine_step_h,
    label_prefix,
    coarse_progress_label::AbstractString="",
    fine_progress_label::AbstractString="",
    use_threads::Bool=false,
    max_parallel_workers::Int=Base.Threads.nthreads(),
)
    coarse = simulate_best_near_target(
        base_cfg,
        target_f_ghz;
        lq_values_h=coarse_lq_values_h,
        label_prefix="$(label_prefix)_coarse",
        progress_label=coarse_progress_label,
        use_threads=use_threads,
        max_parallel_workers=max_parallel_workers,
    )

    fine_lq_values_h = build_fine_lq_values(
        coarse.best_row.lq_nh * nH,
        fine_half_window_h,
        fine_step_h,
    )

    fine = simulate_best_near_target(
        base_cfg,
        target_f_ghz;
        lq_values_h=fine_lq_values_h,
        label_prefix="$(label_prefix)_fine",
        progress_label=fine_progress_label,
        use_threads=use_threads,
        max_parallel_workers=max_parallel_workers,
    )

    result = simulate_case(
        updated_config(base_cfg; l_q_h=fine.best_row.lq_nh * nH);
        label=label_prefix,
    )

    return (
        result=result,
        coarse_sweep_df=coarse.sweep_df,
        fine_sweep_df=fine.sweep_df,
        coarse_best_row=coarse.best_row,
        best_row=fine.best_row,
    )
end

function choose_best_candidate(df::DataFrame, inputs)
    score_ratio = abs.(df.readout_to_xy_ratio .- inputs.readout_ratio_comparison_target)
    score_strength = -df.readout_only_re_y_s
    ranking_df = copy(df)
    ranking_df[!, :score_ratio] = score_ratio
    ranking_df[!, :score_strength] = score_strength
    sort!(ranking_df, [:score_ratio, :score_strength])
    return ranking_df[1, :]
end

function candidate_progress_detail(row)
    return @sprintf(
        "CW=%.0fum | rq=%.1f/%.1ffF",
        row.coupled_window_length_um,
        row.c_rq1_ff,
        row.c_rq2_ff,
    )
end

function build_study_output_paths()
    study_name = basename(@__DIR__)
    study_output_root = normpath(joinpath(@__DIR__, "..", "outputs", study_name))
    raw_dir = joinpath(study_output_root, "raw")
    figures_dir = joinpath(study_output_root, "figures")
    return (
        study_name=study_name,
        study_output_root=study_output_root,
        raw_dir=raw_dir,
        figures_dir=figures_dir,
        candidate_csv_path=joinpath(raw_dir, "readout_candidate_sweep_summary.csv"),
        candidate_partial_csv_path=joinpath(raw_dir, "readout_candidate_sweep_summary.partial.csv"),
        summary_csv_path=joinpath(raw_dir, "selected_loss_decomposition_summary.csv"),
        lq_sweep_csv_path=joinpath(raw_dir, "selected_setup_lq_sweep_summary.csv"),
        lq_ydm_trace_csv_path=joinpath(raw_dir, "selected_setup_lq_yin_traces.csv"),
        window_length_csv_path=joinpath(raw_dir, "selected_coupled_window_length_sweep_summary.csv"),
        ro_window_length_csv_path=joinpath(raw_dir, "selected_ro_only_coupled_window_length_sweep_summary.csv"),
        window_length_ydm_trace_csv_path=joinpath(raw_dir, "selected_coupled_window_length_yin_traces.csv"),
        selected_case_ceff_trace_csv_path=joinpath(raw_dir, "selected_case_ceff_frequency_traces.csv"),
        readout_s21_raw_csv_path=joinpath(raw_dir, "selected_readout_s21_raw.csv"),
        readout_s21_model_csv_path=joinpath(raw_dir, "selected_readout_s21_vf_model.csv"),
        readout_s21_resonance_csv_path=joinpath(raw_dir, "selected_readout_s21_vf_resonances.csv"),
    )
end

function build_case_ceff_trace_rows(case_result)
    return [
        (
            case=case_result.label,
            g_ptc_mode="qubit_only",
            ceff_ptc_mode="all_ports",
            frequency_ghz=freq_ghz,
            omega_rad_per_s=case_result.ceff_trace.omega_rad_per_s[idx],
            re_y_dm_s=real(yin_loss_value),
            im_y_dm_s=imag(yin_loss_value),
            re_y_dm_ceff_s=real(yin_ceff_value),
            im_y_dm_ceff_s=imag(yin_ceff_value),
            c_eff_fit_f=case_result.ceff_trace.c_eff_fit_f[idx],
            c_eff_fit_ff=case_result.ceff_trace.c_eff_fit_f[idx] / fF,
            c_eff_direct_f=case_result.ceff_trace.c_eff_direct_f[idx],
            c_eff_direct_ff=case_result.ceff_trace.c_eff_direct_f[idx] / fF,
            t1_fit_s=(real(yin_loss_value) > 0 && case_result.ceff_trace.c_eff_fit_f[idx] > 0) ? case_result.ceff_trace.c_eff_fit_f[idx] / real(yin_loss_value) : NaN,
            t1_fit_us=(real(yin_loss_value) > 0 && case_result.ceff_trace.c_eff_fit_f[idx] > 0) ? (case_result.ceff_trace.c_eff_fit_f[idx] / real(yin_loss_value)) * 1e6 : NaN,
            t1_direct_s=(real(yin_loss_value) > 0 && case_result.ceff_trace.c_eff_direct_f[idx] > 0) ? case_result.ceff_trace.c_eff_direct_f[idx] / real(yin_loss_value) : NaN,
            t1_direct_us=(real(yin_loss_value) > 0 && case_result.ceff_trace.c_eff_direct_f[idx] > 0) ? (case_result.ceff_trace.c_eff_direct_f[idx] / real(yin_loss_value)) * 1e6 : NaN,
            fit_rmse_s=case_result.ceff_trace.fit_rmse_s[idx],
            fit_point_count=case_result.ceff_trace.fit_point_count[idx],
            fit_window_start_idx=case_result.ceff_trace.fit_window_start_idx[idx],
            fit_window_stop_idx=case_result.ceff_trace.fit_window_stop_idx[idx],
            fit_half_window_points=case_result.ceff_trace.fit_half_window_points,
            crossed=case_result.crossed,
            extracted_fq_ghz=case_result.fq_ghz,
            extracted_re_y_dm_s=case_result.G_resonance_s,
            ceff_sample_frequency_ghz=case_result.ceff_sample_frequency_ghz,
            c_eff_fit_at_extracted_f_f=case_result.ceff_fit_at_resonance_f,
            c_eff_fit_at_extracted_f_ff=case_result.ceff_fit_at_resonance_f / fF,
            c_eff_direct_at_extracted_f_f=case_result.ceff_direct_at_resonance_f,
            c_eff_direct_at_extracted_f_ff=case_result.ceff_direct_at_resonance_f / fF,
            t1_fit_at_extracted_f_s=(case_result.G_resonance_s > 0 && case_result.ceff_fit_at_resonance_f > 0) ? case_result.ceff_fit_at_resonance_f / case_result.G_resonance_s : NaN,
            t1_fit_at_extracted_f_us=(case_result.G_resonance_s > 0 && case_result.ceff_fit_at_resonance_f > 0) ? (case_result.ceff_fit_at_resonance_f / case_result.G_resonance_s) * 1e6 : NaN,
            t1_direct_at_extracted_f_s=(case_result.G_resonance_s > 0 && case_result.ceff_direct_at_resonance_f > 0) ? case_result.ceff_direct_at_resonance_f / case_result.G_resonance_s : NaN,
            t1_direct_at_extracted_f_us=(case_result.G_resonance_s > 0 && case_result.ceff_direct_at_resonance_f > 0) ? (case_result.ceff_direct_at_resonance_f / case_result.G_resonance_s) * 1e6 : NaN,
        ) for (idx, (freq_ghz, yin_loss_value, yin_ceff_value)) in enumerate(
            zip(case_result.freqs_ghz, case_result.Yin_dm_loss, case_result.Yin_dm_ceff),
        )
    ]
end

function run_loss_decomposition_simulation(inputs, circuit_context)
    output_paths = build_study_output_paths()
    mkpath(output_paths.raw_dir)
    sim_cfg = inputs.simulation_config

    println("============================================================")
    println("Floating-Qubit Loss Decomposition Study")
    println("============================================================")
    println("Loss metrics use qubit-port-only PTC before CT -> Kron reduction.")
    println("Ceff diagnostics use all-port PTC before the same CT -> Kron reduction.")
    println("PF and QWR resonant lengths are fixed; only coupled-window length and C_rq1/C_rq2 are swept on the readout side.")
    @printf(
        "Execution config: workers = %d (available Julia threads = %d), candidate batch save = %d points\n",
        min(sim_cfg.max_parallel_workers, Base.Threads.nthreads()),
        Base.Threads.nthreads(),
        sim_cfg.parameter_sweep_batch_size,
    )
    println()

    println("Stage 1/6: XY-only baseline Lq sweep (coarse -> fine)")
    xy_baseline = simulate_best_near_target_refined(
        circuit_context.xy_only_cfg,
        inputs.baseline_target_f_ghz;
        coarse_lq_values_h=inputs.lq_sweep_values_h,
        fine_half_window_h=inputs.matched_lq_fine_half_window_h,
        fine_step_h=inputs.matched_lq_fine_step_h,
        label_prefix="xy_only_baseline",
        coarse_progress_label="XY baseline coarse sweep  ",
        fine_progress_label="XY baseline fine sweep    ",
        use_threads=sim_cfg.use_threaded_standalone_lq_sweeps,
        max_parallel_workers=sim_cfg.max_parallel_workers,
    )

    g_xy_baseline = xy_baseline.result.G_resonance_s
    lq_baseline_h = xy_baseline.result.config.l_q_h

    @printf(
        "XY-only baseline  : Lq = %.3f nH, fq = %.6f GHz, Re(Ydm) = %.6e S\n",
        lq_baseline_h / nH,
        xy_baseline.result.fq_ghz,
        g_xy_baseline,
    )
    println()

    println("Stage 2/6: Readout-candidate sweep at the XY-only baseline bare Lq")
    candidate_df = run_parameter_sweep(
        circuit_context.base_cfg,
        inputs.readout_candidate_sweep_axes,
        progress_label="Readout candidate sweep    ",
        progress_detail_builder=(row, axes, sweep_index, coordinates) -> candidate_progress_detail(row),
        batch_size=sim_cfg.parameter_sweep_batch_size,
        persisted_csv_path=output_paths.candidate_partial_csv_path,
        use_threads=sim_cfg.use_threaded_candidate_sweep,
        max_parallel_workers=sim_cfg.max_parallel_workers,
        return_dataframe=true,
    ) do readout_cfg, sweep_index, coordinates
        ro_case = simulate_case(
            updated_config(config_without_xy(readout_cfg); l_q_h=lq_baseline_h);
            label="readout_only_candidate_$(sweep_index)",
        )
        full_case = simulate_case(
            updated_config(readout_cfg; l_q_h=lq_baseline_h);
            label="full_coupled_candidate_$(sweep_index)",
        )

        return (
            window_label=@sprintf("window_%.0f_um", readout_cfg.coupled_window_length_m / um),
            coupling_label=@sprintf("rq_(%.3f,%.3f)_fF", readout_cfg.c_rq1_f / fF, readout_cfg.c_rq2_f / fF),
            coupled_window_length_um=readout_cfg.coupled_window_length_m / um,
            c_rq1_ff=readout_cfg.c_rq1_f / fF,
            c_rq2_ff=readout_cfg.c_rq2_f / fF,
            baseline_lq_nh=lq_baseline_h / nH,
            readout_only_fq_ghz=ro_case.fq_ghz,
            readout_only_re_y_s=ro_case.G_resonance_s,
            readout_only_crossed=ro_case.crossed,
            readout_to_xy_ratio=ro_case.G_resonance_s / g_xy_baseline,
            full_shift_fq_ghz=full_case.fq_ghz,
            full_shift_re_y_s=full_case.G_resonance_s,
            full_shift_crossed=full_case.crossed,
            full_shift_normalized=full_case.G_resonance_s / g_xy_baseline,
        )
    end
    mv(output_paths.candidate_partial_csv_path, output_paths.candidate_csv_path; force=true)

    valid_mask = candidate_df.readout_only_crossed .& candidate_df.full_shift_crossed
    ratio_mask = valid_mask .&
                 (inputs.readout_ratio_acceptable_min .<= candidate_df.readout_to_xy_ratio) .&
                 (candidate_df.readout_to_xy_ratio .<= inputs.readout_ratio_acceptable_max)

    if any(ratio_mask)
        selected_row = choose_best_candidate(candidate_df[ratio_mask, :], inputs)
        selection_note = "candidate inside readout-to-XY ratio window"
    elseif any(valid_mask)
        selected_row = choose_best_candidate(candidate_df[valid_mask, :], inputs)
        selection_note = "closest overall candidate with physical crossings"
    else
        error("No readout candidate produced a physical Im(Ydm)=0 crossing for both RO-only and XY+RO cases.")
    end

    selected_base_cfg = updated_config(
        circuit_context.base_cfg;
        coupled_window_length_m=selected_row.coupled_window_length_um * um,
        c_rq1_f=selected_row.c_rq1_ff * fF,
        c_rq2_f=selected_row.c_rq2_ff * fF,
    )

    println("Readout-candidate sweep summary:")
    @printf("  selected coupled-window     = %.1f um\n", selected_row.coupled_window_length_um)
    @printf("  selected coupling candidate = %s\n", selected_row.coupling_label)
    @printf("  selection rule              = %s\n", selection_note)
    @printf("  readout-only / xy-only      = %.4f\n", selected_row.readout_to_xy_ratio)
    @printf("  selected C_rq1, C_rq2       = %.3f fF, %.3f fF\n", selected_row.c_rq1_ff, selected_row.c_rq2_ff)
    println()

    println("Stage 3/6: Selected RO-only and XY+Readout at the same bare baseline Lq")
    readout_selected = simulate_case(
        updated_config(config_without_xy(selected_base_cfg); l_q_h=lq_baseline_h);
        label="readout_only_selected",
    )
    full_shift = simulate_case(
        updated_config(selected_base_cfg; l_q_h=lq_baseline_h);
        label="xy_plus_readout_shifted",
    )
    full_shift.crossed || error("Selected XY+Readout case has no physical Im(Ydm)=0 crossing inside the sweep window.")
    matched_target_f_ghz = full_shift.fq_ghz

    @printf(
        "RO-only selected  : Lq = %.3f nH, fq = %.6f GHz, Re(Ydm) = %.6e S\n",
        lq_baseline_h / nH,
        readout_selected.fq_ghz,
        readout_selected.G_resonance_s,
    )
    @printf(
        "XY + Readout      : Lq = %.3f nH, fq = %.6f GHz, Re(Ydm) = %.6e S\n",
        lq_baseline_h / nH,
        full_shift.fq_ghz,
        full_shift.G_resonance_s,
    )
    println()

    println("Stage 4/6: XY-only matched to the selected XY+Readout frequency (coarse -> fine)")
    xy_matched = simulate_best_near_target_refined(
        circuit_context.xy_only_cfg,
        matched_target_f_ghz;
        coarse_lq_values_h=inputs.lq_sweep_values_h,
        fine_half_window_h=inputs.matched_lq_fine_half_window_h,
        fine_step_h=inputs.matched_lq_fine_step_h,
        label_prefix="xy_only_matched",
        coarse_progress_label="XY matched coarse sweep   ",
        fine_progress_label="XY matched fine sweep     ",
        use_threads=sim_cfg.use_threaded_standalone_lq_sweeps,
        max_parallel_workers=sim_cfg.max_parallel_workers,
    )

    g_readout = readout_selected.G_resonance_s
    g_xy_matched = xy_matched.result.G_resonance_s
    g_full_shift = full_shift.G_resonance_s
    ideal_additive_g = g_xy_matched + g_readout
    cross_shift_g = g_full_shift - ideal_additive_g

    @printf(
        "XY-only matched   : Lq = %.3f nH, fq = %.6f GHz, Re(Ydm) = %.6e S\n",
        xy_matched.result.config.l_q_h / nH,
        xy_matched.result.fq_ghz,
        g_xy_matched,
    )
    println()

    selected_case_ceff_results = [
        simulate_case_with_ceff_trace(
            xy_baseline.result.config;
            label="xy_only_baseline",
            fit_half_window_points=inputs.ceff_fit_config.half_window_points,
        ),
        simulate_case_with_ceff_trace(
            readout_selected.config;
            label="readout_only_selected",
            fit_half_window_points=inputs.ceff_fit_config.half_window_points,
        ),
        simulate_case_with_ceff_trace(
            full_shift.config;
            label="xy_plus_readout_shifted",
            fit_half_window_points=inputs.ceff_fit_config.half_window_points,
        ),
        simulate_case_with_ceff_trace(
            xy_matched.result.config;
            label="xy_only_matched",
            fit_half_window_points=inputs.ceff_fit_config.half_window_points,
        ),
    ]
    selected_case_ceff_trace_df = DataFrame(vcat(build_case_ceff_trace_rows.(selected_case_ceff_results)...))

    summary_df = DataFrame([
        make_case_summary_row(
            xy_baseline.result;
            normalized_loss=1.0,
            note="reference XY-only baseline",
            window_label="xy_only",
            coupling_label="xy_only",
        ),
        make_case_summary_row(
            readout_selected;
            normalized_loss=g_readout / g_xy_baseline,
            note="RO-only at the same bare baseline Lq",
            window_label=selected_row.window_label,
            coupling_label=selected_row.coupling_label,
        ),
        make_case_summary_row(
            full_shift;
            normalized_loss=g_full_shift / g_xy_baseline,
            note="XY + Readout at the same bare baseline Lq",
            window_label=selected_row.window_label,
            coupling_label=selected_row.coupling_label,
        ),
        make_case_summary_row(
            xy_matched.result;
            normalized_loss=g_xy_matched / g_xy_baseline,
            note="XY-only retuned to the XY + Readout resonance",
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
            qwr_length_um=inputs.qwr_length_m / um,
            pf_length_um=inputs.purcell_filter_length_m / um,
            window_label=selected_row.window_label,
            coupling_label=selected_row.coupling_label,
            fq_ghz=matched_target_f_ghz,
            re_y_dm_s=ideal_additive_g,
            normalized_loss=ideal_additive_g / g_xy_baseline,
            crossed=true,
            note="Re(Ydm)_XY matched + Re(Ydm)_RO only",
        ),
        (
            case="cross_term_shifted",
            lq_nh=lq_baseline_h / nH,
            c_xy1_ff=xy_baseline.result.config.c_xy1_f / fF,
            c_xy2_ff=xy_baseline.result.config.c_xy2_f / fF,
            c_rq1_ff=selected_row.c_rq1_ff,
            c_rq2_ff=selected_row.c_rq2_ff,
            coupled_window_length_um=selected_row.coupled_window_length_um,
            qwr_length_um=inputs.qwr_length_m / um,
            pf_length_um=inputs.purcell_filter_length_m / um,
            window_label=selected_row.window_label,
            coupling_label=selected_row.coupling_label,
            fq_ghz=matched_target_f_ghz,
            re_y_dm_s=cross_shift_g,
            normalized_loss=cross_shift_g / g_xy_baseline,
            crossed=true,
            note="XY + Readout - (XY matched + RO only)",
        ),
    ])

    println("Stage 5/6: Diagnostic Lq sweeps")
    xy_diagnostic = scan_lq_values_with_yin_traces(
        circuit_context.xy_only_cfg,
        inputs.lq_sweep_values_h;
        label_prefix="xy_only_curve",
        setup_label="XY only",
        progress_label="Diagnostic XY-only Lq     ",
        use_threads=sim_cfg.use_threaded_standalone_lq_sweeps,
        max_parallel_workers=sim_cfg.max_parallel_workers,
    )

    full_diagnostic = scan_lq_values_with_yin_traces(
        selected_base_cfg,
        inputs.lq_sweep_values_h;
        label_prefix="full_selected_curve",
        setup_label="XY + Readout",
        progress_label="Diagnostic full Lq        ",
        use_threads=sim_cfg.use_threaded_standalone_lq_sweeps,
        max_parallel_workers=sim_cfg.max_parallel_workers,
    )
    xy_lq_sweep_df = xy_diagnostic.summary_df
    full_lq_sweep_df = full_diagnostic.summary_df
    lq_ydm_trace_df = vcat(xy_diagnostic.trace_df, full_diagnostic.trace_df; cols=:union)

    coupled_window_axis = only(filter(axis -> axis isa ScalarParameterSweepAxis && axis.parameter == :coupled_window_length_m, inputs.readout_candidate_sweep_axes))
    window_length_rows = NamedTuple[]
    ro_window_length_rows = NamedTuple[]
    window_length_trace_rows = NamedTuple[]
    window_length_total_points = length(coupled_window_axis.values)
    println("Stage 6/6: Coupled-window-length diagnostic sweep and readout S21 fitting")
    for (point_index, coupled_window_length_m) in enumerate(coupled_window_axis.values)
        cfg = updated_config(
            circuit_context.base_cfg;
            coupled_window_length_m=coupled_window_length_m,
            c_rq1_f=selected_row.c_rq1_ff * fF,
            c_rq2_f=selected_row.c_rq2_ff * fF,
        )

        try
            ro_matched_case = simulate_best_near_target_refined(
                config_without_xy(cfg),
                matched_target_f_ghz;
                coarse_lq_values_h=inputs.lq_sweep_values_h,
                fine_half_window_h=inputs.matched_lq_fine_half_window_h,
                fine_step_h=inputs.matched_lq_fine_step_h,
                label_prefix="ro_window_length_curve_$(coupled_window_length_m / um)",
                coarse_progress_label="",
                fine_progress_label="",
                use_threads=sim_cfg.use_threaded_standalone_lq_sweeps,
                max_parallel_workers=sim_cfg.max_parallel_workers,
            )

            matched_case = simulate_best_near_target_refined(
                cfg,
                matched_target_f_ghz;
                coarse_lq_values_h=inputs.lq_sweep_values_h,
                fine_half_window_h=inputs.matched_lq_fine_half_window_h,
                fine_step_h=inputs.matched_lq_fine_step_h,
                label_prefix="window_length_curve_$(coupled_window_length_m / um)",
                coarse_progress_label="",
                fine_progress_label="",
                use_threads=sim_cfg.use_threaded_standalone_lq_sweeps,
                max_parallel_workers=sim_cfg.max_parallel_workers,
            )

            push!(
                ro_window_length_rows,
                (
                    coupled_window_length_um=coupled_window_length_m / um,
                    lq_nh=ro_matched_case.result.config.l_q_h / nH,
                    fq_ghz=ro_matched_case.result.fq_ghz,
                    re_y_dm_s=ro_matched_case.result.G_resonance_s,
                    crossed=ro_matched_case.result.crossed,
                    fallback_fq_ghz=ro_matched_case.result.fq_ghz,
                    fallback_g_resonance_s=ro_matched_case.result.G_resonance_s,
                ),
            )
            push!(
                window_length_rows,
                (
                    coupled_window_length_um=coupled_window_length_m / um,
                    lq_nh=matched_case.result.config.l_q_h / nH,
                    fq_ghz=matched_case.result.fq_ghz,
                    re_y_dm_s=matched_case.result.G_resonance_s,
                    crossed=matched_case.result.crossed,
                    fallback_fq_ghz=matched_case.result.fq_ghz,
                    fallback_g_resonance_s=matched_case.result.G_resonance_s,
                ),
            )
            append!(
                window_length_trace_rows,
                [
                    (
                        coupled_window_length_um=coupled_window_length_m / um,
                        lq_nh=matched_case.result.config.l_q_h / nH,
                        frequency_ghz=freq_ghz,
                        re_y_dm_s=real(yin_value),
                        im_y_dm_s=imag(yin_value),
                        crossed=matched_case.result.crossed,
                        extracted_fq_ghz=matched_case.result.fq_ghz,
                        extracted_re_y_dm_s=matched_case.result.G_resonance_s,
                    ) for (freq_ghz, yin_value) in zip(matched_case.result.freqs_ghz, matched_case.result.Yin_dm)
                ],
            )
        catch err
            if !(err isa ErrorException)
                rethrow()
            end
            push!(
                ro_window_length_rows,
                (
                    coupled_window_length_um=coupled_window_length_m / um,
                    lq_nh=NaN,
                    fq_ghz=NaN,
                    re_y_dm_s=NaN,
                    crossed=false,
                    fallback_fq_ghz=NaN,
                    fallback_g_resonance_s=NaN,
                ),
            )
            push!(
                window_length_rows,
                (
                    coupled_window_length_um=coupled_window_length_m / um,
                    lq_nh=NaN,
                    fq_ghz=NaN,
                    re_y_dm_s=NaN,
                    crossed=false,
                    fallback_fq_ghz=NaN,
                    fallback_g_resonance_s=NaN,
                ),
            )
        end

        print_progress_update(
            "Window-length sweep        ",
            point_index,
            window_length_total_points;
            detail=@sprintf("CW=%.0fum", coupled_window_length_m / um),
        )
    end
    window_length_df = DataFrame(window_length_rows)
    ro_window_length_df = DataFrame(ro_window_length_rows)

    readout_characterization_cfg = config_without_xy(updated_config(selected_base_cfg; c_rq1_f=0.0, c_rq2_f=0.0))
    selected_readout_response = simulate_readout_sparameters(
        readout_characterization_cfg;
        sweep_start_ghz=inputs.readout_s21_sweep_start_ghz,
        sweep_stop_ghz=inputs.readout_s21_sweep_stop_ghz,
        sweep_step_ghz=inputs.readout_s21_sweep_step_ghz,
    )

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
    CSV.write(output_paths.readout_s21_raw_csv_path, readout_s21_raw_df)

    run_vector_fitting_helper(
        output_paths.readout_s21_raw_csv_path,
        output_paths.readout_s21_model_csv_path,
        output_paths.readout_s21_resonance_csv_path,
        inputs,
    )

    CSV.write(output_paths.candidate_csv_path, candidate_df)
    CSV.write(output_paths.summary_csv_path, summary_df)
    CSV.write(output_paths.lq_sweep_csv_path, vcat(xy_lq_sweep_df, full_lq_sweep_df; cols=:union))
    CSV.write(output_paths.lq_ydm_trace_csv_path, lq_ydm_trace_df)
    CSV.write(output_paths.window_length_csv_path, window_length_df)
    CSV.write(output_paths.ro_window_length_csv_path, ro_window_length_df)
    CSV.write(output_paths.window_length_ydm_trace_csv_path, DataFrame(window_length_trace_rows))
    CSV.write(output_paths.selected_case_ceff_trace_csv_path, selected_case_ceff_trace_df)

    return (
        xy_baseline=xy_baseline,
        readout_selected=readout_selected,
        full_shift=full_shift,
        xy_matched=xy_matched,
        g_xy_baseline=g_xy_baseline,
        g_xy_matched=g_xy_matched,
        g_readout=g_readout,
        lq_baseline_h=lq_baseline_h,
        matched_target_f_ghz=matched_target_f_ghz,
        candidate_df=candidate_df,
        selected_row=selected_row,
        selection_note=selection_note,
        selected_base_cfg=selected_base_cfg,
        summary_df=summary_df,
        xy_lq_sweep_df=xy_lq_sweep_df,
        full_lq_sweep_df=full_lq_sweep_df,
        lq_ydm_trace_df=lq_ydm_trace_df,
        window_length_df=window_length_df,
        window_length_ydm_trace_df=DataFrame(window_length_trace_rows),
        selected_case_ceff_trace_df=selected_case_ceff_trace_df,
        selected_readout_response=selected_readout_response,
        output_paths=output_paths,
    )
end
