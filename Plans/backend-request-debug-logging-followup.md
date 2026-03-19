# Backend Request-Debug Logging Follow-up

This note records a backend logging-system issue discovered during Local Mode work.
It is not the active product blocker for the current Local Mode sprint, but it should remain tracked.

## Topic

- Area: `backend request logging / request-debug context`
- Status: `Recorded; non-blocking for Local Mode workflow delivery`
- Recorded: `2026-03-19`

## Observed Issue

- Backend sometimes emitted a logging failure of the form:
  - `ValueError: Formatting field not found in record: 'correlation_id'`
- One observed path was request handling through:
  - [request_debug_middleware.py](/Users/arfiligol/Github/superconducting-circuits-tutorial/backend/src/app/infrastructure/request_debug_middleware.py)
- The formatter expected every log record to contain:
  - `correlation_id`
  - `debug_ref`
- That assumption was not safe for all emitted records.

## Root Cause Summary

- The previous implementation relied on a logging filter to inject request-debug fields.
- In practice, not every record reliably reached the formatter with those fields already present.
- This made the logging pipeline brittle around child loggers / propagated records / handler formatting order.

## Current Local Fix

- A local fix was prepared in:
  - [request_debug.py](/Users/arfiligol/Github/superconducting-circuits-tutorial/backend/src/app/infrastructure/request_debug.py)
  - [test_request_debug_logging.py](/Users/arfiligol/Github/superconducting-circuits-tutorial/backend/tests/test_request_debug_logging.py)
- Direction of the fix:
  - make the formatter itself backfill `correlation_id` and `debug_ref` before formatting
  - keep request-bound values when available
  - fall back to safe `unbound` markers when no request context exists

## Planning Judgement

- This issue does indicate that the backend logging path still needs hardening.
- It does **not** mean the entire logging system is unusable.
- More accurate judgement:
  - audit/debug correlation intent is present
  - the formatter/filter integration was brittle
  - request-debug logging should be treated as a follow-up hardening area after the current Local Mode workflow blockers

## Follow-up Scope

- Verify logging behavior across:
  - app request logs
  - service logs
  - uvicorn / server logs
  - background/runtime logs
- Decide whether request-debug field injection should be owned primarily by:
  - formatter
  - handler filter
  - record factory
  - or a stricter combined strategy
- Add broader regression coverage for mixed logger hierarchies and non-request logs.

## Priority

- Priority: `P2 follow-up`
- Rationale:
  - should be fixed and kept stable
  - but it is not the main blocker for completing the Local Mode research loop
