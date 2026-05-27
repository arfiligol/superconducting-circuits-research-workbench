---
aliases:
  - "如何參與貢獻 (Contributing)"
  - "Contributing"
tags:
  - diataxis/how-to
  - audience/contributor
  - sot/true
  - topic/execution
status: stable
owner: docs-team
audience: contributor
scope: 建立開發環境、執行基本檢查、理解 canonical branch/worktree flow，並導向常用的 Codex contributor workflow。
version: v1.0.1
last_updated: 2026-03-30
updated_by: codex
---

# 如何參與貢獻 (Contributing)

感謝您有興趣參與 **超導量子電路平台** 專案的開發。

本頁只提供 contributor-facing 快速入口：

- 如何建立開發環境
- 如何執行基本檢查
- normal contribution 應如何對齊 branch / worktree flow
- 如何使用 Codex 進行 docs-first、多 agent、broad-slice + fixup iteration

完整 branch roles、isolated worktree policy、merge authority 與 multi-agent delivery model，
請以以下兩頁為準：

- [Branch & Worktree Flow](../reference/guardrails/execution-verification/branch-and-worktree-flow.md)
- [Multiple Agent Collaboration](../reference/guardrails/execution-verification/multi-agent-collaboration.md)

若您想直接使用本專案常見的 Codex 協作工作流，請參考：

- [使用 Codex 的分工與 Fixup 工作流](./contributing/codex-agent-workflow.md)

## 1. 環境建置

我們使用 `uv` 進行依賴管理。

### 前置需求
- Python 3.12+
- [uv](https://github.com/astral-sh/uv)

### 安裝步驟

1.  **Fork 專案**：
    在 GitHub 專案頁面上點擊 "Fork"，將專案複製到您自己的帳號下。

2.  **Clone 您的 Fork**：
    將 `<YOUR_USERNAME>` 替換為您的 GitHub 帳號：
    ```bash
    git clone https://github.com/<YOUR_USERNAME>/superconducting-circuits-tutorial.git
    cd superconducting-circuits-tutorial
    ```

3.  **同步依賴 (Sync dependencies)**：
    這會自動建立 `.venv` 虛擬環境並安裝所有套件（包含開發工具）。
    ```bash
    uv sync
    ```

4.  **啟動虛擬環境**：
    ```bash
    source .venv/bin/activate
    ```

## 2. 開發流程 (Workflow)

### Branch / Worktree Quick Summary

一般 contributor flow 的短版規則如下：

1. 先從 `develop` 同步最新狀態。
2. 新工作預設從 `develop` 建立 feature branch。
3. 若使用 AI agents，**每個 agent / task 都必須使用獨立 worktree**。
4. normal implementation / docs / test work 的預設 PR target 是 `develop`。
5. `main` 是 release branch，不是日常 feature work 的預設 landing branch。

!!! info "Canonical policy lives in Reference"
    本頁不重複完整 Git/worktree policy。
    若你要確認 `main` / `develop` 的角色、agent merge authority，或 sandbox/example agent 的 bounded write root，
    請直接閱讀 [Branch & Worktree Flow](../reference/guardrails/execution-verification/branch-and-worktree-flow.md)。
    其中也明確規定：`sandbox/**` / `examples/**` 內的 source code 屬於可追蹤內容；由其產生的 `csv`、`svg`、`png` 等 disposable outputs 不屬於預設必追蹤交付物。

### 執行測試
我們使用 `pytest` 確保功能正常。
```bash
uv run pytest
```

### 預覽文件
我們使用 `zensical` 的單語文件建置流程：`zensical.toml` 搭配 `docs/docs_zhtw/` staging tree。

先產生語言 staging tree：
```bash
./scripts/prepare_docs_locales.sh
```

預設埠（`localhost:8000`）：
```bash
uv run --group dev zensical serve
```

正式靜態輸出會產生在 `docs/site/`：
```bash
./scripts/build_docs_sites.sh
```

`zensical serve` 支援 Hot Reload，儲存文件後頁面會自動重新整理。

> 需要更多客製化？請參考 [Zensical 官方文件](https://zensical.org/docs/)。

### 提交變更 (Pull Request)

1.  **建立分支 (Branch)**：
    ```bash
    git fetch origin
    git switch develop
    git pull --ff-only origin develop
    git switch -c feature/my-new-feature
    ```
2.  **提交變更 (Commit)**：
    我們建議遵循 Conventional Commits 規範 (e.g., `feat:`, `fix:`, `docs:`)。
    ```bash
    git commit -m "feat: 新增某個功能"
    ```
3.  **推送至 Fork (Push)**：
    ```bash
    git push origin feature/my-new-feature
    ```
4.  **發起 Pull Request**：
    回到原始專案頁面，點擊 "Compare & pull request" 提交您的變更。
    normal work 的預設 PR target 應為 `develop`；`main` 保留給 verified release promotion。

### 提交前檢查 (Pre-commit Checks)
在提交 Pull Request 之前，請確保：

1.  **Typing**: 通過型別檢查（我們使用 Python 3.12+ 語法）。
2.  **Formatting**: 程式碼已格式化（遵循 PEP 8，透過 Ruff 檢查）。
3.  **Tests**: 所有測試皆通過。

> 詳細的程式碼品質規範請參考 [Code Style Guardrails](../reference/guardrails/code-quality/code-style.md)。

## 3. 開發規範 (Guardrails)

所有開發規範統一放在 **[Guardrails](../reference/guardrails/index.md)** 區塊。

!!! tip "AI 助手設定"
    如果您使用 AI 輔助工具（如 Cursor, Windsurf），請前往各規範頁面，複製底部的 **[#agent-rule](../reference/guardrails/index.md)** 區塊貼入您的 System Prompt。

### 快速連結

| 類別 | 規範 | Agent Rule |
|---|---|---|
| **專案基礎** | [專案概述](../reference/guardrails/project-basics/project-overview.md) | [#agent-rule](../reference/guardrails/project-basics/project-overview.md#agent-rule) |
| | [技術堆疊](../reference/guardrails/project-basics/tech-stack.md) | [#agent-rule](../reference/guardrails/project-basics/tech-stack.md#agent-rule) |
| | [目錄結構](../reference/guardrails/project-basics/folder-structure.md) | [#agent-rule](../reference/guardrails/project-basics/folder-structure.md#agent-rule) |
| **執行驗證** | [執行指令](../reference/guardrails/execution-verification/build-commands.md) | [#agent-rule](../reference/guardrails/execution-verification/build-commands.md#agent-rule) |
| | [Branch & Worktree Flow](../reference/guardrails/execution-verification/branch-and-worktree-flow.md) | [#agent-rule](../reference/guardrails/execution-verification/branch-and-worktree-flow.md#agent-rule) |
| | [Multiple Agent Collaboration](../reference/guardrails/execution-verification/multi-agent-collaboration.md) | [#agent-rule](../reference/guardrails/execution-verification/multi-agent-collaboration.md#agent-rule) |
| | [Linting](../reference/guardrails/execution-verification/linting.md) | [#agent-rule](../reference/guardrails/execution-verification/linting.md#agent-rule) |
| | [測試](../reference/guardrails/execution-verification/testing.md) | [#agent-rule](../reference/guardrails/execution-verification/testing.md#agent-rule) |
| **程式品質** | [程式碼風格](../reference/guardrails/code-quality/code-style.md) | [#agent-rule](../reference/guardrails/code-quality/code-style.md#agent-rule) |
| | [類型檢查](../reference/guardrails/code-quality/type-checking.md) | [#agent-rule](../reference/guardrails/code-quality/type-checking.md#agent-rule) |
| | [腳本撰寫](../reference/guardrails/code-quality/script-authoring.md) | [#agent-rule](../reference/guardrails/code-quality/script-authoring.md#agent-rule) |
| **文件設計** | [文件設計](../reference/guardrails/documentation-design/documentation.md) | [#agent-rule](../reference/guardrails/documentation-design/documentation.md#agent-rule) |
| | [Standards](../reference/guardrails/documentation-design/standards.md) | [#agent-rule](../reference/guardrails/documentation-design/standards.md#agent-rule) |
| | [Style](../reference/guardrails/documentation-design/style.md) | [#agent-rule](../reference/guardrails/documentation-design/style.md#agent-rule) |
| | [Maintenance](../reference/guardrails/documentation-design/maintenance.md) | [#agent-rule](../reference/guardrails/documentation-design/maintenance.md#agent-rule) |
| | [電路繪圖](./contributing/circuit-diagrams.md) | [#agent-rule](./contributing/circuit-diagrams.md#agent-rule) |
| | [Zensical Native Style](../reference/guardrails/documentation-design/zensical-native-style.md) | [#agent-rule](../reference/guardrails/documentation-design/zensical-native-style.md#agent-rule) |
