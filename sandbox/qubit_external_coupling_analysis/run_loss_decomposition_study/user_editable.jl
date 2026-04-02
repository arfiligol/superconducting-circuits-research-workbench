function build_explicit_readout_coupling_axis()
    candidates = [
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

    return ParameterSetSweepAxis(
        label="Readout coupling pair",
        unit="pair",
        value_labels=[candidate.label for candidate in candidates],
        display_values=collect(1.0:length(candidates)),
        assignments=[
            Dict(:c_rq1_f => candidate.c_rq1_f, :c_rq2_f => candidate.c_rq2_f) for candidate in candidates
        ],
    )
end

function build_difference_scaled_readout_coupling_axis()
    return DifferenceScaleSweepAxis(
        positive_parameter=:c_rq1_f,
        negative_parameter=:c_rq2_f,
        label="Readout coupling delta scale",
        unit="xΔC",
        average_value=96.0 * fF,
        base_difference_value=8.0 * fF,
        scale_values=[0.25, 0.50, 0.75, 1.00, 1.25, 1.50, 2.00],
    )
end

function build_user_editable_inputs()
    return (
        # Target qubit frequency for the XY-only baseline reference.
        baseline_target_f_ghz=4.00,
        # Preferred readout-only / XY-only loss ratio for the candidate-selection step.
        readout_ratio_comparison_target=0.20,
        # Minimum acceptable readout-only / XY-only loss ratio during candidate selection.
        readout_ratio_acceptable_min=0.15,
        # Maximum acceptable readout-only / XY-only loss ratio during candidate selection.
        readout_ratio_acceptable_max=0.30,
        # Fine-sweep half-window around the coarse matched-Lq point used by the
        # XY-only matched step and the coupled-window diagnostic step.
        matched_lq_fine_half_window_h=0.60 * nH,
        # Fine-sweep Lq step used after the coarse matched-Lq search.
        matched_lq_fine_step_h=0.02 * nH,
        # Keep the script alive after plotting so the temporary PlotlyJS server does not disappear immediately.
        hold_after_plotting=true,
        # Simulation execution controls.
        #
        # `max_parallel_workers` cannot exceed the Julia thread count available at
        # startup. If you want more workers, launch Julia with `-t auto` or set
        # `JULIA_NUM_THREADS` before running the script.
        simulation_config=(
            max_parallel_workers=Base.Threads.nthreads(),
            parameter_sweep_batch_size=12,
            use_threaded_candidate_sweep=true,
            use_threaded_standalone_lq_sweeps=false,
        ),

        # Floating-qubit capacitances.
        c_g1_f=102.38399 * fF,
        c_g2_f=102.33597 * fF,
        c_q_f=59.25219 * fF,
        c_xy1_f=0.16851 * fF,
        c_xy2_f=0.74816 * fF,

        # Shared uncoupled transmission-line RLGC.
        common_l_per_m_h=404.313e-9,
        common_c_per_m_f=179.86e-12,
        common_r_per_m_ohm=0.0,
        common_g_per_m_s=0.0,

        # Port terminations used before reduction.
        qubit_port_res_ohm=50.0,
        xy_port_res_ohm=50.0,
        readout_port_res_ohm=50.0,

        # Readout-branch geometry.
        left_readout_length_m=3462.732 * um,
        purcell_filter_length_m=8500 * um,
        right_readout_length_m=3462.732 * um,
        qwr_length_m=4731.6735 * um,
        pf_coupling_cap_in_f=41.06185 * fF,
        pf_coupling_cap_out_f=125.2587 * fF,
        pf_window_start_m=2200.0 * um,
        qwr_window_start_m=10.0 * um,

        # Distributed discretization target Δz.
        left_readout_target_dz_m=150.0 * um,
        purcell_filter_target_dz_m=150.0 * um,
        right_readout_target_dz_m=150.0 * um,
        qwr_target_dz_m=150.0 * um,
        coupled_window_target_dz_m=15.0 * um,

        # Coupled-window parameterization mode.
        coupled_window_input_mode=:q2d_rlgc,
        coupled_window_zeven_ohm=56.0,
        coupled_window_zodd_ohm=44.0,
        coupled_window_neven=2.45,
        coupled_window_nodd=2.60,

        # Q2D coupled-window RLGC data.
        q2d_l11_per_m_h=410.86374e-9,
        q2d_l22_per_m_h=410.85454e-9,
        q2d_m_per_m_h=19.08527e-9,
        q2d_c11_maxwell_per_m_f=170.29805e-12,
        q2d_c22_maxwell_per_m_f=170.29538e-12,
        q2d_c12_maxwell_per_m_f=-8.09678e-12,
        q2d_c21_maxwell_per_m_f=-8.09678e-12,
        q2d_r11_per_m_ohm=0.0,
        q2d_r22_per_m_ohm=0.0,
        q2d_g11_per_m_s=0.0,
        q2d_g22_per_m_s=0.0,

        # Parameter-sweep axes for the readout-candidate search.
        #
        # The default setup mixes:
        # 1. a single-parameter sweep on coupled-window length
        # 2. an explicit paired-parameter sweep for (C_rq1, C_rq2)
        #
        # If you want to preserve the average coupling and only scale the
        # difference between pad-1 and pad-2 couplings, replace the second axis
        # with `build_difference_scaled_readout_coupling_axis()`.
        readout_candidate_sweep_axes=AbstractParameterSweepAxis[
            ScalarParameterSweepAxis(
                parameter=:coupled_window_length_m,
                label="Coupled Window Length",
                unit="um",
                values=[
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
                ],
                display_divisor=um,
            ),
            build_explicit_readout_coupling_axis(),
        ],

        # Lq sweep and frequency windows.
        lq_sweep_values_h=collect(10.0:1.0:28.0) .* nH,
        qubit_sweep_start_ghz=1.0,
        qubit_sweep_stop_ghz=7.0,
        qubit_sweep_step_ghz=0.002,
        readout_s21_sweep_start_ghz=1,
        readout_s21_sweep_stop_ghz=10,
        readout_s21_sweep_step_ghz=0.02,

        # Vector fitting setup.
        vf_expected_resonators=2,
        vf_background_poles=2,

        # Effective-capacitance fitting setup.
        ceff_fit_config=(
            half_window_points=4,
        ),

        # Plot controls for persisted multi-parameter sweep results.
        #
        # `candidate_compare_axis_index` follows the App-style convention:
        # it picks which sweep axis becomes the plot x-axis, while
        # `candidate_sweep_index` chooses the fixed coordinates for the
        # remaining axes.
        plot_controls=(
            candidate_metric=:readout_to_xy_ratio,
            candidate_compare_axis_index=1,
            candidate_sweep_index=0,
            save_png_figures=false,
            figure_width_px=1280,
            figure_height_px=760,
        ),
    )
end
