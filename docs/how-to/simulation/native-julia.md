---
aliases:
  - "Native Julia Simulation"
  - "原生 Julia 模擬"
tags:
  - diataxis/how-to
  - status/stable
  - topic/simulation
  - topic/julia
  - topic/advanced
status: stable
owner: docs-team
audience: user
scope: "原生 Julia 模擬進階教學"
version: v0.2.0
last_updated: 2026-05-28
updated_by: codex
---

# 原生 Julia 模擬

本教學說明如何直接使用 JosephsonCircuits.jl 進行電路模擬，適合進階使用者或需要擴充功能的開發者。

## 何時選擇原生 Julia？

| 情況 | 建議方法 |
|------|----------|
| 產品化提交、監控、結果瀏覽 | Application task，交由 Julia Runner 非同步執行 |
| 複雜電路、自定義元件 | **原生 Julia** |
| 開發新模擬功能 | **原生 Julia** |
| 效能關鍵應用 | **原生 Julia** |

## 環境設定

### 使用專案 Julia 環境

```bash
cd superconducting-circuits-tutorial
julia --project=core/julia/SuperconductingCircuitsCore
```

### 載入套件

```julia
using JosephsonCircuits
using Plots  # 可選，用於繪圖
```

## 基本語法

### 單位定義

```julia
# 常用單位
nH = 1e-9   # nanohenry
pF = 1e-12  # picofarad
fF = 1e-15  # femtofarad
GHz = 1e9   # gigahertz
MHz = 1e6   # megahertz
```

### 符號變數

```julia
using JosephsonCircuits: @variables

@variables L C Cj Lj R50
```

### 電路定義

電路以 Tuple 陣列定義，每個元素格式為：
`(元件名稱, 節點1, 節點2, 值)`

```julia
circuit = [
    ("P1", "1", "0", 1),       # Port (固定值 1)
    ("R50", "1", "0", R50),    # 電阻
    ("L", "1", "2", L),        # 電感
    ("C", "2", "0", C),        # 電容
]
```

### 參數值

```julia
circuitdefs = Dict(
    L => 10nH,
    C => 1pF,
    R50 => 50.0,
)
```

## 執行 Harmonic Balance

### 頻率設定

```julia
# 頻率範圍
f_start, f_stop, n_points = 0.1GHz, 5GHz, 100
frequencies = range(f_start, f_stop, length=n_points)
ws = 2π .* frequencies  # 角頻率
```

### Pump 設定

```julia
# Pump 頻率和源設定
wp = (2π * 5GHz,)  # Pump 頻率
sources = [(mode=(1,), port=1, current=0.0)]
```

### 執行模擬

```julia
# hbsolve 參數: (ws, wp, sources, Npumpharmonics, Nmodulationharmonics, circuit, circuitdefs)
sol = hbsolve(ws, wp, sources, (10,), (20,), circuit, circuitdefs)
```

## 提取 S 參數

```julia
# 提取 S11
S11 = sol.linearized.S(
    outputmode=(0,),
    outputport=1,
    inputmode=(0,),
    inputport=1,
    freqindex=:
)

# 計算振幅和相位
S11_mag = abs.(S11)
S11_phase = angle.(S11)

# 找共振
min_idx = argmin(S11_mag)
resonance_freq = frequencies[min_idx] / GHz
println("共振頻率: $(resonance_freq) GHz")
```

## 進階：Josephson Junction

模擬含 Josephson Junction 的電路：

```julia
@variables Lj Cj Ic

# SQUID 電路範例
circuit = [
    ("P1", "1", "0", 1),
    ("R50", "1", "0", 50.0),
    ("C", "1", "2", C),
    ("Lj", "2", "0", Lj),     # Junction 電感
    ("Cj", "2", "0", Cj),     # Junction 電容
]

# Junction 參數
Φ0 = 2.067833848e-15  # 磁通量子
Ic = 1e-6             # 臨界電流 (1 μA)
Lj0 = Φ0 / (2π * Ic)  # Josephson 電感

circuitdefs = Dict(
    C => 10fF,
    Lj => Lj0,
    Cj => 5fF,
)
```

## 參數掃描

```julia
# 掃描電容值
C_values = [0.5, 1.0, 1.5, 2.0] .* pF
results = []

for C_val in C_values
    circuitdefs[C] = C_val
    sol = hbsolve(ws, wp, sources, (10,), (20,), circuit, circuitdefs)
    S11 = sol.linearized.S(outputmode=(0,), outputport=1, inputmode=(0,), inputport=1, freqindex=:)
    push!(results, (C=C_val, S11=S11))
end
```

## 多執行緒加速

```julia
using Base.Threads

# 確認執行緒數
println("使用 $(nthreads()) 個執行緒")

# 平行掃描
Threads.@threads for i in 1:length(C_values)
    # ... 模擬邏輯
end
```

啟動 Julia 時指定執行緒數：

```bash
julia --project=. --threads=auto
```

## 相關資源

- [JosephsonCircuits.jl 文件](https://qicklab.github.io/JosephsonCircuits.jl/)
- [Tutorial: LC 共振器](../../tutorials/lc-resonator.md) - 入門案例
- [擴充 Julia 函數](../extend/extend-julia-functions.md) - 貢獻者指南
