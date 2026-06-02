## Error Handling
- Use stable error categories/codes, not only free-form messages.
- Separate user-safe messages from debug/internal details.
- Mark execution/storage/task errors as retryable or non-retryable.
- Do not leak raw adapter internals (paths, SQL fragments, raw exceptions) into public UI/API/Notebook contracts.
- Frontend logic must key off stable error codes, not message text matching.
- Task submission, execution, result attach, and recovery attach failures must have explicit error categories.
