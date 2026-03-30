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
    y_modal = apply_coordinate_transformation(y_ptc, build_qubit_modal_transform(cfg))
    y_dm_only = kron_reduce_y_cube(y_modal; keep_ports=(2,), drop_ports=(1, 3, 4, 5))
    return (
        Yin_dm=vec(y_dm_only[1, 1, :]),
        Y_ptc=y_ptc,
        Y_modal=y_modal,
        Y_dm_only=y_dm_only,
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
