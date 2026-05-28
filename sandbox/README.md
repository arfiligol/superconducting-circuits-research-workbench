# Sandbox 實驗區

這個目錄用於自由實驗和探索。

## 使用方式

1. 在這裡建立 `.jl` 腳本進行實驗
2. 腳本不會被 Git 追蹤（已在 `.gitignore` 排除）
3. 實驗成功後，整理並複製到 `examples/` 目錄

## 範例

```julia
# sandbox/my_experiment.jl
using JosephsonCircuits
# ... 你的實驗代碼
```

## 注意

- 這裡的 `.jl` 檔案不進版控
- 如果想保留代碼，請移到 `examples/`

## Promoted Julia Core

The reusable circuit component prototype has been promoted to:

`core/julia/SuperconductingCircuitsCore/`

New development should happen in the Julia Core package and the docs-defined Julia Core authoring model. Sandbox copies of retired circuit-model prototypes should not be kept as runnable fallback implementations.
