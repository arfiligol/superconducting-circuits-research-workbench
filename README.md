# Superconducting Circuits Tutorial

使用 [JosephsonCircuits.jl](https://github.com/QICKLab/JosephsonCircuits.jl) 學習超導電路模擬的教學專案。

## Rewrite Foundation

Rewrite branch 目前同時保留 legacy NiceGUI runtime 與新的 `frontend/`、`backend/`、`desktop/` foundation。
請用獨立入口操作 rewrite stack，不要把 legacy runtime helper 當成 rewrite 啟動方式。

### Runtime Modes

目前產品模型是「同一個 app shell，兩種 runtime mode」：

- `Local Mode`
  - 適合本機操作、教學、草稿與單機工作流
  - 對使用者來說是 app 內建的本地 authority surface
  - 對 repo contributor 來說，通常代表啟動 rewrite 本機 stack
- `Online Mode`
  - 使用同一個 shell，但改連到獨立的 backend server target
  - 需要明確啟動 server，並在 app 內輸入 target (`IP:Port` / origin) 後再進入 online flow

!!! info "Contributor shorthand"
    如果你只是想把 app 跑起來並開始操作，先用 `npm run rewrite:dev`。
    這會啟動 repo 內的 rewrite frontend + local backend pairing，作為本機開發 baseline。

### Rewrite Quick Start

```bash
# Install rewrite workspace dependencies
npm run rewrite:install

# Run rewrite checks from repo root
npm run rewrite:check

# Build rewrite workspaces
npm run rewrite:build

# Start rewrite frontend + backend dev stack
npm run rewrite:dev

# Stop rewrite stack
npm run rewrite:stop
```

### Runtime Startup Paths

#### Local Mode / Local Development Baseline

如果你要的是本機 baseline：

```bash
# Repo-root orchestration: frontend + local backend
npm run rewrite:dev
```

常用入口：

- frontend: [http://127.0.0.1:3000](http://127.0.0.1:3000)
- backend health: [http://127.0.0.1:8000/health](http://127.0.0.1:8000/health)

這條路徑最適合：

- 本機操作
- UI / workflow 開發
- schemdraw / schema / dataset / task baseline 驗證
- Desktop wrapper 連本機 frontend

#### Online / Server Mode

如果你要驗證 app 連外部 server target 的 online flow，請先啟動 backend server：

```bash
cd backend && uv sync
cd backend && uv run uvicorn src.app.main:app --reload --host 127.0.0.1 --port 8000
```

接著在 app 內：

1. 進入 runtime-mode entry（例如 Header `Global Context`、Account、Auth Entry）
2. 輸入 server target，例如 `http://127.0.0.1:8000`
3. 切到 `Online Mode`
4. 視目前 session 狀態再進入 sign-in / retry / target validation flow

!!! warning "Mode switch is not a data bridge"
    `Local Mode` 和 `Online Mode` 是 context switch，不會自動搬移 datasets、schemas、results 或 tasks。
    local/online 之間的資料移動仍應透過明確的 import / upload / download / export flow。

### Rewrite Desktop Wrapper

```bash
# Start the rewrite stack first, then wrap the frontend in Electron
DESKTOP_START_URL=http://127.0.0.1:3000 npm run dev --prefix desktop
```

### Rewrite CLI

```bash
# Install local rewrite packages, including sc-core and sc-cli
uv sync

# Show the new Typer-based CLI package help
uv run sc --help

# Proof commands wired to sc-core
uv run sc core preview-artifacts
uv run sc circuit-definition inspect path/to/draft.circuit.yaml
```

### Legacy Runtime

```bash
# Legacy NiceGUI runtime remains separate
./scripts/dev_start.sh
./scripts/dev_stop.sh
```

## 📚 文件網站

👉 **[線上教學文件](https://arfiligol.github.io/superconducting-circuits-tutorial/)**

## 🚀 快速開始

### 1. 安裝環境

```bash
git clone https://github.com/arfiligol/superconducting-circuits-tutorial.git
cd superconducting-circuits-tutorial

# Python 環境 (使用 uv)
uv sync

# Julia 依賴會在首次執行時自動安裝 (透過 juliapkg)
```

### 2. 本地預覽文件

```bash
# 先產生 zh-TW staging tree
./scripts/prepare_docs_locales.sh

# 文件站
uv run --group dev zensical serve

# 靜態建置輸出到 docs/site/
./scripts/build_docs_sites.sh
```

## 📁 專案結構

```
superconducting-circuits-tutorial/
├── cli/                     # Rewrite Typer CLI adapter package
│   ├── src/sc_cli/          # Commands, presenters, entrypoint
│   └── tests/               # CLI-focused pytest coverage
├── backend/                 # FastAPI rewrite service
│   ├── src/app/             # API, services, domain, infrastructure
│   └── sc_backend/          # CLI-safe backend facade package
├── frontend/                # Next.js rewrite frontend
├── desktop/                 # Electron rewrite wrapper
├── src/
│   ├── app/                 # Legacy NiceGUI runtime (migration-only)
│   ├── core/                # Installable shared scientific core
│   │   └── sc_core/         # Framework-agnostic rewrite boundary
│   ├── julia/               # Shared Julia utilities and plotting helpers
│   ├── scripts/             # Legacy CLI and migration helpers
│   └── worker/              # Worker runtime and task execution
├── data/                    # Local DB / raw / processed / trace-store data
├── docs/                    # Zensical docs and guardrails
│   ├── overrides/           # Docs theme overrides
│   └── docs_zhtw/           # Generated zh-TW staging tree (do not edit directly)
├── examples/                 # 可執行範例
├── sandbox/                  # Scratch scripts and legacy experiments
├── openapi.json              # Committed OpenAPI snapshot for frontend-backend contract sync
├── pyproject.toml            # Python 依賴 (uv)
├── juliapkg.json             # Julia 依賴 (JosephsonCircuits.jl)
├── Project.toml              # Julia 專案設定
└── Manifest.toml             # Julia lock file
```

## 🔬 模擬工具 (Simulation)

使用 JosephsonCircuits.jl 進行電路模擬：

```bash
# LC 共振器模擬
uv run sc-simulate-lc -L 10 -C 1 --start 0.1 --stop 5 --points 100
```

| 指令 | 說明 |
|------|------|
| `sc-simulate-lc` | LC 共振器 S 參數模擬 |

## 📊 分析工具 (Analysis)

Python CLI 工具進行數據分析：

```bash
# SQUID 模型擬合
uv run sc analysis fit lc-squid SampleDataset

# Flux 依賴性繪圖
uv run sc plot flux-dependence FluxSweepDataset
```

| 指令 | 說明 |
|------|------|
| `sc analysis fit lc-squid` | SQUID 導納模型擬合 |
| `sc plot admittance` | 導納數據視覺化 (lines/heatmap) |
| `sc plot flux-dependence` | Flux 依賴性分析繪圖 |
| `sc plot different-qubit-structure-frequency-comparison-table` | 不同 Qubit 結構頻率比較表 |

## 🎯 適合誰？

- 想學習超導量子電路模擬的研究生
- 需要使用 JosephsonCircuits.jl 的研究人員
- 對 JPA 和 Qubit 模擬有興趣的人

## 📖 教學主題

| 主題 | 說明 |
|------|------|
| LC 共振器 | 基本電路模型 |
| 參數掃描 | 單/多維度掃描技術 |
| Harmonic Balance | 核心模擬方法 |
| S/Z/Y 參數 | 網路參數分析 |

## 📜 License

MIT
