function config_without_xy(cfg::StudyConfig)
    return updated_config(cfg; c_xy1_f=0.0, c_xy2_f=0.0)
end

function build_study_circuit_context(inputs)
    initial_coupled_window_length_m = let
        window_axis = only(filter(axis -> axis isa ScalarParameterSweepAxis && axis.parameter == :coupled_window_length_m, inputs.readout_candidate_sweep_axes))
        first(window_axis.values)
    end

    base_cfg = StudyConfig(
        c_g1_f=inputs.c_g1_f,
        c_g2_f=inputs.c_g2_f,
        c_q_f=inputs.c_q_f,
        c_xy1_f=inputs.c_xy1_f,
        c_xy2_f=inputs.c_xy2_f,
        c_rq1_f=0.0,
        c_rq2_f=0.0,
        common_l_per_m_h=inputs.common_l_per_m_h,
        common_c_per_m_f=inputs.common_c_per_m_f,
        common_r_per_m_ohm=inputs.common_r_per_m_ohm,
        common_g_per_m_s=inputs.common_g_per_m_s,
        left_readout_length_m=inputs.left_readout_length_m,
        purcell_filter_length_m=inputs.purcell_filter_length_m,
        right_readout_length_m=inputs.right_readout_length_m,
        qwr_length_m=inputs.qwr_length_m,
        left_readout_target_dz_m=inputs.left_readout_target_dz_m,
        purcell_filter_target_dz_m=inputs.purcell_filter_target_dz_m,
        right_readout_target_dz_m=inputs.right_readout_target_dz_m,
        qwr_target_dz_m=inputs.qwr_target_dz_m,
        coupled_window_target_dz_m=inputs.coupled_window_target_dz_m,
        pf_coupling_cap_in_f=inputs.pf_coupling_cap_in_f,
        pf_coupling_cap_out_f=inputs.pf_coupling_cap_out_f,
        coupled_window_input_mode=inputs.coupled_window_input_mode,
        coupled_window_length_m=initial_coupled_window_length_m,
        pf_window_start_m=inputs.pf_window_start_m,
        qwr_window_start_m=inputs.qwr_window_start_m,
        coupled_window_zeven_ohm=inputs.coupled_window_zeven_ohm,
        coupled_window_zodd_ohm=inputs.coupled_window_zodd_ohm,
        coupled_window_neven=inputs.coupled_window_neven,
        coupled_window_nodd=inputs.coupled_window_nodd,
        q2d_l11_per_m_h=inputs.q2d_l11_per_m_h,
        q2d_l22_per_m_h=inputs.q2d_l22_per_m_h,
        q2d_m_per_m_h=inputs.q2d_m_per_m_h,
        q2d_c11_maxwell_per_m_f=inputs.q2d_c11_maxwell_per_m_f,
        q2d_c22_maxwell_per_m_f=inputs.q2d_c22_maxwell_per_m_f,
        q2d_c12_maxwell_per_m_f=inputs.q2d_c12_maxwell_per_m_f,
        q2d_c21_maxwell_per_m_f=inputs.q2d_c21_maxwell_per_m_f,
        q2d_r11_per_m_ohm=inputs.q2d_r11_per_m_ohm,
        q2d_r22_per_m_ohm=inputs.q2d_r22_per_m_ohm,
        q2d_g11_per_m_s=inputs.q2d_g11_per_m_s,
        q2d_g22_per_m_s=inputs.q2d_g22_per_m_s,
        qubit_port_res_ohm=inputs.qubit_port_res_ohm,
        xy_port_res_ohm=inputs.xy_port_res_ohm,
        readout_port_res_ohm=inputs.readout_port_res_ohm,
        sweep_start_ghz=inputs.qubit_sweep_start_ghz,
        sweep_stop_ghz=inputs.qubit_sweep_stop_ghz,
        sweep_step_ghz=inputs.qubit_sweep_step_ghz,
    )

    return (
        base_cfg=base_cfg,
        xy_only_cfg=updated_config(base_cfg; c_rq1_f=0.0, c_rq2_f=0.0),
    )
end
