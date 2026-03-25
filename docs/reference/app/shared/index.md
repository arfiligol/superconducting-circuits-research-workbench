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
scope: App 共享模型，涵蓋 runtime modes、workspace、resource scope、auth、runtime、observability 與 audit
version: v0.4.0
last_updated: 2026-03-25
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

## Grouping Principle

本區優先依 **責任類型** 分組，而不是依 `Local Mode` / `Online Mode` 分樹。

原因是：

- 多數 shared contracts 同時適用於 `local` 與 `online`
- 差異通常是 applicability 或 authority semantics，不是 owner 真的換了一套
- 若直接拆成 mode-based folder / nav，反而容易長出兩份互相重複的 SoT

!!! info "Mode is an applicability dimension"
    `Local Mode` / `Online Mode` 應優先在各頁 contract 內表達 applicability 與差異語意。
    Shared index 與 nav 則優先回答「這份 contract 在管什麼責任」。

## Page Map

=== "Foundations / Cross-Mode"

    | Page | Core focus |
    |---|---|
    | [Runtime Modes](runtime-modes.md) | 同一個 App 的 `Local Mode` / `Online Mode`、desktop runtime profile overlay、mode switch 與 isolation rules |
    | [Mode Feature Matrix](mode-feature-matrix.md) | 各 shared surfaces / workflows 在 `Local Mode` 與 `Online Mode` 下的 support matrix |
    | [Response & Error Contract](response-and-error-contract.md) | success / error envelope、common error families、frontend display contract |

=== "Identity / Access / Collaboration"

    | Page | Core focus |
    |---|---|
    | [Identity & Workspace Model](identity-workspace-model.md) | user、session、active workspace、active dataset 的最小模型 |
    | [Resource Ownership & Visibility](resource-ownership-and-visibility.md) | dataset / schema / task / result 的 workspace ownership 與 sharing rules |
    | [Authentication & Authorization](authentication-and-authorization.md) | workspace membership、capabilities、queue permissions |
    | [Outbound Email Delivery](outbound-email-delivery.md) | workspace invitation 的 SMTP baseline 與 mail delivery contract |

=== "Execution Runtime"

    | Page | Core focus |
    |---|---|
    | [Task Runtime & Processors](task-runtime-and-processors.md) | worker / processor status、task state machine、cancel / terminate、local runtime topology |

=== "Governance / Observability"

    | Page | Core focus |
    |---|---|
    | [Observability Model](observability-model.md) | audit logging、workflow observability、product telemetry 的 shared taxonomy |
    | [Audit Logging](audit-logging.md) | actor-centric audit trail 與 separate audit store |

## Related

* [Frontend Reference](../frontend/index.md)
* [Backend Reference](../backend/index.md)
* [Architecture Reference](../../architecture/index.md)
