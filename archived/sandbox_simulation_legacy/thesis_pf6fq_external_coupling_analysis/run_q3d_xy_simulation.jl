using CSV
using DataFrames
using JosephsonCircuits
using LinearAlgebra
using Printf
using Symbolics

const GHz = 1e9
const nH = 1e-9
const fF = 1e-15
const pF = 1e-12

const STUDY_DIR = @__DIR__
const REPO_ROOT = normpath(joinpath(STUDY_DIR, "..", ".."))
const RAW_LAYOUT_DIR = joinpath(REPO_ROOT, "data", "raw", "layout_simulation", "PF6FQ")
const RAW_OUTPUT_DIR = joinpath(STUDY_DIR, "outputs", "raw")
const TABLE_OUTPUT_DIR = joinpath(STUDY_DIR, "outputs", "tables")

const NODE_ORDER = ("Ground", "Pad1", "Pad2", "XY_Line")

function parse_q3d_unit(text)
    unit_match = match(r"%C Units:([^,\r\n]+)", text)
    isnothing(unit_match) && error("Missing Q3D C Units header.")
    unit = strip(unit_match.captures[1])
    if lowercase(unit) == "ff"
        return (unit=unit, scale=fF)
    elseif lowercase(unit) == "pf"
        return (unit=unit, scale=pF)
    end
    error("Unsupported Q3D capacitance unit: $(unit)")
end

function parse_q3d_cap_matrix(path)
    text = read(path, String)
    unit = parse_q3d_unit(text)
    matrix_match = match(r"capMatrix\s*=\s*\[((?:.|\n)*?)\];", text)
    isnothing(matrix_match) && error("Missing capMatrix block in $(path)")

    rows = Vector{Vector{Float64}}()
    for raw_line in split(matrix_match.captures[1], '\n')
        line = strip(replace(raw_line, ";" => ""))
        isempty(line) && continue
        push!(rows, [parse(Float64, strip(value)) for value in split(line, ",") if !isempty(strip(value))])
    end

    matrix = reduce(vcat, transpose.(rows)) .* unit.scale
    size(matrix) == (4, 4) || error("Expected 4x4 capMatrix in $(path), got $(size(matrix))")
    isapprox(matrix, transpose(matrix); rtol=1e-8, atol=1e-21) ||
        error("capMatrix is not symmetric within tolerance: $(path)")
    return (matrix_f=matrix, source_unit=unit.unit)
end

function q3d_path_for_qubit(qubit)
    return joinpath(RAW_LAYOUT_DIR, qubit, "$(qubit)_XY_Q3D_C_Matrix.m")
end

function capacitance_components(qubit)
    path = q3d_path_for_qubit(qubit)
    parsed = parse_q3d_cap_matrix(path)
    c = parsed.matrix_f

    c_g1 = -c[2, 1]
    c_g2 = -c[3, 1]
    c_q = -c[2, 3]
    c_xy1 = -c[2, 4]
    c_xy2 = -c[3, 4]
    c_xy_ground = -c[4, 1]

    c_g1 > 0 || error("Non-positive C_g1 for $(qubit)")
    c_g2 > 0 || error("Non-positive C_g2 for $(qubit)")
    c_q > 0 || error("Non-positive C_q for $(qubit)")
    c_xy1 > 0 || error("Non-positive C_xy1 for $(qubit)")
    c_xy2 > 0 || error("Non-positive C_xy2 for $(qubit)")

    w1 = c_g1 + c_xy1
    w2 = c_g2 + c_xy2
    alpha = w1 / (w1 + w2)
    beta = w2 / (w1 + w2)
    c_d_xy = (c_g1 * c_xy2 - c_g2 * c_xy1) / (w1 + w2)
    c_dd = c_q + (w1 * w2) / (w1 + w2)
    c_eff_q = c_q + (c_g1 * c_g2) / (c_g1 + c_g2) + (c_xy1 * c_xy2) / (c_xy1 + c_xy2)

    return (
        qubit=qubit,
        source_path=path,
        source_unit=parsed.source_unit,
        cap_matrix_f=parsed.matrix_f,
        c_g1_f=c_g1,
        c_g2_f=c_g2,
        c_q_f=c_q,
        c_xy1_f=c_xy1,
        c_xy2_f=c_xy2,
        c_xy_ground_f=c_xy_ground,
        alpha=alpha,
        beta=beta,
        c_d_xy_f=c_d_xy,
        c_dd_f=c_dd,
        c_eff_q_f=c_eff_q,
    )
end

function capacitance_summary_rows(qubits)
    return [
        (
            qubit=comp.qubit,
            source_unit=comp.source_unit,
            c_g1_ff=comp.c_g1_f / fF,
            c_g2_ff=comp.c_g2_f / fF,
            c_q_ff=comp.c_q_f / fF,
            c_xy1_ff=comp.c_xy1_f / fF,
            c_xy2_ff=comp.c_xy2_f / fF,
            c_xy_ground_ff=comp.c_xy_ground_f / fF,
            alpha=comp.alpha,
            beta=comp.beta,
            c_d_xy_ff=comp.c_d_xy_f / fF,
            c_dd_ff=comp.c_dd_f / fF,
            c_eff_q_ff=comp.c_eff_q_f / fF,
            source_path=relpath(comp.source_path, REPO_ROOT),
        ) for comp in capacitance_components.(qubits)
    ]
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
        compensated[port, port, :] .-= 1 / resistance_ohm
    end
    return compensated
end

function build_modal_transform(comp)
    return [
        comp.alpha comp.beta 0.0
        1.0 -1.0 0.0
        0.0 0.0 1.0
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
        y_kd = yk[keep, drop]
        y_dd = yk[drop, drop]
        y_dk = yk[drop, keep]
        reduced[:, :, k] = y_kk - y_kd * (y_dd \ y_dk)
    end
    return reduced
end

function differential_mode_input_admittance(y_cube, comp)
    y_modal = apply_coordinate_transformation(y_cube, build_modal_transform(comp))
    y_dm_only = kron_reduce_y_cube(y_modal; keep_ports=(2,), drop_ports=(1, 3))
    return vec(y_dm_only[1, 1, :])
end

function extract_resonance_from_yin(freqs_ghz, yin_dm)
    imag_y = imag.(yin_dm)
    real_y = real.(yin_dm)
    crossing_pairs = Tuple{Int,Int}[]

    for k in 1:(length(freqs_ghz) - 1)
        if imag_y[k] == 0
            return (
                frequency_ghz=freqs_ghz[k],
                re_y=real_y[k],
                crossed=true,
                fallback=false,
                idx=k,
                selected_crossing_index=1,
                bracket_f0_ghz=freqs_ghz[k],
                bracket_f1_ghz=freqs_ghz[k],
                bracket_im_y0=imag_y[k],
                bracket_im_y1=imag_y[k],
                slope_im_y_per_ghz=NaN,
                slope_sign="zero_sample",
            )
        end
        if imag_y[k] * imag_y[k + 1] < 0
            push!(crossing_pairs, (k, k + 1))
        end
    end

    if !isempty(crossing_pairs)
        scores = [abs(imag_y[i]) + abs(imag_y[j]) for (i, j) in crossing_pairs]
        selected_index = argmin(scores)
        k1, k2 = crossing_pairs[selected_index]
        f1, f2 = freqs_ghz[k1], freqs_ghz[k2]
        im1, im2 = imag_y[k1], imag_y[k2]
        re1, re2 = real_y[k1], real_y[k2]
        t = -im1 / (im2 - im1)
        slope = (im2 - im1) / (f2 - f1)
        return (
            frequency_ghz=f1 + t * (f2 - f1),
            re_y=re1 + t * (re2 - re1),
            crossed=true,
            fallback=false,
            idx=k1,
            selected_crossing_index=selected_index,
            bracket_f0_ghz=f1,
            bracket_f1_ghz=f2,
            bracket_im_y0=im1,
            bracket_im_y1=im2,
            slope_im_y_per_ghz=slope,
            slope_sign=slope > 0 ? "positive" : "negative",
        )
    end

    idx = argmin(abs.(imag_y))
    return (
        frequency_ghz=freqs_ghz[idx],
        re_y=real_y[idx],
        crossed=false,
        fallback=true,
        idx=idx,
        selected_crossing_index=0,
        bracket_f0_ghz=NaN,
        bracket_f1_ghz=NaN,
        bracket_im_y0=NaN,
        bracket_im_y1=NaN,
        slope_im_y_per_ghz=NaN,
        slope_sign="fallback_min_abs_im",
    )
end

@variables R50 C_g1 C_g2 C_q C_xy1 C_xy2 L_q

function build_floating_xy_netlist()
    circuit = Tuple{String,String,String,Num}[]
    push!(circuit, ("C_g1", "1", "0", C_g1))
    push!(circuit, ("C_g2", "2", "0", C_g2))
    push!(circuit, ("C_q", "1", "2", C_q))
    push!(circuit, ("L_q", "1", "2", L_q))
    push!(circuit, ("C_xy1", "1", "3", C_xy1))
    push!(circuit, ("C_xy2", "2", "3", C_xy2))
    push!(circuit, ("P1", "1", "0", 1))
    push!(circuit, ("R_P1", "1", "0", R50))
    push!(circuit, ("P2", "2", "0", 2))
    push!(circuit, ("R_P2", "2", "0", R50))
    push!(circuit, ("P3", "3", "0", 3))
    push!(circuit, ("R_XY", "3", "0", R50))
    return circuit
end

function build_trace_rows(comp, lq_nh, freqs_ghz, yin_dm)
    return [
        (
            qubit=comp.qubit,
            l_jun_nh=lq_nh,
            frequency_ghz=freq_ghz,
            re_y_eff_s=real(y_value),
            im_y_eff_s=imag(y_value),
        ) for (freq_ghz, y_value) in zip(freqs_ghz, yin_dm)
    ]
end

function simulate_case(comp, lq_nh; sweep_start_ghz, sweep_stop_ghz, sweep_step_ghz)
    circuitdefs = Dict(
        R50 => 50.0,
        C_g1 => comp.c_g1_f,
        C_g2 => comp.c_g2_f,
        C_q => comp.c_q_f,
        C_xy1 => comp.c_xy1_f,
        C_xy2 => comp.c_xy2_f,
        L_q => lq_nh * nH,
    )

    ws = 2π .* (sweep_start_ghz:sweep_step_ghz:sweep_stop_ghz) .* GHz
    wp = (2π * 8.001 * GHz,)
    sources = [(mode=(1,), port=1, current=0.0)]

    solution = hbsolve(
        ws,
        wp,
        sources,
        (10,),
        (20,),
        build_floating_xy_netlist(),
        circuitdefs;
        returnZ=true,
        sorting=:name,
    )

    freqs_ghz = solution.linearized.w ./ (2π .* GHz)
    y_cube_raw = z_to_y_cube(solution)
    y_cube_ptc = apply_port_termination_compensation(
        y_cube_raw;
        resistance_ohm_by_port=Dict(1 => 50.0, 2 => 50.0),
    )
    yin_dm = differential_mode_input_admittance(y_cube_ptc, comp)
    resonance = extract_resonance_from_yin(freqs_ghz, yin_dm)
    gamma_xy_per_s = resonance.re_y / comp.c_eff_q_f
    t1_xy_s = gamma_xy_per_s > 0 ? 1 / gamma_xy_per_s : NaN

    return (
        summary=(
            qubit=comp.qubit,
            l_jun_nh=lq_nh,
            frequency_ghz=resonance.frequency_ghz,
            re_y_eff_s=resonance.re_y,
            c_eff_q_ff=comp.c_eff_q_f / fF,
            gamma_xy_per_s=gamma_xy_per_s,
            t1_xy_s=t1_xy_s,
            t1_xy_us=t1_xy_s * 1e6,
            crossed=resonance.crossed,
            fallback=resonance.fallback,
            selected_index=resonance.idx,
            selected_crossing_index=resonance.selected_crossing_index,
            bracket_f0_ghz=resonance.bracket_f0_ghz,
            bracket_f1_ghz=resonance.bracket_f1_ghz,
            bracket_im_y0=resonance.bracket_im_y0,
            bracket_im_y1=resonance.bracket_im_y1,
            slope_im_y_per_ghz=resonance.slope_im_y_per_ghz,
            slope_sign=resonance.slope_sign,
            sweep_start_ghz=sweep_start_ghz,
            sweep_stop_ghz=sweep_stop_ghz,
            sweep_step_ghz=sweep_step_ghz,
        ),
        trace_rows=build_trace_rows(comp, lq_nh, freqs_ghz, yin_dm),
    )
end

function main()
    smoke = "--smoke" in ARGS
    qubits = smoke ? ["Q0"] : ["Q0", "Q1", "Q2"]
    lq_values_nh = smoke ? [24.0] : [5.0, 10.0, 15.0, 18.0, 20.0, 22.0, 24.0, 26.0, 28.0]
    sweep_start_ghz = smoke ? 3.0 : 1.0
    sweep_stop_ghz = smoke ? 5.5 : 10.0
    sweep_step_ghz = smoke ? 0.01 : 0.002

    mkpath(RAW_OUTPUT_DIR)
    mkpath(TABLE_OUTPUT_DIR)

    cap_df = DataFrame(capacitance_summary_rows(["Q0", "Q1", "Q2"]))
    cap_path = joinpath(RAW_OUTPUT_DIR, "q3d_capacitance_parameters.csv")
    cap_table_path = joinpath(TABLE_OUTPUT_DIR, "thesis_q3d_capacitance_summary.csv")
    CSV.write(cap_path, cap_df)
    CSV.write(cap_table_path, cap_df)
    println("Wrote $(relpath(cap_path, REPO_ROOT))")
    println("Wrote $(relpath(cap_table_path, REPO_ROOT))")

    rows = NamedTuple[]
    trace_rows = NamedTuple[]
    for qubit in qubits
        comp = capacitance_components(qubit)
        for lq_nh in lq_values_nh
            @printf("Simulating %s L_jun=%.1f nH\n", qubit, lq_nh)
            case_result = simulate_case(
                comp,
                lq_nh;
                sweep_start_ghz=sweep_start_ghz,
                sweep_stop_ghz=sweep_stop_ghz,
                sweep_step_ghz=sweep_step_ghz,
            )
            push!(rows, case_result.summary)
            append!(trace_rows, case_result.trace_rows)
        end
    end

    result_df = DataFrame(rows)
    result_path = joinpath(RAW_OUTPUT_DIR, "q3d_jc_xy_reduced_observables.csv")
    CSV.write(result_path, result_df)
    println("Wrote $(relpath(result_path, REPO_ROOT))")

    trace_df = DataFrame(trace_rows)
    trace_path = joinpath(RAW_OUTPUT_DIR, "q3d_jc_xy_reduced_y_traces.csv")
    CSV.write(trace_path, trace_df)
    println("Wrote $(relpath(trace_path, REPO_ROOT))")
end

main()
