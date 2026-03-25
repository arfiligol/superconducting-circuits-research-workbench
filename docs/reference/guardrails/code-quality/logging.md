---
aliases:
  - "Logging Rules"
  - "日誌規範"
tags:
  - audience/team
  - sot/true
status: stable
owner: docs-team
audience: team
scope: "日誌記錄規範：分級、顏色、使用方式"
version: v1.1.1
last_updated: 2026-03-25
updated_by: codex
---

# Logging Standards

本專案使用 Python 標準 `logging` 模組搭配 **Rich** 進行彩色輸出。

!!! info "Use this page for runtime logging"
    這頁管的是開發與執行期 logging，不是 app-level audit logging。需要 actor/action/resource 的治理記錄時，應看 `App > Shared / Audit Logging`。
    若要區分 audit logging、workflow observability 與 product telemetry 的責任，應看 `App > Shared / Observability Model`。

## Logging Map

| 問題 | 應看哪裡 |
| --- | --- |
| 哪裡可以 `print()`？ | `core/` 與 `scripts/` 的邊界 |
| 什麼時候用 `info` / `warning` / `error`？ | 日誌等級表 |
| CLI 如何顯示彩色 logging？ | `setup_logging` + `RichHandler` |

## 原則

1. **`core/` 層禁止 `print()`** - 只有 `scripts/` 層可以直接輸出
2. **所有 `core/` 層使用 `logging`** - 讓呼叫者決定如何處理日誌
3. **彩色分級** - 使用 Rich 的 Console 輸出
4. **Rich 為標準日誌輸出** - CLI 必須使用 `RichHandler`

## 日誌等級

| Level | 用途 | 顏色 |
|-------|------|------|
| `DEBUG` | 開發調試資訊 | 灰色 |
| `INFO` | 正常流程資訊 | 綠色 |
| `WARNING` | 潛在問題 | 黃色 |
| `ERROR` | 錯誤但可繼續 | 紅色 |
| `CRITICAL` | 嚴重錯誤 | 粗體紅色 |

!!! warning "Message formatting rule"
    logging 呼叫一律使用參數化格式，例如 `logger.info("Value: %s", value)`；不要用 f-string 先把訊息展開。

## 使用方式

=== "在 `core/` 層"

    ```python
    import logging

    logger = logging.getLogger(__name__)

    def process_data(path: Path) -> Result:
        logger.info("Processing %s", path.name)

        if not path.exists():
            logger.warning("File not found: %s", path)
            return None

        try:
            result = do_something()
            logger.debug("Result: %s", result)
            return result
        except ValueError as e:
            logger.error("Failed to process: %s", e)
            raise
    ```

=== "在 `scripts/` 層 (CLI Entry Point)"

    ```python
    from core.shared.logging import setup_logging

    def main() -> None:
        setup_logging(level="INFO")  # 或 DEBUG for verbose

        # 現在所有 core/ 層的 logging 會顯示彩色輸出
        result = process_data(path)

        # CLI 層可以用 print() 做最終輸出
        print(f"Result: {result}")
    ```

## 配置

### 預設 Logger Setup (`core/shared/logging.py`)

```python
from rich.logging import RichHandler

def setup_logging(level: str = "INFO") -> None:
    logging.basicConfig(
        level=level,
        format="%(message)s",
        handlers=[RichHandler(rich_tracebacks=True)]
    )
```

## 遷移指南

將現有 `print()` 替換為 `logging`：

| 原本 | 替換為 |
|------|--------|
| `print(f"[Info] ...")` | `logger.info("...")` |
| `print(f"[Warning] ...")` | `logger.warning("...")` |
| `print(f"[Error] ...")` | `logger.error("...")` |
| `print(f"[OK] ...")` | `logger.info("...")` |

??? note "Why this page stays simple"
    logging 規則故意保持薄層：先把 `print()` 邊界、level 語意、CLI handler 定清楚，再由各子系統決定具體欄位與 correlation data。

---

## Agent Rule { #agent-rule }

```markdown
## Logging
- **No `print()` in `core/`**: Use `logging` module only.
- **`print()` allowed ONLY in `scripts/`**: For final CLI output.
- **Setup**:
    - Import: `import logging; logger = logging.getLogger(__name__)`
    - Configure in CLI: `from core.shared.logging import setup_logging`
    - **Handler**: Use `RichHandler` for colored output in CLI.
- **Levels**:
    - `logger.debug()`: Development details.
    - `logger.info()`: Normal flow (e.g., "Processing file...").
    - `logger.warning()`: Potential issues (e.g., "File not found").
    - `logger.error()`: Errors that allow continuation.
    - `logger.critical()`: Fatal errors.
- **Never**: Use f-string in logger. Use `logger.info("Value: %s", value)`.
```
