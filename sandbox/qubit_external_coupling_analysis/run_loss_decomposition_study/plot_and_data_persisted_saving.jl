function run_vector_fitting_helper(raw_csv_path, model_csv_path, resonance_csv_path, inputs)
    helper_path = normpath(joinpath(@__DIR__, "..", "tools", "fit_readout_s21_vector_fitting.py"))
    cmd = `uv run python $helper_path --input-csv $raw_csv_path --model-csv $model_csv_path --resonance-csv $resonance_csv_path --resonators $(inputs.vf_expected_resonators) --bg-poles $(inputs.vf_background_poles)`
    run(cmd)
end

function load_persisted_outputs()
    paths = build_study_output_paths()
    required_paths = [
        paths.candidate_csv_path,
        paths.summary_csv_path,
        paths.lq_sweep_csv_path,
        paths.lq_ydm_trace_csv_path,
        paths.window_length_csv_path,
        paths.ro_window_length_csv_path,
        paths.window_length_ydm_trace_csv_path,
        paths.selected_case_ceff_trace_csv_path,
        paths.readout_s21_raw_csv_path,
        paths.readout_s21_model_csv_path,
        paths.readout_s21_resonance_csv_path,
    ]
    missing_paths = filter(path -> !isfile(path), required_paths)
    isempty(missing_paths) || error(
        "Missing persisted raw data files. Re-run run_simulation.jl first.\n" *
        join(missing_paths, "\n"),
    )
    return (
        paths=paths,
        candidate_df=CSV.read(paths.candidate_csv_path, DataFrame),
        summary_df=CSV.read(paths.summary_csv_path, DataFrame),
        lq_sweep_df=CSV.read(paths.lq_sweep_csv_path, DataFrame),
        lq_ydm_trace_df=CSV.read(paths.lq_ydm_trace_csv_path, DataFrame),
        window_length_df=CSV.read(paths.window_length_csv_path, DataFrame),
        ro_window_length_df=CSV.read(paths.ro_window_length_csv_path, DataFrame),
        window_length_ydm_trace_df=CSV.read(paths.window_length_ydm_trace_csv_path, DataFrame),
        selected_case_ceff_trace_df=CSV.read(paths.selected_case_ceff_trace_csv_path, DataFrame),
        readout_s21_raw_df=CSV.read(paths.readout_s21_raw_csv_path, DataFrame),
        readout_s21_model_df=CSV.read(paths.readout_s21_model_csv_path, DataFrame),
        readout_s21_resonance_df=CSV.read(paths.readout_s21_resonance_csv_path, DataFrame),
    )
end

function build_figure_paths(output_paths)
    mkpath(output_paths.figures_dir)
    return (
        readout_s21_png_path=joinpath(output_paths.figures_dir, "readout_s21_vector_fit.png"),
        candidate_compare_png_path=joinpath(output_paths.figures_dir, "candidate_compare.png"),
        lq_sweep_png_path=joinpath(output_paths.figures_dir, "selected_setup_lq_sweep.png"),
        xy_only_yin_heatmap_png_path=joinpath(output_paths.figures_dir, "xy_only_yin_lq_heatmap.png"),
        full_yin_heatmap_png_path=joinpath(output_paths.figures_dir, "xy_plus_readout_yin_lq_heatmap.png"),
        ro_window_length_png_path=joinpath(output_paths.figures_dir, "ro_only_coupled_window_length_sweep.png"),
        window_length_png_path=joinpath(output_paths.figures_dir, "selected_coupled_window_length_sweep.png"),
        window_length_yin_heatmap_png_path=joinpath(output_paths.figures_dir, "xy_plus_readout_yin_window_heatmap.png"),
        selected_case_ceff_png_path=joinpath(output_paths.figures_dir, "selected_case_ceff_vs_frequency.png"),
        selected_case_t1_png_path=joinpath(output_paths.figures_dir, "selected_case_t1_vs_frequency.png"),
        selected_case_png_path=joinpath(output_paths.figures_dir, "selected_case_scatter.png"),
    )
end

function try_save_png(plot_obj, path, inputs)
    if !inputs.plot_controls.save_png_figures
        return
    end
    try
        savefig(
            plot_obj,
            path;
            width=inputs.plot_controls.figure_width_px,
            height=inputs.plot_controls.figure_height_px,
        )
        println("Saved figure PNG: ", path)
    catch err
        println("Could not save figure PNG to $(path)")
        println("  Reason: $(sprint(showerror, err))")
    end
end

function build_candidate_compare_plot(inputs, persisted_outputs)
    candidate_df = persisted_outputs.candidate_df
    compare_axis_index = inputs.plot_controls.candidate_compare_axis_index
    sweep_index = inputs.plot_controls.candidate_sweep_index
    metric = String(inputs.plot_controls.candidate_metric)
    metric_column = Symbol(metric)
    axes = inputs.readout_candidate_sweep_axes
    fixed_coordinates = decode_sweep_index(axes, sweep_index)

    mask = trues(nrow(candidate_df))
    for axis_index in 1:length(axes)
        if axis_index == compare_axis_index
            continue
        end
        axis_column = Symbol("axis_$(axis_index)_coordinate")
        mask .&= candidate_df[!, axis_column] .== fixed_coordinates[axis_index]
    end

    filtered = candidate_df[mask, :]
    sort!(filtered, Symbol("axis_$(compare_axis_index)_coordinate"))

    return build_plot(
        [
            scatter(
                mode="lines+markers",
                x=filtered[!, Symbol("axis_$(compare_axis_index)_value_label")],
                y=filtered[!, metric_column],
                text=[
                    @sprintf(
                        "window = %.1f um<br>C_rq = (%.3f, %.3f) fF<br>fq = %.6f GHz",
                        row.coupled_window_length_um,
                        row.c_rq1_ff,
                        row.c_rq2_ff,
                        row.readout_only_fq_ghz,
                    ) for row in eachrow(filtered)
                ],
                hovertemplate="%{x}<br>%{text}<br>metric = %{y:.6e}<extra></extra>",
                name=metric,
            ),
        ],
        "Readout Candidate Sweep: $(axes[compare_axis_index].label)",
        "$(axes[compare_axis_index].label) ($(axes[compare_axis_index].unit))",
        metric;
        legend_title="Metric",
    )
end

function build_selected_case_plot(summary_df)
    row_for(case_name) = only(filter(row -> row.case == case_name, eachrow(summary_df)))
    xy_baseline = row_for("xy_only_baseline")
    ro_only = row_for("readout_only_selected")
    full_shift = row_for("xy_plus_readout_shifted")
    xy_matched = row_for("xy_only_matched")
    ideal_additive = row_for("ideal_additive_reference")

    return build_plot(
        [
            scatter(
                mode="markers+text",
                x=[xy_baseline.fq_ghz, ro_only.fq_ghz, full_shift.fq_ghz, xy_matched.fq_ghz, ideal_additive.fq_ghz],
                y=[xy_baseline.re_y_dm_s, ro_only.re_y_dm_s, full_shift.re_y_dm_s, xy_matched.re_y_dm_s, ideal_additive.re_y_dm_s],
                text=["XY baseline", "RO only", "XY + Readout", "XY matched", "Ideal additive"],
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
end

function build_selected_case_ceff_plot(ceff_trace_df::DataFrame)
    case_order = unique(ceff_trace_df.case)
    traces = GenericTrace[]

    for case_name in case_order
        case_df = ceff_trace_df[ceff_trace_df.case .== case_name, :]
        sort!(case_df, :frequency_ghz)
        push!(
            traces,
            scatter(
                mode="lines",
                x=case_df.frequency_ghz,
                y=case_df.c_eff_fit_ff,
                customdata=hcat(
                    case_df.c_eff_direct_ff,
                    case_df.fit_rmse_s,
                    case_df.extracted_fq_ghz,
                ),
                hovertemplate="Case: $(case_name)<br>Frequency: %{x:.4f} GHz<br>Ceff fit: %{y:.4f} fF<br>Ceff direct Im(Y)/ω: %{customdata[0]:.4f} fF<br>fit RMSE: %{customdata[1]:.3e} S<br>extracted fq: %{customdata[2]:.6f} GHz<extra></extra>",
                name=case_name,
            ),
        )
    end

    return build_plot(
        traces,
        "Selected Cases: Ceff,q(ω) From All-Port PTC",
        "Frequency (GHz)",
        "Ceff,q (fF)";
        legend_title="Case",
    )
end

function build_selected_case_t1_plot(ceff_trace_df::DataFrame)
    case_order = unique(ceff_trace_df.case)
    traces = GenericTrace[]

    for case_name in case_order
        case_df = ceff_trace_df[ceff_trace_df.case .== case_name, :]
        case_df = case_df[isfinite.(case_df.t1_fit_us) .& (case_df.t1_fit_us .> 0), :]
        isempty(case_df) && continue
        sort!(case_df, :frequency_ghz)
        push!(
            traces,
            scatter(
                mode="lines",
                x=case_df.frequency_ghz,
                y=case_df.t1_fit_us,
                customdata=hcat(
                    case_df.c_eff_fit_ff,
                    case_df.re_y_dm_s,
                    case_df.extracted_fq_ghz,
                ),
                hovertemplate="Case: $(case_name)<br>Frequency: %{x:.4f} GHz<br>T1 fit: %{y:.4f} us<br>Ceff fit (all-port): %{customdata[0]:.4f} fF<br>Re(Ydm) loss metric: %{customdata[1]:.3e} S<br>extracted fq: %{customdata[2]:.6f} GHz<extra></extra>",
                name=case_name,
            ),
        )
    end

    fig = build_plot(
        traces,
        "Selected Cases: T1(ω) Using All-Port Ceff And Qubit-Port Loss",
        "Frequency (GHz)",
        "T1 (us)";
        legend_title="Case",
    )
    PlotlyJS.relayout!(fig, yaxis=attr(title="T1 (us)", type="log"))
    return fig
end

function build_yin_heatmap_plot(trace_df::DataFrame; sweep_column::Symbol, sweep_axis_title::AbstractString, title::AbstractString)
    freq_values = sort(unique(trace_df.frequency_ghz))
    sweep_values = sort(unique(trace_df[!, sweep_column]))
    freq_index = Dict(value => idx for (idx, value) in enumerate(freq_values))
    sweep_index = Dict(value => idx for (idx, value) in enumerate(sweep_values))

    re_grid = fill(NaN, length(sweep_values), length(freq_values))
    im_grid = fill(NaN, length(sweep_values), length(freq_values))

    for row in eachrow(trace_df)
        y_idx = sweep_index[row[sweep_column]]
        x_idx = freq_index[row.frequency_ghz]
        re_grid[y_idx, x_idx] = row.re_y_dm_s
        im_grid[y_idx, x_idx] = row.im_y_dm_s
    end

    grouped = combine(
        groupby(trace_df, sweep_column),
        :crossed => first => :crossed,
        :extracted_fq_ghz => first => :extracted_fq_ghz,
    )
    sort!(grouped, sweep_column)
    crossed_grouped = grouped[grouped.crossed .== true, :]
    uncrossed_grouped = grouped[grouped.crossed .== false, :]

    fig = PlotlyJS.make_subplots(rows=2, cols=1, shared_xaxes=true, vertical_spacing=0.10)
    PlotlyJS.add_trace!(
        fig,
        heatmap(
            x=freq_values,
            y=sweep_values,
            z=re_grid,
            colorscale="Viridis",
            colorbar=attr(title="Re(Ydm)", len=0.38, y=0.80),
            name="Re(Ydm)",
            showscale=true,
        ),
        row=1,
        col=1,
    )
    PlotlyJS.add_trace!(
        fig,
        scatter(
            x=crossed_grouped.extracted_fq_ghz,
            y=crossed_grouped[!, sweep_column],
            mode="markers",
            marker=attr(color="white", size=6, line=attr(color="black", width=1)),
            name="Extracted crossing",
        ),
        row=1,
        col=1,
    )
    PlotlyJS.add_trace!(
        fig,
        scatter(
            x=uncrossed_grouped.extracted_fq_ghz,
            y=uncrossed_grouped[!, sweep_column],
            mode="markers",
            marker=attr(symbol="x", color="black", size=8),
            name="No crossing in sweep window",
        ),
        row=1,
        col=1,
    )
    PlotlyJS.add_trace!(
        fig,
        heatmap(
            x=freq_values,
            y=sweep_values,
            z=im_grid,
            colorscale="RdBu",
            colorbar=attr(title="Im(Ydm)", len=0.38, y=0.20),
            name="Im(Ydm)",
            showscale=true,
            zmid=0.0,
        ),
        row=2,
        col=1,
    )
    PlotlyJS.add_trace!(
        fig,
        scatter(
            x=crossed_grouped.extracted_fq_ghz,
            y=crossed_grouped[!, sweep_column],
            mode="markers",
            marker=attr(color="white", size=6, line=attr(color="black", width=1)),
            name="Extracted crossing",
            showlegend=false,
        ),
        row=2,
        col=1,
    )
    PlotlyJS.add_trace!(
        fig,
        scatter(
            x=uncrossed_grouped.extracted_fq_ghz,
            y=uncrossed_grouped[!, sweep_column],
            mode="markers",
            marker=attr(symbol="x", color="black", size=8),
            name="No crossing in sweep window",
            showlegend=false,
        ),
        row=2,
        col=1,
    )

    PlotlyJS.relayout!(
        fig,
        title=title,
        xaxis=attr(title="Frequency (GHz)", showticklabels=false),
        xaxis2=attr(title="Frequency (GHz)"),
        yaxis=attr(title=sweep_axis_title),
        yaxis2=attr(title=sweep_axis_title),
        legend=attr(title=attr(text="Overlay")),
    )

    return fig
end

function display_persisted_plots_and_summary(inputs, persisted_outputs)
    lq_sweep_df = persisted_outputs.lq_sweep_df
    xy_lq_sweep_df = lq_sweep_df[lq_sweep_df.setup .== "XY only", :]
    full_lq_sweep_df = lq_sweep_df[lq_sweep_df.setup .== "XY + Readout", :]
    xy_crossed_df = xy_lq_sweep_df[xy_lq_sweep_df.crossed .== true, :]
    xy_uncrossed_df = xy_lq_sweep_df[xy_lq_sweep_df.crossed .== false, :]
    full_crossed_df = full_lq_sweep_df[full_lq_sweep_df.crossed .== true, :]
    full_uncrossed_df = full_lq_sweep_df[full_lq_sweep_df.crossed .== false, :]

    xy_yin_heatmap_plot = build_yin_heatmap_plot(
        persisted_outputs.lq_ydm_trace_df[persisted_outputs.lq_ydm_trace_df.setup .== "XY only", :];
        sweep_column=:lq_nh,
        sweep_axis_title="Lq (nH)",
        title="XY only: Ydm,in vs Frequency For All Lq",
    )

    full_yin_heatmap_plot = build_yin_heatmap_plot(
        persisted_outputs.lq_ydm_trace_df[persisted_outputs.lq_ydm_trace_df.setup .== "XY + Readout", :];
        sweep_column=:lq_nh,
        sweep_axis_title="Lq (nH)",
        title="XY + Readout: Ydm,in vs Frequency For All Lq",
    )

    window_yin_heatmap_plot = build_yin_heatmap_plot(
        persisted_outputs.window_length_ydm_trace_df;
        sweep_column=:coupled_window_length_um,
        sweep_axis_title="Coupled Window Length (um)",
        title="XY + Readout: Ydm,in vs Frequency For All Coupled Window Lengths",
    )

    readout_s21_vf_plot = build_plot(
        [
            scatter(mode="markers", x=persisted_outputs.readout_s21_raw_df.frequency_ghz, y=persisted_outputs.readout_s21_raw_df.S21_mag, name="Readout S21 raw"),
            scatter(mode="lines", x=persisted_outputs.readout_s21_model_df.frequency_ghz, y=persisted_outputs.readout_s21_model_df.S21_model_mag, name="Vector fitting model"),
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
                x=xy_crossed_df.lq_nh,
                y=xy_crossed_df.g_resonance_s,
                text=[@sprintf("fq = %.6f GHz", fq) for fq in xy_crossed_df.fq_ghz],
                hovertemplate="Setup: XY only<br>Lq: %{x:.3f} nH<br>Re(Ydm): %{y:.6e} S<br>%{text}<extra></extra>",
                name="XY only",
            ),
            scatter(
                mode="lines+markers",
                x=full_crossed_df.lq_nh,
                y=full_crossed_df.g_resonance_s,
                text=[@sprintf("fq = %.6f GHz", fq) for fq in full_crossed_df.fq_ghz],
                hovertemplate="Setup: XY + Readout<br>Lq: %{x:.3f} nH<br>Re(Ydm): %{y:.6e} S<br>%{text}<extra></extra>",
                name="XY + Readout",
            ),
            scatter(
                mode="markers",
                x=xy_uncrossed_df.lq_nh,
                y=xy_uncrossed_df.fallback_g_resonance_s,
                text=[
                    @sprintf(
                        "no Im(Ydm)=0 crossing inside sweep window<br>fallback fq = %.6f GHz",
                        fq,
                    ) for fq in xy_uncrossed_df.fallback_fq_ghz
                ],
                marker=attr(symbol="x-open", size=10),
                hovertemplate="Setup: XY only<br>Lq: %{x:.3f} nH<br>Fallback Re(Ydm): %{y:.6e} S<br>%{text}<extra></extra>",
                name="XY only (no crossing)",
            ),
            scatter(
                mode="markers",
                x=full_uncrossed_df.lq_nh,
                y=full_uncrossed_df.fallback_g_resonance_s,
                text=[
                    @sprintf(
                        "no Im(Ydm)=0 crossing inside sweep window<br>fallback fq = %.6f GHz",
                        fq,
                    ) for fq in full_uncrossed_df.fallback_fq_ghz
                ],
                marker=attr(symbol="x-open", size=10),
                hovertemplate="Setup: XY + Readout<br>Lq: %{x:.3f} nH<br>Fallback Re(Ydm): %{y:.6e} S<br>%{text}<extra></extra>",
                name="XY + Readout (no crossing)",
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
                x=persisted_outputs.window_length_df.coupled_window_length_um[persisted_outputs.window_length_df.crossed .== true],
                y=persisted_outputs.window_length_df.re_y_dm_s[persisted_outputs.window_length_df.crossed .== true],
                text=[
                    @sprintf("fq = %.6f GHz, Lq = %.3f nH", row.fq_ghz, row.lq_nh) for row in eachrow(persisted_outputs.window_length_df[persisted_outputs.window_length_df.crossed .== true, :])
                ],
                hovertemplate="Setup: XY + Readout<br>Coupled window: %{x:.1f} um<br>Re(Ydm): %{y:.6e} S<br>%{text}<extra></extra>",
                name="XY + Readout",
            ),
            scatter(
                mode="markers",
                x=persisted_outputs.window_length_df.coupled_window_length_um[persisted_outputs.window_length_df.crossed .== false],
                y=persisted_outputs.window_length_df.fallback_g_resonance_s[persisted_outputs.window_length_df.crossed .== false],
                marker=attr(symbol="x-open", size=10),
                text=[
                    "no Im(Ydm)=0 crossing in coarse/fine match search" for _ in 1:nrow(persisted_outputs.window_length_df[persisted_outputs.window_length_df.crossed .== false, :])
                ],
                hovertemplate="Setup: XY + Readout<br>Coupled window: %{x:.1f} um<br>%{text}<extra></extra>",
                name="XY + Readout (no crossing)",
            ),
        ],
        "XY + Readout: Re(Ydm,in) vs Coupled Window Length",
        "Coupled Window Length (um)",
        "Re(Ydm,in) (S)";
        legend_title="Setup",
    )

    ro_window_length_plot = build_plot(
        [
            scatter(
                mode="lines+markers",
                x=persisted_outputs.ro_window_length_df.coupled_window_length_um[persisted_outputs.ro_window_length_df.crossed .== true],
                y=persisted_outputs.ro_window_length_df.re_y_dm_s[persisted_outputs.ro_window_length_df.crossed .== true],
                text=[
                    @sprintf("fq = %.6f GHz, Lq = %.3f nH", row.fq_ghz, row.lq_nh) for row in eachrow(persisted_outputs.ro_window_length_df[persisted_outputs.ro_window_length_df.crossed .== true, :])
                ],
                hovertemplate="Setup: RO only<br>Coupled window: %{x:.1f} um<br>Re(Ydm): %{y:.6e} S<br>%{text}<extra></extra>",
                name="RO only",
            ),
            scatter(
                mode="markers",
                x=persisted_outputs.ro_window_length_df.coupled_window_length_um[persisted_outputs.ro_window_length_df.crossed .== false],
                y=persisted_outputs.ro_window_length_df.fallback_g_resonance_s[persisted_outputs.ro_window_length_df.crossed .== false],
                marker=attr(symbol="x-open", size=10),
                text=[
                    "no Im(Ydm)=0 crossing in coarse/fine match search" for _ in 1:nrow(persisted_outputs.ro_window_length_df[persisted_outputs.ro_window_length_df.crossed .== false, :])
                ],
                hovertemplate="Setup: RO only<br>Coupled window: %{x:.1f} um<br>%{text}<extra></extra>",
                name="RO only (no crossing)",
            ),
        ],
        "RO only: Re(Ydm,in) vs Coupled Window Length",
        "Coupled Window Length (um)",
        "Re(Ydm,in) (S)";
        legend_title="Setup",
    )

    candidate_compare_plot = build_candidate_compare_plot(inputs, persisted_outputs)
    selected_case_plot = build_selected_case_plot(persisted_outputs.summary_df)
    selected_case_ceff_plot = build_selected_case_ceff_plot(persisted_outputs.selected_case_ceff_trace_df)
    selected_case_t1_plot = build_selected_case_t1_plot(persisted_outputs.selected_case_ceff_trace_df)

    figure_paths = build_figure_paths(persisted_outputs.paths)
    try_save_png(readout_s21_vf_plot, figure_paths.readout_s21_png_path, inputs)
    try_save_png(candidate_compare_plot, figure_paths.candidate_compare_png_path, inputs)
    try_save_png(lq_sweep_plot, figure_paths.lq_sweep_png_path, inputs)
    try_save_png(xy_yin_heatmap_plot, figure_paths.xy_only_yin_heatmap_png_path, inputs)
    try_save_png(full_yin_heatmap_plot, figure_paths.full_yin_heatmap_png_path, inputs)
    try_save_png(ro_window_length_plot, figure_paths.ro_window_length_png_path, inputs)
    try_save_png(window_length_plot, figure_paths.window_length_png_path, inputs)
    try_save_png(window_yin_heatmap_plot, figure_paths.window_length_yin_heatmap_png_path, inputs)
    try_save_png(selected_case_ceff_plot, figure_paths.selected_case_ceff_png_path, inputs)
    try_save_png(selected_case_t1_plot, figure_paths.selected_case_t1_png_path, inputs)
    try_save_png(selected_case_plot, figure_paths.selected_case_png_path, inputs)

    display(readout_s21_vf_plot)
    display(candidate_compare_plot)
    display(lq_sweep_plot)
    display(xy_yin_heatmap_plot)
    display(full_yin_heatmap_plot)
    display(ro_window_length_plot)
    display(window_length_plot)
    display(window_yin_heatmap_plot)
    display(selected_case_ceff_plot)
    display(selected_case_t1_plot)
    display(selected_case_plot)

    println("Vector-fitting resonance summary:")
    for row in eachrow(persisted_outputs.readout_s21_resonance_df)
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
    for row in eachrow(persisted_outputs.summary_df)
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
    println("Selected-case Ceff summary (all-port PTC, local slope fit):")
    ceff_case_summary_df = combine(
        groupby(persisted_outputs.selected_case_ceff_trace_df, :case),
        :extracted_fq_ghz => first => :extracted_fq_ghz,
        :ceff_sample_frequency_ghz => first => :ceff_sample_frequency_ghz,
        :c_eff_fit_at_extracted_f_ff => first => :c_eff_fit_at_extracted_f_ff,
        :c_eff_direct_at_extracted_f_ff => first => :c_eff_direct_at_extracted_f_ff,
    )
    for row in eachrow(ceff_case_summary_df)
        @printf(
            "  %-26s fq = %7.4f GHz | sampled at %.4f GHz | Ceff_fit = % .4f fF | Ceff_direct = % .4f fF\n",
            row.case,
            row.extracted_fq_ghz,
            row.ceff_sample_frequency_ghz,
            row.c_eff_fit_at_extracted_f_ff,
            row.c_eff_direct_at_extracted_f_ff,
        )
    end

    println()
    println("Selected-case T1 summary (T1 = Ceff_fit[all-port] / Re(Ydm)[qubit-port-only]):")
    t1_case_summary_df = combine(
        groupby(persisted_outputs.selected_case_ceff_trace_df, :case),
        :extracted_fq_ghz => first => :extracted_fq_ghz,
        :ceff_sample_frequency_ghz => first => :ceff_sample_frequency_ghz,
        :t1_fit_at_extracted_f_us => first => :t1_fit_at_extracted_f_us,
        :extracted_re_y_dm_s => first => :extracted_re_y_dm_s,
    )
    for row in eachrow(t1_case_summary_df)
        @printf(
            "  %-26s fq = %7.4f GHz | sampled at %.4f GHz | T1_fit = % .4f us | Re(Ydm) sample = % .6e S\n",
            row.case,
            row.extracted_fq_ghz,
            row.ceff_sample_frequency_ghz,
            row.t1_fit_at_extracted_f_us,
            row.extracted_re_y_dm_s,
        )
    end

    println()
    println("Loaded raw outputs from:")
    println("  ", persisted_outputs.paths.raw_dir)
    println("Figure output directory:")
    println("  ", persisted_outputs.paths.figures_dir)

    if inputs.hold_after_plotting
        println()
        println("Plots are being served from a temporary local PlotlyJS server.")
        println("Press Enter to end the script after you finish viewing the plots...")
        readline()
    end
end
