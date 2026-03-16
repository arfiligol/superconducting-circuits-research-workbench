---
aliases:
  - App Shared Reference
  - Shared App Model
tags:
  - diataxis/reference
  - audience/team
  - sot/true
  - topic/app-reference
status: draft
owner: docs-team
audience: team
scope: App 共享模型，涵蓋 runtime modes、workspace、resource scope、auth、runtime 與 audit
version: v0.2.0
last_updated: 2026-03-16
updated_by: codex
---

# Shared App Model

本區收錄 Frontend 與 Backend 共同依賴的 App-level shared model。

!!! info "What belongs here"
    若一份文件同時在回答 shell context、workspace collaboration、task queue visibility、runtime governance 或 audit trail，
    但又不屬於單一 frontend page 或單一 backend surface，它就應該放在這裡。

!!! warning "Not Core, Not CLI"
    本區不是 `Core`，也不是 `CLI`。
    這些頁主要定義 multi-user app 與 service-backed workflows 的 shared semantics。

!!! info "Same app across local and online modes"
    本區也負責同一個 App 在 `Local Mode` 與 `Online Mode` 之間共享的 mode model。
    若某個 contract 需要回答「local 是否 bypass auth」、「online 是否需要 collaboration」，通常都屬於這裡。

## Page Map

| Page | Core focus |
|---|---|
| [Runtime Modes](runtime-modes.md) | 同一個 App 的 `Local Mode` / `Online Mode`、mode switch 與 isolation rules |
| [Identity & Workspace Model](identity-workspace-model.md) | user、session、active workspace、active dataset 的最小模型 |
| [Resource Ownership & Visibility](resource-ownership-and-visibility.md) | dataset / schema / task / result 的 workspace ownership 與 sharing rules |
| [Authentication & Authorization](authentication-and-authorization.md) | workspace membership、capabilities、queue permissions |
| [Response & Error Contract](response-and-error-contract.md) | success / error envelope、common error families、frontend display contract |
| [Outbound Email Delivery](outbound-email-delivery.md) | workspace invitation 的 SMTP baseline 與 mail delivery contract |
| [Task Runtime & Processors](task-runtime-and-processors.md) | worker / processor status、task state machine、cancel / terminate |
| [Audit Logging](audit-logging.md) | actor-centric audit trail 與 separate audit store |

## Related

* [Frontend Reference](../frontend/index.md)
* [Backend Reference](../backend/index.md)
* [Architecture Reference](../../architecture/index.md)
