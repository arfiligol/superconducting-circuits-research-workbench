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

    left_readout = cpw_line!(draft, "left_readout"; line=left_readout_spec)
    purcell_filter = purcell_filter!(
        draft,
        "purcell_filter";
        line=purcell_filter_spec,
        left_coupling_cap_f=cfg.pf_coupling_cap_in_f,
        right_coupling_cap_f=cfg.pf_coupling_cap_out_f,
    )
    right_readout = cpw_line!(draft, "right_readout"; line=right_readout_spec)

    connect_pins!(draft, pin(left_readout, :right), pin(purcell_filter, :left); id="left_readout_to_pf")
    connect_pins!(draft, pin(purcell_filter, :right), pin(right_readout, :left); id="pf_to_right_readout")

    readout_in = external_pin!(draft, "readout_in")
    readout_out = external_pin!(draft, "readout_out")
    connect_pins!(draft, pin(left_readout, :left), pin(readout_in, :node); id="readout_in_connection")
    connect_pins!(draft, pin(right_readout, :right), pin(readout_out, :node); id="readout_out_connection")
    terminated_port!(
        draft,
        pin(readout_in, :node);
        port_number=4,
        resistance_ohm=cfg.readout_port_res_ohm,
        id="readout_in_port",
    )
    terminated_port!(
        draft,
        pin(readout_out, :node);
        port_number=5,
        resistance_ohm=cfg.readout_port_res_ohm,
        id="readout_out_port",
    )

    qwr = quarter_wave_resonator!(draft, "qwr"; line=qwr_spec, boundary=:short, prefix="qwr")

    coupled_window!(
        draft,
        section_m(
            purcell_filter,
            cfg.pf_window_start_m,
            cfg.pf_window_start_m + cfg.coupled_window_length_m,
        ),
        section_m(
            qwr,
            cfg.qwr_window_start_m,
            cfg.qwr_window_start_m + cfg.coupled_window_length_m,
        );
        id="pf_qwr_window",
        spec=coupled_window_spec,
    )

    qubit = differential_lc_qubit!(
        draft,
        "floating_qubit";
        Cg1=cfg.c_g1_f,
        Cg2=cfg.c_g2_f,
        Cq=cfg.c_q_f,
        Lq=cfg.l_q_h,
        prefix="q",
    )
    xy = external_pin!(draft, "xy_node")

    if cfg.c_xy1_f > 0
        couple_capacitive!(
            draft,
            pin(qubit, :pad1),
            pin(xy, :node);
            C=cfg.c_xy1_f,
            id="xy_to_q1",
        )
    end
    if cfg.c_xy2_f > 0
        couple_capacitive!(
            draft,
            pin(qubit, :pad2),
            pin(xy, :node);
            C=cfg.c_xy2_f,
            id="xy_to_q2",
        )
    end
    if cfg.c_rq1_f > 0
        couple_capacitive!(
            draft,
            pin(qwr, :open),
            pin(qubit, :pad1);
            C=cfg.c_rq1_f,
            id="qwr_to_q1",
        )
    end
    if cfg.c_rq2_f > 0
        couple_capacitive!(
            draft,
            pin(qwr, :open),
            pin(qubit, :pad2);
            C=cfg.c_rq2_f,
            id="qwr_to_q2",
        )
    end

    terminated_port!(
        draft,
        pin(qubit, :pad1);
        port_number=1,
        resistance_ohm=cfg.qubit_port_res_ohm,
        id="qubit_pad1_port",
    )
    terminated_port!(
        draft,
        pin(qubit, :pad2);
        port_number=2,
        resistance_ohm=cfg.qubit_port_res_ohm,
        id="qubit_pad2_port",
    )
    terminated_port!(
        draft,
        pin(xy, :node);
        port_number=3,
        resistance_ohm=cfg.xy_port_res_ohm,
        id="xy_port",
    )

    symbolic_artifact = finalize_circuit(draft; renumber_nodes=false)
    numeric_artifact = finalize_circuit(draft; renumber_nodes=true)

    return (
        draft=draft,
        symbolic_netlist=symbolic_artifact.netlist,
        numeric_netlist=numeric_artifact.netlist,
        symbolic_artifact=symbolic_artifact,
        numeric_artifact=numeric_artifact,
        left_readout_spec=left_readout_spec,
        purcell_filter_spec=purcell_filter_spec,
        right_readout_spec=right_readout_spec,
        qwr_spec=qwr_spec,
        coupled_window_spec=coupled_window_spec,
    )
end
