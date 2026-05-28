## Execution & Verification
- 定義 build、lint、type-check、test、CI 的 workspace 基線。
- branch roles、direct-develop policy 與 optional worktree use 由 `Branch & Worktree Flow` 定義。
- 變更程式碼時，優先執行與 touched area 直接相關的檢查。
- workspace delivery baseline 包含 app/frontend、app/backend、Julia Runner、desktop、docs 五條驗證線。
- migration phases 需搭配 Phase Gates、Task Scope Sizing 與 Codex subagent coordination rules 驗收。
