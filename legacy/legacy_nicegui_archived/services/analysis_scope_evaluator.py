"""Runtime record-scope evaluator for analysis availability/completion."""

from __future__ import annotations

from typing import Any


def get_available_analyses(
    analyses: list[dict[str, Any]],
    records: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Determine which analyses can run under one record index scope."""
    available: list[dict[str, Any]] = []

    for analysis in analyses:
        if analysis.get("scope") != "per_dataset":
            continue

        reqs = analysis.get("requires", {})

        found_match = False
        for record in records:
            match = True
            for key, value in reqs.items():
                if key == "parameter" and isinstance(value, list):
                    if record.get(key) not in value:
                        match = False
                elif record.get(key) != value:
                    match = False

            if match:
                found_match = True
                break

        if found_match:
            available.append(analysis)

    return available


def is_analysis_completed(analysis: dict[str, Any], params: list[Any]) -> bool:
    """Check whether one analysis methods already exist in derived-parameter rows."""
    completed_methods = analysis.get("completed_methods", [])
    if not completed_methods:
        return False
    return any(param.method in completed_methods for param in params)
