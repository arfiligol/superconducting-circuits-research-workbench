function section_count_from_target_dz(length_m, target_dz_m; label)
    target_dz_m > 0 || error("target Δz for $(label) must be positive.")
    length_m > 0 || error("length for $(label) must be positive.")
    return max(1, ceil(Int, length_m / target_dz_m))
end

function make_rlgc_spec(length_m, target_dz_m, cfg::StudyConfig; label)
    return RLGCSpec(
        length_m=length_m,
        n_sections=section_count_from_target_dz(length_m, target_dz_m; label=label),
        l_per_m_h=cfg.common_l_per_m_h,
        c_per_m_f=cfg.common_c_per_m_f,
        r_per_m_ohm=cfg.common_r_per_m_ohm,
        g_per_m_s=cfg.common_g_per_m_s,
    )
end

function build_coupled_window_spec(cfg::StudyConfig)
    n_sections = section_count_from_target_dz(
        cfg.coupled_window_length_m,
        cfg.coupled_window_target_dz_m;
        label="coupled window",
    )

    if cfg.coupled_window_input_mode == :modal
        window_mutual = JosephsonCircuits.even_odd_to_mutual(
            cfg.coupled_window_zeven_ohm,
            cfg.coupled_window_zodd_ohm,
            cfg.coupled_window_neven,
            cfg.coupled_window_nodd,
        )

        return CoupledWindowSpec(
            length_m=cfg.coupled_window_length_m,
            n_sections=n_sections,
            l11_per_m_h=window_mutual.L[1, 1],
            l22_per_m_h=window_mutual.L[2, 2],
            lm_per_m_h=window_mutual.L[1, 2],
            c1g_per_m_f=window_mutual.C[1, 1],
            c2g_per_m_f=window_mutual.C[2, 2],
            cm_per_m_f=window_mutual.C[1, 2],
        )
    elseif cfg.coupled_window_input_mode == :q2d_rlgc
        l_matrix = [
            cfg.q2d_l11_per_m_h cfg.q2d_m_per_m_h
            cfg.q2d_m_per_m_h cfg.q2d_l22_per_m_h
        ]

        c_maxwell = [
            cfg.q2d_c11_maxwell_per_m_f cfg.q2d_c12_maxwell_per_m_f
            cfg.q2d_c21_maxwell_per_m_f cfg.q2d_c22_maxwell_per_m_f
        ]
        c_mutual = JosephsonCircuits.maxwell_to_mutual(c_maxwell)

        return CoupledWindowSpec(
            length_m=cfg.coupled_window_length_m,
            n_sections=n_sections,
            l11_per_m_h=l_matrix[1, 1],
            l22_per_m_h=l_matrix[2, 2],
            lm_per_m_h=l_matrix[1, 2],
            c1g_per_m_f=c_mutual[1, 1],
            c2g_per_m_f=c_mutual[2, 2],
            cm_per_m_f=c_mutual[1, 2],
            r1_per_m_ohm=cfg.q2d_r11_per_m_ohm,
            r2_per_m_ohm=cfg.q2d_r22_per_m_ohm,
            g1_per_m_s=cfg.q2d_g11_per_m_s,
            g2_per_m_s=cfg.q2d_g22_per_m_s,
        )
    end

    error("Unsupported coupled_window_input_mode=$(cfg.coupled_window_input_mode).")
end

function build_floating_qubit_environment_netlist(cfg::StudyConfig)
    left_readout_spec = make_rlgc_spec(
        cfg.left_readout_length_m,
        cfg.left_readout_target_dz_m,
        cfg;
        label="left readout",
    )
    purcell_filter_spec = make_rlgc_spec(
        cfg.purcell_filter_length_m,
        cfg.purcell_filter_target_dz_m,
        cfg;
        label="Purcell filter",
    )
    right_readout_spec = make_rlgc_spec(
        cfg.right_readout_length_m,
        cfg.right_readout_target_dz_m,
        cfg;
        label="right readout",
    )
    qwr_spec = make_rlgc_spec(
        cfg.qwr_length_m,
        cfg.qwr_target_dz_m,
        cfg;
        label="QWR",
    )
    coupled_window_spec = build_coupled_window_spec(cfg)

    draft = CircuitDraft("floating_qubit_loss_decomposition")

    left_readout = add_readout_line_component!(draft; id="left_readout", line_spec=left_readout_spec)
    purcell_filter = add_half_wave_purcell_filter_component!(
        draft;
        id="purcell_filter",
        left_coupling_cap_f=cfg.pf_coupling_cap_in_f,
        right_coupling_cap_f=cfg.pf_coupling_cap_out_f,
        line_spec=purcell_filter_spec,
    )
    right_readout = add_readout_line_component!(draft; id="right_readout", line_spec=right_readout_spec)
    apply_series_chain!(draft, left_readout, purcell_filter, right_readout)

    connect!(draft, left_readout, :left, "readout_in")
    connect!(draft, right_readout, :right, "readout_out")
    add_port_with_termination!(
        draft;
        port_number=4,
        node="readout_in",
        resistance_ohm=cfg.readout_port_res_ohm,
        prefix="readout",
    )
    add_port_with_termination!(
        draft;
        port_number=5,
        node="readout_out",
        resistance_ohm=cfg.readout_port_res_ohm,
        prefix="readout",
    )

    qwr_open_node = "qwr_open_node"
    qwr_line = add_transmission_line!(
        draft;
        id="qwr_line",
        prefix="qwr",
        start_node=qwr_open_node,
        end_node=draft.ground_node,
        spec=qwr_spec,
        ground_node=draft.ground_node,
        add_shunt_at_last_node=false,
    )

    apply_coupled_window!(
        draft;
        prefix="pf_qwr_window",
        line_a=purcell_filter,
        span_a=LineSpan(cfg.pf_window_start_m, cfg.pf_window_start_m + cfg.coupled_window_length_m),
        line_b=qwr_line,
        span_b=LineSpan(cfg.qwr_window_start_m, cfg.qwr_window_start_m + cfg.coupled_window_length_m),
        spec=coupled_window_spec,
    )

    q1_pad = "q1_pad"
    q2_pad = "q2_pad"
    xy_node = "xy_node"

    add_component!(draft; name="C_g1", node1=q1_pad, node2=draft.ground_node, value=cfg.c_g1_f)
    add_component!(draft; name="C_g2", node1=q2_pad, node2=draft.ground_node, value=cfg.c_g2_f)
    add_component!(draft; name="C_q", node1=q1_pad, node2=q2_pad, value=cfg.c_q_f)
    add_component!(draft; name="L_q", node1=q1_pad, node2=q2_pad, value=cfg.l_q_h)

    if cfg.c_xy1_f > 0
        add_component!(draft; name="C_xy1", node1=q1_pad, node2=xy_node, value=cfg.c_xy1_f)
    end
    if cfg.c_xy2_f > 0
        add_component!(draft; name="C_xy2", node1=q2_pad, node2=xy_node, value=cfg.c_xy2_f)
    end
    if cfg.c_rq1_f > 0
        add_component!(draft; name="C_rq1", node1=qwr_open_node, node2=q1_pad, value=cfg.c_rq1_f)
    end
    if cfg.c_rq2_f > 0
        add_component!(draft; name="C_rq2", node1=qwr_open_node, node2=q2_pad, value=cfg.c_rq2_f)
    end

    add_port_with_termination!(
        draft;
        port_number=1,
        node=q1_pad,
        resistance_ohm=cfg.qubit_port_res_ohm,
        prefix="qubit",
    )
    add_port_with_termination!(
        draft;
        port_number=2,
        node=q2_pad,
        resistance_ohm=cfg.qubit_port_res_ohm,
        prefix="qubit",
    )
    add_port_with_termination!(
        draft;
        port_number=3,
        node=xy_node,
        resistance_ohm=cfg.xy_port_res_ohm,
        prefix="xy",
    )

    return (
        draft=draft,
        symbolic_netlist=finalize_to_josephson_netlist(draft; renumber_nodes=false),
        numeric_netlist=finalize_to_josephson_netlist(draft; renumber_nodes=true),
        left_readout_spec=left_readout_spec,
        purcell_filter_spec=purcell_filter_spec,
        right_readout_spec=right_readout_spec,
        qwr_spec=qwr_spec,
        coupled_window_spec=coupled_window_spec,
    )
end
