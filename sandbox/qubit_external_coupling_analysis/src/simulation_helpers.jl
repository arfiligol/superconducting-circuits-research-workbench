function solve_linear_response(
    cfg::StudyConfig;
    sweep_start_ghz=cfg.sweep_start_ghz,
    sweep_stop_ghz=cfg.sweep_stop_ghz,
    sweep_step_ghz=cfg.sweep_step_ghz,
    returnZ=false,
    returnS=true,
)
    netlists = build_floating_qubit_environment_netlist(cfg)

    ws = 2π .* (sweep_start_ghz:sweep_step_ghz:sweep_stop_ghz) .* GHz
    wp = (2π * 8.001 * GHz,)
    sources = [(mode=(1,), port=1, current=0.0)]
    solution = hbsolve(
        ws,
        wp,
        sources,
        (1,),
        (1,),
        netlists.numeric_netlist,
        Dict{Any,Float64}();
        returnZ=returnZ,
        returnS=returnS,
        sorting=:name,
    )

    return (solution=solution, netlists=netlists)
end

function simulate_case(cfg::StudyConfig; label::AbstractString)
    response = solve_linear_response(cfg; returnZ=true)
    freqs_ghz = response.solution.linearized.w ./ (2π .* GHz)
    y_cube_raw = z_to_y_cube(response.solution)
    dm_result = differential_mode_input_admittance(y_cube_raw, cfg)
    resonance = extract_resonance_from_yin(freqs_ghz, dm_result.Yin_dm)

    return (
        label=String(label),
        config=cfg,
        freqs_ghz=freqs_ghz,
        Yin_dm=dm_result.Yin_dm,
        resonance=resonance,
        G_resonance_s=resonance.re_y,
        fq_ghz=resonance.frequency_ghz,
        crossed=resonance.crossed,
        symbolic_component_count=length(response.netlists.symbolic_netlist),
    )
end

function simulate_case_with_ceff_trace(
    cfg::StudyConfig;
    label::AbstractString,
    fit_half_window_points::Integer=4,
)
    response = solve_linear_response(cfg; returnZ=true)
    freqs_ghz = response.solution.linearized.w ./ (2π .* GHz)
    y_cube_raw = z_to_y_cube(response.solution)
    dm_loss_result = differential_mode_input_admittance(y_cube_raw, cfg; ptc_mode=:qubit_only)
    dm_ceff_result = differential_mode_input_admittance(y_cube_raw, cfg; ptc_mode=:all_ports)
    resonance = extract_resonance_from_yin(freqs_ghz, dm_loss_result.Yin_dm)
    ceff_trace = fit_effective_capacitance_trace(
        freqs_ghz,
        dm_ceff_result.Yin_dm;
        half_window_points=fit_half_window_points,
    )
    resonance_idx = argmin(abs.(freqs_ghz .- resonance.frequency_ghz))

    return (
        label=String(label),
        config=cfg,
        freqs_ghz=freqs_ghz,
        Yin_dm_loss=dm_loss_result.Yin_dm,
        Yin_dm_ceff=dm_ceff_result.Yin_dm,
        resonance=resonance,
        G_resonance_s=resonance.re_y,
        fq_ghz=resonance.frequency_ghz,
        crossed=resonance.crossed,
        ceff_trace=ceff_trace,
        ceff_fit_at_resonance_f=ceff_trace.c_eff_fit_f[resonance_idx],
        ceff_direct_at_resonance_f=ceff_trace.c_eff_direct_f[resonance_idx],
        ceff_sample_frequency_ghz=freqs_ghz[resonance_idx],
        symbolic_component_count=length(response.netlists.symbolic_netlist),
    )
end

function simulate_readout_sparameters(
    cfg::StudyConfig;
    sweep_start_ghz,
    sweep_stop_ghz,
    sweep_step_ghz,
    input_port=4,
    output_port=5,
)
    response = solve_linear_response(
        cfg;
        sweep_start_ghz=sweep_start_ghz,
        sweep_stop_ghz=sweep_stop_ghz,
        sweep_step_ghz=sweep_step_ghz,
        returnS=true,
    )
    freqs_ghz = response.solution.linearized.w ./ (2π .* GHz)
    s21 = response.solution.linearized.S(
        outputmode=(0,),
        outputport=output_port,
        inputmode=(0,),
        inputport=input_port,
        freqindex=:,
    )
    s11 = response.solution.linearized.S(
        outputmode=(0,),
        outputport=input_port,
        inputmode=(0,),
        inputport=input_port,
        freqindex=:,
    )
    return (
        freqs_ghz=freqs_ghz,
        s21=s21,
        s11=s11,
        netlists=response.netlists,
    )
end

function scan_lq_values(
    base_cfg::StudyConfig,
    lq_values_h;
    label_prefix,
    progress_label::AbstractString="",
    use_threads::Bool=false,
    max_parallel_workers::Int=Base.Threads.nthreads(),
)
    total_points = length(lq_values_h)
    rows = Vector{NamedTuple}(undef, total_points)
    completed_points = Base.Threads.Atomic{Int}(0)
    worker_count = min(max(max_parallel_workers, 1), Base.Threads.nthreads())

    function build_scan_row(lq_h)
        result = simulate_case(updated_config(base_cfg; l_q_h=lq_h); label="$(label_prefix)_$(lq_h / nH) nH")
        return (
            lq_nh=lq_h / nH,
            fq_ghz=result.crossed ? result.fq_ghz : NaN,
            g_resonance_s=result.crossed ? result.G_resonance_s : NaN,
            fallback_fq_ghz=result.fq_ghz,
            fallback_g_resonance_s=result.G_resonance_s,
            crossed=result.crossed,
        )
    end

    if use_threads && worker_count > 1 && total_points > 1
        work_channel = Channel{Tuple{Int,Float64}}(total_points)
        for (point_index, lq_h) in enumerate(lq_values_h)
            put!(work_channel, (point_index, lq_h))
        end
        close(work_channel)

        Base.Threads.foreach(work_channel; ntasks=worker_count) do (point_index, lq_h)
            rows[point_index] = build_scan_row(lq_h)
            if !isempty(progress_label)
                current = Base.Threads.atomic_add!(completed_points, 1) + 1
                print_progress_update(
                    progress_label,
                    current,
                    total_points;
                    detail=@sprintf("Lq = %.3f nH", lq_h / nH),
                )
            end
        end
    else
        for (point_index, lq_h) in enumerate(lq_values_h)
            rows[point_index] = build_scan_row(lq_h)
            if !isempty(progress_label)
                print_progress_update(
                    progress_label,
                    point_index,
                    total_points;
                    detail=@sprintf("Lq = %.3f nH", lq_h / nH),
                )
            end
        end
    end
    return DataFrame(rows)
end

function scan_lq_values_with_yin_traces(
    base_cfg::StudyConfig,
    lq_values_h;
    label_prefix,
    setup_label::AbstractString,
    progress_label::AbstractString="",
    use_threads::Bool=false,
    max_parallel_workers::Int=Base.Threads.nthreads(),
)
    total_points = length(lq_values_h)
    summary_rows = Vector{NamedTuple}(undef, total_points)
    trace_rows_by_point = Vector{Vector{NamedTuple}}(undef, total_points)
    completed_points = Base.Threads.Atomic{Int}(0)
    worker_count = min(max(max_parallel_workers, 1), Base.Threads.nthreads())

    function build_scan_result(lq_h)
        result = simulate_case(updated_config(base_cfg; l_q_h=lq_h); label="$(label_prefix)_$(lq_h / nH) nH")
        summary_row = (
            lq_nh=lq_h / nH,
            fq_ghz=result.crossed ? result.fq_ghz : NaN,
            g_resonance_s=result.crossed ? result.G_resonance_s : NaN,
            fallback_fq_ghz=result.fq_ghz,
            fallback_g_resonance_s=result.G_resonance_s,
            crossed=result.crossed,
            setup=String(setup_label),
        )
        trace_rows = [
            (
                setup=String(setup_label),
                lq_nh=lq_h / nH,
                frequency_ghz=freq_ghz,
                re_y_dm_s=real(yin_value),
                im_y_dm_s=imag(yin_value),
                crossed=result.crossed,
                extracted_fq_ghz=result.fq_ghz,
                extracted_re_y_dm_s=result.G_resonance_s,
            ) for (freq_ghz, yin_value) in zip(result.freqs_ghz, result.Yin_dm)
        ]
        return summary_row, trace_rows
    end

    if use_threads && worker_count > 1 && total_points > 1
        work_channel = Channel{Tuple{Int,Float64}}(total_points)
        for (point_index, lq_h) in enumerate(lq_values_h)
            put!(work_channel, (point_index, lq_h))
        end
        close(work_channel)

        Base.Threads.foreach(work_channel; ntasks=worker_count) do (point_index, lq_h)
            summary_row, trace_rows = build_scan_result(lq_h)
            summary_rows[point_index] = summary_row
            trace_rows_by_point[point_index] = trace_rows
            if !isempty(progress_label)
                current = Base.Threads.atomic_add!(completed_points, 1) + 1
                print_progress_update(
                    progress_label,
                    current,
                    total_points;
                    detail=@sprintf("Lq = %.3f nH", lq_h / nH),
                )
            end
        end
    else
        for (point_index, lq_h) in enumerate(lq_values_h)
            summary_row, trace_rows = build_scan_result(lq_h)
            summary_rows[point_index] = summary_row
            trace_rows_by_point[point_index] = trace_rows
            if !isempty(progress_label)
                print_progress_update(
                    progress_label,
                    point_index,
                    total_points;
                    detail=@sprintf("Lq = %.3f nH", lq_h / nH),
                )
            end
        end
    end

    return (
        summary_df=DataFrame(summary_rows),
        trace_df=DataFrame(vcat(trace_rows_by_point...)),
    )
end

function select_nearest_frequency(df::DataFrame, target_f_ghz)
    crossed_df = df[df.crossed .== true, :]
    crossed_df = crossed_df[.!isnan.(crossed_df.fq_ghz), :]
    if nrow(crossed_df) > 0
        return crossed_df[argmin(abs.(crossed_df.fq_ghz .- target_f_ghz)), :]
    end
    error("No Im(Ydm)=0 crossing found inside the requested sweep window.")
end

function make_case_summary_row(result; normalized_loss=nothing, note="", window_label="", coupling_label="")
    return (
        case=result.label,
        lq_nh=result.config.l_q_h / nH,
        c_xy1_ff=result.config.c_xy1_f / fF,
        c_xy2_ff=result.config.c_xy2_f / fF,
        c_rq1_ff=result.config.c_rq1_f / fF,
        c_rq2_ff=result.config.c_rq2_f / fF,
        coupled_window_length_um=result.config.coupled_window_length_m / um,
        qwr_length_um=result.config.qwr_length_m / um,
        pf_length_um=result.config.purcell_filter_length_m / um,
        window_label=String(window_label),
        coupling_label=String(coupling_label),
        fq_ghz=result.fq_ghz,
        re_y_dm_s=result.G_resonance_s,
        normalized_loss=isnothing(normalized_loss) ? NaN : normalized_loss,
        crossed=result.crossed,
        note=String(note),
    )
end
