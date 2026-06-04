---
aliases:
  - "LC 共振器"
tags:
  - diataxis/tutorial
  - status/draft
---

# LC 共振器

LC 共振器是最基本的超導電路模型，理解它是學習更複雜電路的基礎。

## 物理背景

LC 電路的共振頻率由電感 $L$ 和電容 $C$ 決定：

$$f_0 = \frac{1}{2\pi\sqrt{LC}}$$

在共振頻率處，電路阻抗達到極值，反射係數 $S_{11}$ 會出現明顯的相位變化。

## 電路模型

```text
     ┌───────┐
 ────┤ Port  ├────┬────
     │  50Ω  │    │
     └───────┘    │
                ┌─┴─┐
                │ L │ 電感
                └─┬─┘
                  │
                ┌─┴─┐
                │ C │ 電容
                └─┬─┘
                  │
                 GND
```

## 完整程式碼

```julia title="examples/01_simple_lc/lc_resonator.jl"
using JosephsonCircuits
using PlotlyJS

# === 單位定義 ===
const nH = 1e-9
const pF = 1e-12
const GHz = 1e9

# === 符號變數 ===
@variables L C R50

# === 電路拓撲 ===
circuit = [
    ("P1", "1", "0", 1),
    ("R50", "1", "0", R50),
    ("L", "1", "2", L),
    ("C", "2", "0", C),
]

# === 參數值 ===
circuitdefs = Dict(
    L => 10nH,
    C => 1pF,
    R50 => 50,
)

# === 模擬設定 ===
ws = 2π * (0.1:0.01:10) * GHz
wp = (2π * 5.0GHz,)
sources = [(mode=(1,), port=1, current=0.0)]

# === 執行模擬 ===
sol = hbsolve(ws, wp, sources, (10,), (20,), circuit, circuitdefs)

# === 提取結果 ===
freqs = sol.linearized.w / (2π * GHz)
S11 = sol.linearized.S(outputmode=(0,), outputport=1, inputmode=(0,), inputport=1, freqindex=:)

# === 繪圖 ===
phase_deg = rad2deg.(angle.(S11))
trace = scatter(x=freqs, y=phase_deg, mode="lines", name="S11 Phase")
plot(trace)
```

👉 [下載完整程式碼](https://github.com/arfiligol/superconducting-circuits-research-workbench/blob/main/examples/01_simple_lc/lc_resonator.jl)

## 參數探索

試著改變 L 和 C 的值，觀察共振頻率如何變化：

| L (nH) | C (pF) | $f_0$ (GHz) |
|--------|--------|-------------|
| 10     | 1      | 1.59        |
| 5      | 1      | 2.25        |
| 10     | 0.5    | 2.25        |

## 下一步

👉 [參數掃描](parameter-sweep.md) — 學習如何自動化掃描參數
