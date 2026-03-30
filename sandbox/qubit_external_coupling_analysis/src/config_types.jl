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
