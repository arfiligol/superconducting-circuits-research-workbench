---
aliases:
  - "參數掃描"
tags:
  - diataxis/tutorial
  - status/draft
---

# 參數掃描

學習如何對電路參數進行系統性掃描，這是分析電路行為的重要技術。

## 單維度掃描

掃描單一參數，觀察其對電路響應的影響。

### 範例：掃描電感值

```julia title="examples/02_parameter_sweep/single_sweep.jl"
using JosephsonCircuits
using PlotlyJS

const nH = 1e-9
const pF = 1e-12
const GHz = 1e9

@variables L C R50

circuit = [
    ("P1", "1", "0", 1),
    ("R50", "1", "0", R50),
    ("L", "1", "2", L),
    ("C", "2", "0", C),
]

# 基本參數
base_defs = Dict(C => 1pF, R50 => 50)

# 掃描範圍
L_values = (5:1:15) * nH

# 模擬設定
ws = 2π * (0.1:0.01:10) * GHz
wp = (2π * 5.0GHz,)
sources = [(mode=(1,), port=1, current=0.0)]

# 儲存結果
traces = []

for L_val in L_values
    defs = merge(base_defs, Dict(L => L_val))
    sol = hbsolve(ws, wp, sources, (10,), (20,), circuit, defs)

    freqs = sol.linearized.w / (2π * GHz)
    S11 = sol.linearized.S(outputmode=(0,), outputport=1, inputmode=(0,), inputport=1, freqindex=:)

    push!(traces, scatter(
        x=freqs,
        y=rad2deg.(angle.(S11)),
        mode="lines",
        name="L = $(round(L_val/nH, digits=1)) nH"
    ))
end

plot(traces)
```

## 多維度掃描

同時掃描多個參數。

### 範例：掃描 L 和 C

```julia title="examples/02_parameter_sweep/multi_sweep.jl"
using JosephsonCircuits
using DataFrames

const nH = 1e-9
const pF = 1e-12
const GHz = 1e9

# 掃描網格
L_values = [5, 10, 15] * nH
C_values = [0.5, 1.0, 1.5] * pF

# 結果表格
results = DataFrame(L_nH=Float64[], C_pF=Float64[], f0_GHz=Float64[])

for L_val in L_values
    for C_val in C_values
        # 理論共振頻率
        f0 = 1 / (2π * sqrt(L_val * C_val)) / GHz

        push!(results, (L_val/nH, C_val/pF, f0))
    end
end

println(results)
```

## 檢視結果

目前產品化檢視應透過 Application 的 Result Browser 或 notebook cockpit 完成。
Application-triggered simulation 由 Julia Runner 產生 staging Zarr，再由 Backend publish 成正式 TraceStore。

研究中的直接掃描可以在 Pluto notebook 中繪圖；不要依賴已移除的 root Julia helper。

## 下一步

👉 [Notebook Interface](../reference/notebooks/index.md) — 了解研究 notebook 與 app task 的邊界
