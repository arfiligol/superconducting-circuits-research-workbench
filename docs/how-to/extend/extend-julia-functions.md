---
aliases:
  - "Extend Julia Functions"
  - "擴充 Julia 函數"
tags:
  - diataxis/how-to
  - status/stable
  - topic/extend
  - topic/contributing
  - topic/julia
status: stable
owner: docs-team
audience: contributor
scope: "貢獻者指南：擴充 Julia 模擬函數"
version: v0.1.0
last_updated: 2026-01-28
updated_by: docs-team
---

# 擴充 Julia 函數

本指南說明如何為專案新增 Julia 模擬函數，並透過 Python 封裝供使用者使用。

## 架構概覽

```
Python                    JuliaCall                Julia
┌─────────────────┐       ┌─────────────┐         ┌─────────────────────┐
│ CLI Script      │       │             │         │ hbsolve.jl          │
│ (run_lc.py)     │──────▶│  juliacall  │────────▶│ run_lc_simulation() │
├─────────────────┤       │             │         └─────────────────────┘
│ JuliaSimulator  │       │             │                   │
│ (julia_adapter) │◀──────│  Main       │◀──────────────────┘
├─────────────────┤       └─────────────┘         ┌─────────────────────┐
│ Domain Models   │                               │ JosephsonCircuits.jl│
│ (circuit.py)    │                               └─────────────────────┘
└─────────────────┘
```

## 步驟 1：新增 Julia 函數

編輯 `core/simulation/infrastructure/hbsolve.jl`：

```julia
"""
    run_my_simulation(param1, param2, ...)

新函數的說明。

# Arguments
- `param1`: 參數 1 說明
- `param2`: 參數 2 說明

# Returns
Dict with keys: :frequencies_ghz, :s11_real, :s11_imag
"""
function run_my_simulation(param1::Float64, param2::Float64)
    # 單位轉換（如需要）
    nH = 1e-9
    pF = 1e-12
    GHz = 1e9

    # 定義電路
    @variables L C R50
    circuit = [
        ("P1", "1", "0", 1),
        # ... 電路定義
    ]

    circuitdefs = Dict(
        L => param1 * nH,
        C => param2 * pF,
        R50 => 50.0,
    )

    # 頻率設定
    frequencies = range(0.1, 10, length=100) .* GHz
    ws = 2π .* frequencies

    # Pump 設定
    wp = (2π * 5GHz,)
    sources = [(mode=(1,), port=1, current=0.0)]

    # 執行模擬
    sol = hbsolve(ws, wp, sources, (10,), (20,), circuit, circuitdefs)

    # 提取 S11
    S11 = sol.linearized.S(
        outputmode=(0,), outputport=1,
        inputmode=(0,), inputport=1,
        freqindex=:
    )

    # 返回 Dict（會被轉換為 Python dict）
    return Dict(
        :frequencies_ghz => collect(frequencies ./ GHz),
        :s11_real => real.(S11),
        :s11_imag => imag.(S11)
    )
end
```

!!! important
    - 函數必須返回 `Dict`，使用 Symbol 作為 key
    - 陣列使用 `collect()` 轉換為 Julia Array
    - 不要在函數內使用 `const`（Julia 不允許在函數內宣告 const）

## 步驟 2：新增 Pydantic Domain Model（如需要）

若新函數需要新的輸入/輸出結構，編輯 `core/simulation/domain/circuit.py`：

```python
from pydantic import BaseModel

class MySimulationConfig(BaseModel):
    """新模擬配置。"""

    param1: float
    param2: float
    # ... 其他參數

class MySimulationResult(BaseModel):
    """新模擬結果。"""

    frequencies_ghz: list[float]
    s11_real: list[float]
    s11_imag: list[float]
    # ... 其他輸出
```

## 步驟 3：更新 Python Adapter

編輯 `core/simulation/infrastructure/julia_adapter.py`：

```python
from core.simulation.domain.circuit import (
    FrequencyRange,
    SimulationResult,
    MySimulationConfig,  # 新增
)

class JuliaSimulator:
    # ... 現有方法 ...

    def run_my_simulation(
        self,
        config: MySimulationConfig,
        freq_range: FrequencyRange,
    ) -> SimulationResult:
        """
        執行自定義模擬。

        Args:
            config: 模擬配置。
            freq_range: 頻率範圍。

        Returns:
            SimulationResult with S11 data.
        """
        self._ensure_initialized()
        assert self._jl is not None

        # 呼叫 Julia 函數
        result = self._jl.run_my_simulation(
            float(config.param1),
            float(config.param2),
        )

        # 轉換結果
        return SimulationResult(
            frequencies_ghz=list(result["frequencies_ghz"]),
            s11_real=list(result["s11_real"]),
            s11_imag=list(result["s11_imag"]),
        )
```

!!! tip
    - 使用 `assert self._jl is not None` 滿足型別檢查
    - Julia 返回的 Dict key 是 Symbol，但 JuliaCall 會自動轉換為 Python str

## 步驟 4：新增 CLI Entry Point

建立 `src/scripts/simulation/run_my_simulation.py`：

```python
"""CLI for my custom simulation."""

import argparse
import sys

from core.simulation.infrastructure.julia_adapter import JuliaSimulator
from core.simulation.domain.circuit import FrequencyRange


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run my custom simulation",
    )
    parser.add_argument("--param1", type=float, required=True)
    parser.add_argument("--param2", type=float, required=True)
    parser.add_argument("--start", type=float, default=0.1)
    parser.add_argument("--stop", type=float, default=10.0)
    parser.add_argument("--points", type=int, default=100)

    args = parser.parse_args()

    print(f"Running simulation: param1={args.param1}, param2={args.param2}")

    simulator = JuliaSimulator()
    freq_range = FrequencyRange(
        start_ghz=args.start,
        stop_ghz=args.stop,
        points=args.points,
    )

    # 使用新函數
    result = simulator.run_my_simulation(
        config=MySimulationConfig(
            param1=args.param1,
            param2=args.param2,
        ),
        freq_range=freq_range,
    )

    print(f"Simulation complete: {len(result.frequencies_ghz)} points")


if __name__ == "__main__":
    main()
```

## 步驟 5：註冊 CLI Entry Point

更新 `pyproject.toml`：

```toml
[project.scripts]
# ... 現有 scripts ...
sc-my-simulation = "scripts.simulation.run_my_simulation:main"
```

## 步驟 6：測試

```bash
# 型別檢查
uv run basedpyright core/simulation/

# 執行測試
uv run sc-my-simulation --param1 10.0 --param2 1.0
```

## 步驟 7：更新文件

1. 在 `docs/reference/cli/` 新增 CLI 參考頁面
2. 更新 `docs/how-to/simulation/` 相關教學
3. 更新 README.md（如需要）

## 常見問題

### Julia 語法錯誤

**問題**：`syntax: unsupported 'const' declaration on local variable`

**解決**：Julia 不允許在函數內使用 `const`，改為普通變數賦值。

### 型別轉換

| Python 類型 | Julia 類型 |
|-------------|------------|
| `float` | `Float64` |
| `int` | `Int` |
| `list` | `Vector` |
| `dict` | `Dict` |

### 效能考量

對於需要大量迴圈的計算（如參數掃描），建議在 Julia 端實作完整邏輯，而非從 Python 反覆呼叫。

## 相關資源

- [Script Authoring](../../reference/guardrails/code-quality/script-authoring.md) - CLI 規範
- [Folder Structure](../../reference/guardrails/project-basics/folder-structure.md) - 目錄結構
- [Python API 詳解](../simulation/python-api.md) - API 使用
