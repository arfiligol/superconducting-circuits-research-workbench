using LinearAlgebra
using JosephsonCircuits
using PlotlyJS

include(joinpath(@__DIR__, "Reusable Component", "ReusableComponents.jl"))
using .ReusableComponents

# =============================================================================
# 1. Basic Setup
# =============================================================================

const nH = 1e-9
const GHz = 1e9

# Reusable distributed builders live under:
#   sandbox/legacy_circuit_model_analysis/Reusable Component/
# Other sandbox circuits can `include(...)` the same module and reuse:
# - add_quarter_wave_resonator!
# - add_half_wave_purcell_filter!
# - add_readout_line!

# =============================================================================
# 2. Circuit Symbols
# =============================================================================

@variables R50
@variables C_01 C_02 C_12 L_12
@variables C_13 C_23
@variables C_r L_r
@variables L_rp L_pr K_rp_pr
@variables C_p1 C_p2
@variables L_tl_top L_tl_bot

# =============================================================================
# 3. Plot Helpers
# =============================================================================
# 取代原本 utils.jl 裡的 ili_plot

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

# =============================================================================
# 4. Manual Component Values
# =============================================================================

component_values = Dict(
    C_01 => 45.0e-15,
    C_02 => 46.0e-15,
    C_12 => 28.0e-15,
    C_13 => 2.5e-15,
    C_23 => 2.3e-15,
)

# =============================================================================
# 5. Build Circuit Definitions
# =============================================================================

base_circuitdefs = merge(
    component_values,
    Dict(
        R50 => 50.0,
        L_12 => 12.34e-9,

        # TODO: 換成你已驗證過的 readout resonator / RTL 參數
        C_r => 100.0e-15,
        L_r => 8.0e-9,
        L_rp => 0.2e-9,
        L_pr => 0.2e-9,
        K_rp_pr => 0.02,
        C_p1 => 10.0e-15,
        C_p2 => 10.0e-15,
        L_tl_top => 0.2e-9,
        L_tl_bot => 0.2e-9,
    ),
)

# =============================================================================
# 6. Build Circuits
# =============================================================================

function build_floating_qubit_with_readout_circuit(; include_qubit_inductor::Bool=true)
    circuit = Tuple{String,String,String,Num}[]

    # ---------------------------
    # Qubit body
    # ---------------------------
    push!(circuit, ("C_01", "1", "0", C_01))
    push!(circuit, ("C_02", "2", "0", C_02))
    push!(circuit, ("C_12", "1", "2", C_12))

    if include_qubit_inductor
        push!(circuit, ("L_12", "1", "2", L_12))
    end

    # ---------------------------
    # Coupling to readout resonator
    # ---------------------------
    push!(circuit, ("C_13", "1", "3", C_13))
    push!(circuit, ("C_23", "2", "3", C_23))

    # ---------------------------
    # Readout resonator
    # ---------------------------
    push!(circuit, ("C_r", "3", "0", C_r))
    push!(circuit, ("L_r", "3", "0", L_r))
    push!(circuit, ("L_rp", "3", "0", L_rp))

    # ---------------------------
    # Pickup coil + capacitive coupling to the two readout-line branches
    # ---------------------------
    push!(circuit, ("L_pr", "4", "5", L_pr))
    push!(circuit, ("C_p1", "4", "6", C_p1))
    push!(circuit, ("C_p2", "5", "8", C_p2))

    # ---------------------------
    # Simplified transmission-line branches
    # ---------------------------
    # 先用 lumped series inductors 當作 TL placeholder，保留圖上的拓樸與兩個外部 50 Ohm 環境。
    push!(circuit, ("L_tl_top", "6", "7", L_tl_top))
    push!(circuit, ("L_tl_bot", "8", "9", L_tl_bot))

    # ---------------------------
    # Mutual inductive coupling
    # ---------------------------
    push!(circuit, ("K_rp_pr", "L_rp", "L_pr", K_rp_pr))

    # ---------------------------
    # Ports
    # ---------------------------
    # P1 / P2: qubit artificial measurement ports
    push!(circuit, ("P1", "1", "0", 1))
    push!(circuit, ("R_P1", "1", "0", R50))

    push!(circuit, ("P2", "2", "0", 2))
    push!(circuit, ("R_P2", "2", "0", R50))

    # P3 / P4: two physical readout-line environments
    push!(circuit, ("P3", "7", "0", 3))
    push!(circuit, ("R_P3", "7", "0", R50))

    push!(circuit, ("P4", "9", "0", 4))
    push!(circuit, ("R_P4", "9", "0", R50))

    return circuit
end

full_circuit = build_floating_qubit_with_readout_circuit(include_qubit_inductor=true)

# =============================================================================
# 7. Solver
# =============================================================================

function solve_circuit(
    circuit,
    circuitdefs;
    f_start::Real=1.0,
    f_stop::Real=10.0,
    f_step::Real=0.001,
    solver::Function=hbsolve,
)
    ws = 2π .* (f_start:f_step:f_stop) .* GHz
    wp = (2π * 8.001 * GHz,)
    Ip = 0.0
    sources = [(mode=(1,), port=1, current=Ip)]
    Npumpharmonics = (20,)
    Nmodulationharmonics = (10,)

    return solver(
        ws,
        wp,
        sources,
        Nmodulationharmonics,
        Npumpharmonics,
        circuit,
        circuitdefs;
        returnZ=true,
    )
end

# =============================================================================
# 8. Z(ω) -> Y(ω)
# =============================================================================

function z_to_y_cube(solution)
    z_cube = Array(solution.linearized.Z[1, :, 1, :, :])
    _, _, n_freq = size(z_cube)
    y_cube = similar(z_cube)

    for k in 1:n_freq
        y_cube[:, :, k] = inv(Matrix(@view z_cube[:, :, k]))
    end

    return y_cube
end

# =============================================================================
# 9. Port Termination Compensation (PTC)
# =============================================================================

function apply_port_termination_compensation(y_cube; resistance_ohm_by_port::Dict{Int,Float64})
    compensated = copy(y_cube)
    n_ports, _, n_freq = size(compensated)

    for (port, resistance_ohm) in resistance_ohm_by_port
        if port < 1 || port > n_ports
            error("Port $port out of range.")
        end
        if resistance_ohm <= 0
            error("Resistance must be positive.")
        end

        shunt_admittance = 1 / resistance_ohm
        for k in 1:n_freq
            compensated[port, port, k] -= shunt_admittance
        end
    end

    return compensated
end

# =============================================================================
# 10. Coordinate Transformation
# =============================================================================
# port basis: (P1, P2, ReadoutTop, ReadoutBottom)
# modal basis: (CM, DM, ReadoutTop, ReadoutBottom)

function differential_mode_weights(component_values)
    w_1 = component_values[C_01] + component_values[C_13]
    w_2 = component_values[C_02] + component_values[C_23]
    total = w_1 + w_2

    return (
        w_1=w_1,
        w_2=w_2,
        alpha=w_1 / total,
        beta=w_2 / total,
    )
end

function build_cm_dm_coordinate_transform(component_values)
    weights = differential_mode_weights(component_values)
    alpha = weights.alpha
    beta = weights.beta

    # Vm = A * Vp
    return [
        alpha beta 0.0 0.0
        1.0 -1.0 0.0 0.0
        0.0 0.0 1.0 0.0
        0.0 0.0 0.0 1.0
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

# =============================================================================
# 11. Kron Reduction
# =============================================================================

function kron_reduce_y_cube(y_cube; keep_ports, drop_ports)
    n_ports, _, n_freq = size(y_cube)
    keep = collect(keep_ports)
    drop = collect(drop_ports)

    isempty(keep) && error("keep_ports must not be empty.")
    length(union(keep, drop)) == length(keep) + length(drop) ||
        error("keep_ports and drop_ports must be disjoint.")
    sort(union(keep, drop)) == collect(1:n_ports) ||
        error("keep_ports and drop_ports must partition all ports.")

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

# =============================================================================
# 12. Differential-Mode Input Admittance
# =============================================================================
# raw Y
#   -> PTC
#   -> CT to (cm, dm, p3, p4)
#   -> Kron reduce away (cm, p3, p4)
#   -> keep dm only

function differential_mode_input_admittance(y_cube, component_values)
    transform_matrix = build_cm_dm_coordinate_transform(component_values)
    y_modal = apply_coordinate_transformation(y_cube, transform_matrix)

    y_dm_only = kron_reduce_y_cube(
        y_modal;
        keep_ports=(2,),
        drop_ports=(1, 3, 4),
    )

    yin_dm = vec(y_dm_only[1, 1, :])

    return (
        Yin_dm=yin_dm,
        Y_modal=y_modal,
        Y_dm_only=y_dm_only,
        coordinate_transform=transform_matrix,
    )
end

# =============================================================================
# 13. Resonance Extraction
# =============================================================================

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

# =============================================================================
# 15. Run Full Simulation
# =============================================================================

full_solution = solve_circuit(
    full_circuit,
    base_circuitdefs;
    f_start=1.0,
    f_stop=10.0,
    f_step=0.001,
)

freqs = full_solution.linearized.w ./ (2π .* GHz)
y_cube_raw = z_to_y_cube(full_solution)

# 只扣掉 qubit artificial measurement ports
y_cube_ptc = apply_port_termination_compensation(
    y_cube_raw;
    resistance_ohm_by_port=Dict(
        1 => 50.0,
        2 => 50.0,
    ),
)

dm_result = differential_mode_input_admittance(y_cube_ptc, component_values)
yin_dm = dm_result.Yin_dm
resonance = extract_resonance_from_yin(freqs, yin_dm)

# =============================================================================
# 16. Compute Physical Quantities
# =============================================================================

idx = resonance.idx
qubit_frequency_ghz = resonance.frequency_ghz
G0 = resonance.re_y
Ceff0 =
    component_values[C_12] +
    (component_values[C_01] * component_values[C_02]) / (component_values[C_01] + component_values[C_02]) +
    (component_values[C_13] * component_values[C_23]) / (component_values[C_13] + component_values[C_23])

if G0 <= 0
    @warn "Re(Yin_dm) <= 0 at f ≈ $qubit_frequency_ghz GHz -> T1 is not finite or model should be checked."
else
    T1 = Ceff0 / G0
    ω0 = 2π * qubit_frequency_ghz * GHz
    Q = ω0 * Ceff0 / G0

    println("====================================")
    println("Differential-Mode Readout-Induced Loss")
    println("====================================")
    println("Qubit frequency  : $(qubit_frequency_ghz) GHz")
    println("Ceff_dm          : $(Ceff0) F")
    println("Re(Yin_dm)       : $(G0) S")
    println("T1               : $(T1) s")
    println("Q                : $(Q)")
    println("Crossed zero     : $(resonance.crossed)")
end

# =============================================================================
# 17. Plots
# =============================================================================

yin_plot = build_plot(
    [
        scatter(
            mode="lines",
            x=freqs,
            y=imag.(yin_dm),
            name="Im(Yin_dm)",
        ),
        scatter(
            mode="lines",
            x=freqs,
            y=real.(yin_dm),
            name="Re(Yin_dm)",
        ),
    ],
    "Differential-Mode Input Admittance Seen by Qubit",
    "Frequency (GHz)",
    "Admittance (S)";
    legend_title="Legend",
)

display(yin_plot)
