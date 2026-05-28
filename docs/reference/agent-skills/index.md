---
aliases:
  - Agent Skill Library
  - Project Skill Library
  - Agent 技能庫
tags:
  - diataxis/reference
  - audience/contributor
  - sot/true
  - topic/governance
status: draft
owner: docs-team
audience: contributor
scope: 跨工具 AI Agent 參與本專案開發時建議同步的 project-provided skill catalog 與同步規則
version: v0.1.0
last_updated: 2026-05-28
updated_by: codex
---

# Agent Skill Library

本區提供 project-provided Skill templates，讓 Codex App、Claude Code、Gemini 或其他 coding agent 可以同步成各自工具支援的 reusable instruction、skill、command 或 agent context。

這裡不是新的 runtime surface，也不是固定 agent 編制。它定義的是：如果一個 agent 要參與本專案開發，最好先具備哪些可重用能力。

!!! warning "Sync, then load SoT"
    Skill 只能提供工作流程能力。每次實際開發仍必須先讀本 repo 的 SoT、guardrails、folder structure、commands 與 validation rules。Skill 不能取代 workspace rules。

## Sync Contract

Agent 同步本區 Skill 時，必須保留三件事：

| Required part | Rule |
| --- | --- |
| `name` | 保留 canonical skill name，方便不同工具與交付報告使用同一名稱 |
| trigger description | 保留何時使用此 skill 的描述，不要只留下正文 |
| hard-block behavior | 若 skill 要求缺文件即停止，不可改成 agent 自行猜測 |

??? example "Copy this table as Markdown"
    ```markdown
    | Required part | Rule |
    | --- | --- |
    | `name` | 保留 canonical skill name，方便不同工具與交付報告使用同一名稱 |
    | trigger description | 保留何時使用此 skill 的描述，不要只留下正文 |
    | hard-block behavior | 若 skill 要求缺文件即停止，不可改成 agent 自行猜測 |
    ```

Agent 可以把同一份 Skill template 轉成不同工具的原生格式：

| Agent environment | Expected sync behavior |
| --- | --- |
| Codex App | 建立對應 Codex Skill，並讓 skill description 觸發載入 |
| Claude Code | 建立等價 reusable instruction、command、agent definition 或 context fragment |
| Gemini | 建立等價 reusable instruction 或 project context fragment |
| Other coding agents | 使用該工具支援的 reusable context / skill / command 機制 |

??? example "Copy this table as Markdown"
    ```markdown
    | Agent environment | Expected sync behavior |
    | --- | --- |
    | Codex App | 建立對應 Codex Skill，並讓 skill description 觸發載入 |
    | Claude Code | 建立等價 reusable instruction、command、agent definition 或 context fragment |
    | Gemini | 建立等價 reusable instruction 或 project context fragment |
    | Other coding agents | 使用該工具支援的 reusable context / skill / command 機制 |
    ```

!!! info "Tool-specific details"
    本 repo 不規定每個外部工具的本機安裝路徑。同步 agent 必須依照自己工具當下支援的官方機制建立 skill，並保留本區的 canonical content。

## Catalog

| Skill | Status | Use when | Template |
| --- | --- | --- | --- |
| `work-lane-orchestration` | Recommended | 任務需要主 thread 統整、多 surface vertical slice、subagent work lanes、SoT loading、跨邊界驗收 | [Work Lane Orchestration](work-lane-orchestration.md) |

??? example "Copy this table as Markdown"
    ```markdown
    | Skill | Status | Use when | Template |
    | --- | --- | --- | --- |
    | `work-lane-orchestration` | Recommended | 任務需要主 thread 統整、多 surface vertical slice、subagent work lanes、SoT loading、跨邊界驗收 | [Work Lane Orchestration](work-lane-orchestration.md) |
    ```

## Update Rules

新增或修改本區 Skill 時：

1. 在 `docs/reference/agent-skills/` 新增或更新 template page。
2. 更新本頁 `Catalog`。
3. 若新增頁面，更新 `zensical.toml` navigation。
4. 保持 skill template 跨專案可用，不把本 repo 的 lane taxonomy、commands 或 folder ownership hardcode 進 generic skill。
5. 若 skill 的目的本來就是本 repo 專用，必須在頁面標明 project-specific，不要包裝成通用能力。

## Related

- [Codex Subagent Coordination](../guardrails/execution-verification/multi-agent-collaboration.md)
- [Source of Truth Order](../guardrails/project-basics/source-of-truth-order.md)
- [Folder Structure](../guardrails/project-basics/folder-structure.md)
