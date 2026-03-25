using LinearAlgebra
using JosephsonCircuits
using PlotlyJS
using CSV
using DataFrames
using Printf

const GHz = 1e9
const mm = 1e-3
const um = 1e-6
const nH = 1e-9
const fF = 1e-15

Base.@kwdef struct StudyConfig
    c_g1_f::Float64 = 102.38399 * fF
    c_g2_f::Float64 = 102.33597 * fF
    c_q_f::Float64 = 59.25219 * fF
    c_xy1_f::Float64 = 2.5 * fF
    c_xy2_f::Float64 = 2.3 * fF
    c_rq1_f::Float64 = 2.5 * fF
    c_rq2_f::Float64 = 2.3 * fF
    l_q_h::Float64 = 20.0 * nH

    qubit_port_res_ohm::Float64 = 50.0
    xy_port_res_ohm::Float64 = 50.0
    readout_port_res_ohm::Float64 = 50.0

    common_l_per_m_h::Float64 = 404.313e-9
    common_c_per_m_f::Float64 = 179.86e-12
    common_r_per_m_ohm::Float64 = 0.0
    common_g_per_m_s::Float64 = 0.0

    left_readout_length_m::Float64 = 3462.732 * um
    purcell_filter_length_m::Float64 = 9900.32 * um
    right_readout_length_m::Float64 = 3462.732 * um
    qwr_length_m::Float64 = 4731.6735 * um

    left_readout_target_dz_m::Float64 = 150.0 * um
    purcell_filter_target_dz_m::Float64 = 150.0 * um
    right_readout_target_dz_m::Float64 = 150.0 * um
    qwr_target_dz_m::Float64 = 150.0 * um
    coupled_window_target_dz_m::Float64 = 15.0 * um

    pf_coupling_cap_in_f::Float64 = 41.06185 * fF
    pf_coupling_cap_out_f::Float64 = 125.2587 * fF

    coupled_window_input_mode::Symbol = :q2d_rlgc
    coupled_window_length_m::Float64 = 300.0 * um
    pf_window_start_m::Float64 = 2200.0 * um
    qwr_window_start_m::Float64 = 10.0 * um

    coupled_window_zeven_ohm::Float64 = 56.0
    coupled_window_zodd_ohm::Float64 = 44.0
    coupled_window_neven::Float64 = 2.45
    coupled_window_nodd::Float64 = 2.60

    q2d_l11_per_m_h::Float64 = 410.86374e-9
    q2d_l22_per_m_h::Float64 = 410.85454e-9
    q2d_m_per_m_h::Float64 = 19.08527e-9

    q2d_c11_maxwell_per_m_f::Float64 = 170.29805e-12
    q2d_c22_maxwell_per_m_f::Float64 = 170.29538e-12
    q2d_c12_maxwell_per_m_f::Float64 = -8.09678e-12
    q2d_c21_maxwell_per_m_f::Float64 = -8.09678e-12

    q2d_r11_per_m_ohm::Float64 = 0.0
    q2d_r22_per_m_ohm::Float64 = 0.0
    q2d_g11_per_m_s::Float64 = 0.0
    q2d_g22_per_m_s::Float64 = 0.0

    sweep_start_ghz::Float64 = 3.0
    sweep_stop_ghz::Float64 = 4.6
    sweep_step_ghz::Float64 = 0.002
end

function updated_config(cfg::StudyConfig; kwargs...)
    names = fieldnames(StudyConfig)
    values = Dict(name => getfield(cfg, name) for name in names)
    for (key, value) in kwargs
        values[key] = value
    end
    return StudyConfig(; (name => values[name] for name in names)...)
end

function build_plot(traces, title, xaxis_title, yaxis_title; legend_title="Legend")
    return plot(
        traces,
        Layout(
            title=title,
            xaxis=attr(title=xaxis_title),
            yaxis=attr(title=yaxis_title),
            legend=attr(title=attr(text=legend_title)),
        ),
    )
end

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

    const_qwr_open = "qwr_open_node"
    qwr_line = add_transmission_line!(
        draft;
        id="qwr_line",
        prefix="qwr",
        start_node=const_qwr_open,
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

    c_xy1 = cfg.c_xy1_f
    c_xy2 = cfg.c_xy2_f
    c_rq1 = cfg.c_rq1_f
    c_rq2 = cfg.c_rq2_f

    if c_xy1 > 0
        add_component!(draft; name="C_xy1", node1=q1_pad, node2=xy_node, value=c_xy1)
    end
    if c_xy2 > 0
        add_component!(draft; name="C_xy2", node1=q2_pad, node2=xy_node, value=c_xy2)
    end
    if c_rq1 > 0
        add_component!(draft; name="C_rq1", node1=const_qwr_open, node2=q1_pad, value=c_rq1)
    end
    if c_rq2 > 0
        add_component!(draft; name="C_rq2", node1=const_qwr_open, node2=q2_pad, value=c_rq2)
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

    symbolic_netlist = finalize_to_josephson_netlist(draft; renumber_nodes=false)
    numeric_netlist = finalize_to_josephson_netlist(draft; renumber_nodes=true)

    return (
        draft=draft,
        symbolic_netlist=symbolic_netlist,
        numeric_netlist=numeric_netlist,
        left_readout_spec=left_readout_spec,
        purcell_filter_spec=purcell_filter_spec,
        right_readout_spec=right_readout_spec,
        qwr_spec=qwr_spec,
        coupled_window_spec=coupled_window_spec,
    )
end

function z_to_y_cube(solution)
    z_cube = Array(solution.linearized.Z[1, :, 1, :, :])
    _, _, n_freq = size(z_cube)
    y_cube = similar(z_cube)

    for k in 1:n_freq
        y_cube[:, :, k] = inv(Matrix(@view z_cube[:, :, k]))
    end
    return y_cube
end

function apply_port_termination_compensation(y_cube; resistance_ohm_by_port)
    compensated = copy(y_cube)
    for (port, resistance_ohm) in resistance_ohm_by_port
        shunt_admittance = 1 / resistance_ohm
        compensated[port, port, :] .-= shunt_admittance
    end
    return compensated
end

function differential_mode_weights(cfg::StudyConfig)
    w1 = cfg.c_g1_f + cfg.c_xy1_f + cfg.c_rq1_f
    w2 = cfg.c_g2_f + cfg.c_xy2_f + cfg.c_rq2_f
    total = w1 + w2
    return (alpha=w1 / total, beta=w2 / total, w1=w1, w2=w2)
end

function build_qubit_modal_transform(cfg::StudyConfig)
    weights = differential_mode_weights(cfg)
    alpha = weights.alpha
    beta = weights.beta
    return [
        alpha beta 0.0 0.0 0.0
        1.0 -1.0 0.0 0.0 0.0
        0.0 0.0 1.0 0.0 0.0
        0.0 0.0 0.0 1.0 0.0
        0.0 0.0 0.0 0.0 1.0
    ]
end

function apply_coordinate_transformation(y_cube, transform_matrix)
    _, _, n_freq = size(y_cube)
    transformed = Array{ComplexF64}(undef, size(y_cube))
    a_inv = inv(Matrix{Float64}(transform_matrix))
    a_inv_t = transpose(a_inv)
    for k in 1:n_freq
        transformed[:, :, k] = a_inv_t * Matrix(@view y_cube[:, :, k]) * a_inv
    end
    return transformed
end

function kron_reduce_y_cube(y_cube; keep_ports, drop_ports)
    keep = collect(keep_ports)
    drop = collect(drop_ports)
    _, _, n_freq = size(y_cube)
    reduced = Array{ComplexF64}(undef, length(keep), length(keep), n_freq)
    for k in 1:n_freq
        yk = Matrix(@view y_cube[:, :, k])
        y_kk = yk[keep, keep]
        if isempty(drop)
            reduced[:, :, k] = y_kk
            continue
        end
        y_kd = yk[keep, drop]
        y_dd = yk[drop, drop]
        y_dk = yk[drop, keep]
        reduced[:, :, k] = y_kk - y_kd * (y_dd \ y_dk)
    end
    return reduced
end

function differential_mode_input_admittance(y_cube, cfg::StudyConfig)
    y_ptc = apply_port_termination_compensation(
        y_cube;
        resistance_ohm_by_port=Dict(
            1 => cfg.qubit_port_res_ohm,
            2 => cfg.qubit_port_res_ohm,
        ),
    )
    transform_matrix = build_qubit_modal_transform(cfg)
    y_modal = apply_coordinate_transformation(y_ptc, transform_matrix)
    y_dm_only = kron_reduce_y_cube(y_modal; keep_ports=(2,), drop_ports=(1, 3, 4, 5))
    return (
        Yin_dm=vec(y_dm_only[1, 1, :]),
        Y_ptc=y_ptc,
        Y_modal=y_modal,
        Y_dm_only=y_dm_only,
        coordinate_transform=transform_matrix,
    )
end

function extract_resonance_from_yin(freqs_ghz, yin_dm)
    imag_y = imag.(yin_dm)
    real_y = real.(yin_dm)
    crossing_pairs = Tuple{Int,Int}[]

    for k in 1:(length(freqs_ghz)-1)
        if imag_y[k] == 0
            return (frequency_ghz=freqs_ghz[k], re_y=real_y[k], crossed=true, idx=k)
        end
        if imag_y[k] * imag_y[k+1] < 0
            push!(crossing_pairs, (k, k + 1))
        end
    end

    if !isempty(crossing_pairs)
        scores = [abs(imag_y[i]) + abs(imag_y[j]) for (i, j) in crossing_pairs]
        k1, k2 = crossing_pairs[argmin(scores)]
        f1, f2 = freqs_ghz[k1], freqs_ghz[k2]
        im1, im2 = imag_y[k1], imag_y[k2]
        re1, re2 = real_y[k1], real_y[k2]
        t = -im1 / (im2 - im1)
        return (
            frequency_ghz=f1 + t * (f2 - f1),
            re_y=re1 + t * (re2 - re1),
            crossed=true,
            idx=k1,
        )
    end

    idx = argmin(abs.(imag_y))
    return (
        frequency_ghz=freqs_ghz[idx],
        re_y=real_y[idx],
        crossed=false,
        idx=idx,
    )
end

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

    return (
        solution=solution,
        netlists=netlists,
    )
end

function simulate_case(cfg::StudyConfig; label::AbstractString)
    response = solve_linear_response(cfg; returnZ=true)
    solution = response.solution
    freqs_ghz = solution.linearized.w ./ (2π .* GHz)
    y_cube_raw = z_to_y_cube(solution)
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
    solution = response.solution
    freqs_ghz = solution.linearized.w ./ (2π .* GHz)
    s21 = solution.linearized.S(
        outputmode=(0,),
        outputport=output_port,
        inputmode=(0,),
        inputport=input_port,
        freqindex=:,
    )
    s11 = solution.linearized.S(
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
    progress_name::AbstractString="",
    progress_parentid=ROOT_PROGRESS_PARENT,
)
    rows = NamedTuple[]
    total_points = length(lq_values_h)

    function solve_all_lq_points(progress_id=nothing)
        for (point_index, lq_h) in enumerate(lq_values_h)
            cfg = updated_config(base_cfg; l_q_h=lq_h)
            result = simulate_case(cfg; label="$(label_prefix)_$(lq_h / nH) nH")
            fq_ghz = result.crossed ? result.fq_ghz : NaN
            g_resonance_s = result.crossed ? result.G_resonance_s : NaN
            push!(
                rows,
                (
                    lq_nh=lq_h / nH,
                    fq_ghz=fq_ghz,
                    g_resonance_s=g_resonance_s,
                    crossed=result.crossed,
                    fallback_fq_ghz=result.fq_ghz,
                    fallback_g_resonance_s=result.G_resonance_s,
                ),
            )
            if !isempty(progress_name)
                update_progress!(
                    progress_id,
                    point_index,
                    total_points;
                    name=@sprintf("Lq = %.3f nH", lq_h / nH),
                    parentid=progress_parentid,
                )
            end
        end
        return nothing
    end

    if isempty(progress_name)
        solve_all_lq_points()
    else
        with_progress_scope(progress_name; parentid=progress_parentid) do progress_id
            solve_all_lq_points(progress_id)
        end
    end

    return DataFrame(rows)
end

function select_nearest_frequency(df::DataFrame, target_f_ghz)
    valid_mask = df.crossed .& .!isnan.(df.fq_ghz)
    any(valid_mask) || error("No Im(Ydm)=0 crossing was found in the requested Lq sweep.")
    valid_df = df[valid_mask, :]
    idx = argmin(abs.(valid_df.fq_ghz .- target_f_ghz))
    return valid_df[idx, :]
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
