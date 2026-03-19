using JosephsonCircuits
using PlotlyJS
using CSV
using DataFrames

include(joinpath(@__DIR__, "Reusable Component", "ReusableComponents.jl"))
using .ReusableComponents

# =============================================================================
# 1. Basic Setup
# =============================================================================

const GHz = 1e9
const mm = 1e-3
const fF = 1e-15

# =============================================================================
# 2. Plot Helper
# =============================================================================

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
# 3. Distributed-Line Specs
# =============================================================================
# 這支 sandbox 只測試：
#   readout line -> half-wave PF -> readout line
#
# 左右 readout line 固定 2.5 mm，只 sweep 中間 half-wave PF 的長度。
# 三段都用 distributed RLGC ladder。
# 這裡先用 lossless RLGC 當起點；若之後要加 conductor / dielectric loss，
# 只要把 r_per_m_ohm / g_per_m_s 改成非零即可。
# 下列 unit RLGC 來自你截圖中的 CPW calculator：
#   Ls = 10.6754 nH / inch
#   Cs = 4.27017 pF / inch
#   Rs = 0
#   Gs = 0
# 轉成 SI 後：
#   L' = 4.202913385827e-7 H / m
#   C' = 1.681169291339e-10 F / m

common_l_per_m = 4.202913385827e-7
common_c_per_m = 1.681169291339e-10
common_r_per_m = 0.0
common_g_per_m = 0.0

left_line_length_m = 2.5 * mm
right_line_length_m = 2.5 * mm
left_line_sections = 20
right_line_sections = 20
purcell_filter_sections = 48

# Two adjustable coupling capacitors around the half-wave PF.
C_pf_in = 12.0 * fF
C_pf_out = 12.0 * fF

# Sweep about 10 PF lengths around the current working point.
PF_LENGTH_SWEEP_M = collect(range(9.8 * mm, 10.7 * mm, length=10))

# =============================================================================
# 4. Circuit Builders
# =============================================================================

function make_rlgc_spec(length_m, n_sections)
    return RLGCSpec(
        length_m=length_m,
        n_sections=n_sections,
        l_per_m_h=common_l_per_m,
        c_per_m_f=common_c_per_m,
        r_per_m_ohm=common_r_per_m,
        g_per_m_s=common_g_per_m,
    )
end

function build_purcell_filter_only_circuit(pf_length_m)
    circuit = Tuple{String,String,String,Any}[]

    left_pf_bus = "pf_bus_left"
    right_pf_bus = "pf_bus_right"

    add_readout_line!(
        circuit;
        prefix="left_tl",
        left_node="1",
        right_node=left_pf_bus,
        line_spec=make_rlgc_spec(left_line_length_m, left_line_sections),
        left_port_number=1,
    )

    add_half_wave_purcell_filter!(
        circuit;
        prefix="pf",
        left_external_node=left_pf_bus,
        right_external_node=right_pf_bus,
        left_coupling_cap_f=C_pf_in,
        right_coupling_cap_f=C_pf_out,
        line_spec=make_rlgc_spec(pf_length_m, purcell_filter_sections),
    )

    add_readout_line!(
        circuit;
        prefix="right_tl",
        left_node=right_pf_bus,
        right_node="2",
        line_spec=make_rlgc_spec(right_line_length_m, right_line_sections),
        right_port_number=2,
    )

    return circuit
end

# =============================================================================
# 5. Solver Setup
# =============================================================================

ws = 2π .* (5.2:0.0005:6.2) .* GHz
wp = (2π * 8.001 * GHz,)
Ip = 0.0
sources = [(mode=(1,), port=1, current=Ip)]
Npumpharmonics = (1,)
Nmodulationharmonics = (1,)

function solve_purcell_filter_only(pf_length_m)
    circuit = build_purcell_filter_only_circuit(pf_length_m)
    circuitdefs = Dict{Num,Float64}()

    solution = hbsolve(
        ws,
        wp,
        sources,
        Nmodulationharmonics,
        Npumpharmonics,
        circuit,
        circuitdefs;
        returnS=true,
        # The reusable ladder builders generate descriptive string node labels
        # like `pf_bus_left` and `left_tl_n1`, so use name-based sorting.
        sorting=:name,
    )

    freqs = solution.linearized.w ./ (2π .* GHz)
    s21 = solution.linearized.S(
        outputmode=(0,),
        outputport=2,
        inputmode=(0,),
        inputport=1,
        freqindex=:,
    )

    s21_mag = abs.(s21)
    peak_idx = argmax(s21_mag)

    return (
        pf_length_m=pf_length_m,
        pf_length_mm=pf_length_m / mm,
        freqs=freqs,
        S21=s21,
        S21_mag=s21_mag,
        peak_frequency_GHz=freqs[peak_idx],
        peak_S21_mag=s21_mag[peak_idx],
    )
end

# =============================================================================
# 6. Run Sweep
# =============================================================================

@time pf_sweep_results = [solve_purcell_filter_only(length_m) for length_m in PF_LENGTH_SWEEP_M]

# =============================================================================
# 7. Save Sweep Data
# =============================================================================

purcell_filter_length_sweep_df = vcat([
    DataFrame(
        pf_length_mm=fill(result.pf_length_mm, length(result.freqs)),
        frequency_GHz=result.freqs,
        S21_real=real.(result.S21),
        S21_imag=imag.(result.S21),
        S21_mag=result.S21_mag,
    ) for result in pf_sweep_results
]...)

purcell_filter_length_sweep_summary_df = DataFrame(
    pf_length_mm=[result.pf_length_mm for result in pf_sweep_results],
    peak_frequency_GHz=[result.peak_frequency_GHz for result in pf_sweep_results],
    peak_S21_mag=[result.peak_S21_mag for result in pf_sweep_results],
)

CSV.write(
    joinpath(@__DIR__, "purcell_filter_only_length_sweep.csv"),
    purcell_filter_length_sweep_df,
)

CSV.write(
    joinpath(@__DIR__, "purcell_filter_only_length_sweep_summary.csv"),
    purcell_filter_length_sweep_summary_df,
)

# =============================================================================
# 8. Plot
# =============================================================================

purcell_filter_only_sweep_plot = build_plot(
    [
        scatter(
            mode="lines",
            x=result.freqs,
            y=result.S21_mag,
            name="Lpf=$(round(result.pf_length_mm; digits=3)) mm",
        ) for result in pf_sweep_results
    ],
    "Purcell Filter Only: S21 vs PF Length Sweep",
    "Frequency (GHz)",
    "|S21|";
    legend_title="PF Length",
)

display(purcell_filter_only_sweep_plot)
