---
aliases:
  - Outbound Email Delivery
  - SMTP Delivery
  - 郵件發送
tags:
  - diataxis/reference
  - audience/team
  - sot/true
  - topic/app-reference
status: draft
owner: docs-team
audience: team
scope: workspace invitation email delivery、SMTP baseline、manual invite fallback 與 delivery audit contract
version: v0.1.0
last_updated: 2026-03-14
updated_by: team
---

# Outbound Email Delivery

本頁定義 multi-user app 的 outbound email baseline。V1 的 primary consumer 是 workspace invitation。

!!! info "Why this exists"
    既然正式 invitation flow 以 email 為主，就必須把 mail delivery 的 baseline 顯式寫出來，而不是藏在 auth 文字裡。

!!! warning "SMTP Is The Baseline, Not An Afterthought"
    只要 deployment 要支援真正的多人 invite flow，就必須配置可用的 outbound email transport。
    沒有 SMTP 時，只允許 local / admin-controlled environment 使用 manual invite link fallback。

## Coverage

| Concern | Meaning |
|---|---|
| Delivery transport | 邀請信實際如何送出 |
| Invite message contract | email 內至少要帶哪些資訊 |
| Delivery states | sent / failed / manual 等狀態如何回報 |
| Failure handling | 發信失敗後系統如何通知與 audit |

## Transport Baseline

| Item | Rule |
|---|---|
| Primary transport | SMTP |
| Delivery mode | server-side send |
| Required for production invite flow | yes |
| Local fallback | manual invite link copy |

## SMTP Configuration Baseline

| Environment variable | Meaning |
|---|---|
| `SC_SMTP_HOST` | SMTP server host |
| `SC_SMTP_PORT` | SMTP server port |
| `SC_SMTP_USERNAME` | SMTP auth username |
| `SC_SMTP_PASSWORD` | SMTP auth password |
| `SC_SMTP_FROM_EMAIL` | sender email |
| `SC_SMTP_FROM_NAME` | sender display name |
| `SC_SMTP_USE_TLS` | TLS / STARTTLS baseline switch |
| `SC_APP_BASE_URL` | invitation accept URL 的 base origin |

## Invitation Email Contract

| Field | Required meaning |
|---|---|
| workspace name | 受邀加入哪個 workspace |
| inviter display name | 誰發出 invite |
| role summary | 受邀後的預設 role |
| accept URL | 單次使用 invite token URL |
| expiry summary | token 何時過期 |
| support / admin hint | 發信失敗或邀請錯誤時的下一步 |

## Delivery States

| State | Meaning |
|---|---|
| `queued_for_delivery` | invite 已建立，等待 mail send |
| `sent` | SMTP provider 已接受送件 |
| `delivery_failed` | 發信失敗，尚未完成 email delivery |
| `manual_link_ready` | 沒有 SMTP，但已生成 copyable invite URL |

## Failure Handling

| Rule | Meaning |
|---|---|
| Failure must be surfaced | invite issuer 必須知道 delivery 是否失敗 |
| No silent downgrade | production flow 不應在未告知情況下自動改成 manual link |
| Audit required | invite sent / failed / manual link generated 都必須記錄 |
| Secret handling | mail transport secret 不可寫入 audit payload 或一般 runtime logs |

## Related

* [Authentication & Authorization](authentication-and-authorization.md)
* [Audit Logging](audit-logging.md)
* [Backend / Session & Workspace](../backend/session-workspace.md)
