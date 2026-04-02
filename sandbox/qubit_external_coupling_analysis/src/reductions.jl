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
        compensated[port, port, :] .-= 1 / resistance_ohm
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
    return [
        weights.alpha weights.beta 0.0 0.0 0.0
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

function kron_reduce_y_cube(y_cube; keep_ports, drop_ports, singular_fallback::Symbol=:error)
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
        schur_rhs = try
            y_dd \ y_dk
        catch err
            if singular_fallback == :pinv && err isa LinearAlgebra.SingularException
                pinv(y_dd) * y_dk
            else
                rethrow()
            end
        end
        reduced[:, :, k] = y_kk - y_kd * schur_rhs
    end
    return reduced
end

function qubit_port_termination_resistances(cfg::StudyConfig)
    return Dict(
        1 => cfg.qubit_port_res_ohm,
        2 => cfg.qubit_port_res_ohm,
    )
end

function all_port_termination_resistances(cfg::StudyConfig)
    return Dict(
        1 => cfg.qubit_port_res_ohm,
        2 => cfg.qubit_port_res_ohm,
        3 => cfg.xy_port_res_ohm,
        4 => cfg.readout_port_res_ohm,
        5 => cfg.readout_port_res_ohm,
    )
end

function port_termination_resistances(cfg::StudyConfig; ptc_mode::Symbol=:qubit_only)
    if ptc_mode == :qubit_only
        return qubit_port_termination_resistances(cfg)
    elseif ptc_mode == :all_ports
        return all_port_termination_resistances(cfg)
    end
    error("Unsupported ptc_mode=$(ptc_mode). Expected :qubit_only or :all_ports.")
end

function differential_mode_input_admittance(y_cube, cfg::StudyConfig; ptc_mode::Symbol=:qubit_only)
    y_ptc = apply_port_termination_compensation(
        y_cube;
        resistance_ohm_by_port=port_termination_resistances(cfg; ptc_mode=ptc_mode),
    )
    y_modal = apply_coordinate_transformation(y_ptc, build_qubit_modal_transform(cfg))
    singular_fallback = ptc_mode == :all_ports ? :pinv : :error
    y_dm_only = kron_reduce_y_cube(
        y_modal;
        keep_ports=(2,),
        drop_ports=(1, 3, 4, 5),
        singular_fallback=singular_fallback,
    )
    return (
        Yin_dm=vec(y_dm_only[1, 1, :]),
        Y_ptc=y_ptc,
        Y_modal=y_modal,
        Y_dm_only=y_dm_only,
        ptc_mode=ptc_mode,
        singular_fallback=singular_fallback,
    )
end

function fit_effective_capacitance_trace(freqs_ghz, yin_dm; half_window_points::Integer=4)
    half_window_points >= 1 || error("half_window_points must be at least 1.")
    length(freqs_ghz) == length(yin_dm) || error("freqs_ghz and yin_dm must have the same length.")

    omega_rad_per_s = 2π .* freqs_ghz .* GHz
    imag_y_s = imag.(yin_dm)
    c_eff_direct_f = imag_y_s ./ omega_rad_per_s

    n_points = length(freqs_ghz)
    c_eff_fit_f = fill(NaN, n_points)
    fit_intercept_s = fill(NaN, n_points)
    fit_rmse_s = fill(NaN, n_points)
    fit_point_count = fill(0, n_points)
    fit_window_start_idx = fill(0, n_points)
    fit_window_stop_idx = fill(0, n_points)

    for idx in eachindex(freqs_ghz)
        start_idx = max(firstindex(freqs_ghz), idx - half_window_points)
        stop_idx = min(lastindex(freqs_ghz), idx + half_window_points)
        omega_window = @view omega_rad_per_s[start_idx:stop_idx]
        imag_window = @view imag_y_s[start_idx:stop_idx]
        n_window = length(omega_window)

        if n_window < 2
            continue
        end

        omega_mean = sum(omega_window) / n_window
        imag_mean = sum(imag_window) / n_window
        centered_omega = omega_window .- omega_mean
        centered_imag = imag_window .- imag_mean
        denom = sum(abs2, centered_omega)

        if denom <= eps(Float64)
            continue
        end

        slope_s_per_rad = sum(centered_omega .* centered_imag) / denom
        intercept_s = imag_mean - (slope_s_per_rad * omega_mean)
        fitted_window = intercept_s .+ (slope_s_per_rad .* omega_window)
        residuals = imag_window .- fitted_window

        c_eff_fit_f[idx] = 0.5 * slope_s_per_rad
        fit_intercept_s[idx] = intercept_s
        fit_rmse_s[idx] = sqrt(sum(abs2, residuals) / n_window)
        fit_point_count[idx] = n_window
        fit_window_start_idx[idx] = start_idx
        fit_window_stop_idx[idx] = stop_idx
    end

    return (
        omega_rad_per_s=omega_rad_per_s,
        imag_y_s=imag_y_s,
        c_eff_direct_f=c_eff_direct_f,
        c_eff_fit_f=c_eff_fit_f,
        fit_intercept_s=fit_intercept_s,
        fit_rmse_s=fit_rmse_s,
        fit_point_count=fit_point_count,
        fit_window_start_idx=fit_window_start_idx,
        fit_window_stop_idx=fit_window_stop_idx,
        fit_half_window_points=half_window_points,
    )
end

function extract_resonance_from_yin(freqs_ghz, yin_dm)
    imag_y = imag.(yin_dm)
    real_y = real.(yin_dm)
    crossing_pairs = Tuple{Int,Int}[]

    for k in 1:(length(freqs_ghz) - 1)
        if imag_y[k] == 0
            return (frequency_ghz=freqs_ghz[k], re_y=real_y[k], crossed=true, idx=k)
        end
        if imag_y[k] * imag_y[k + 1] < 0
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
