"""WS6 simulation-page client wrappers over the persisted task/result authority."""

from __future__ import annotations

import json
from typing import Any

from nicegui import ui

from legacy.legacy_nicegui_archived.api.schemas import (
    DesignTasksResponse,
    LatestTraceBatchResponse,
    PostProcessingTaskCreateRequest,
    SimulationTaskCreateRequest,
    TaskDispatchResponse,
    TaskResponse,
)


class ApiClientError(RuntimeError):
    """Raised when a same-origin `/api/v1` call returns an error payload."""

    def __init__(self, *, status_code: int, detail: str):
        super().__init__(detail)
        self.status_code = int(status_code)
        self.detail = str(detail)


async def _fetch_json(
    method: str,
    path: str,
    *,
    body: dict[str, Any] | None = None,
    client: Any | None = None,
) -> Any:
    request_body = None if body is None else json.dumps(body, separators=(",", ":"))
    javascript_runner = client.run_javascript if client is not None else ui.run_javascript
    result = await javascript_runner(
        f"""
        const requestBody = {json.dumps(request_body)};
        const response = await fetch({json.dumps(path)}, {{
          method: {json.dumps(method)},
          headers: {{ 'Content-Type': 'application/json' }},
          credentials: 'same-origin',
          body: requestBody ?? undefined,
        }});
        let body = null;
        try {{
          body = await response.json();
        }} catch (_error) {{
          body = null;
        }}
        return {{ status: response.status, body }};
        """,
        timeout=30.0,
    )
    if not isinstance(result, dict):
        raise ApiClientError(status_code=500, detail="Invalid API client result.")
    status_code = int(result.get("status", 500))
    response_body = result.get("body")
    if status_code >= 400:
        detail = "API request failed"
        if isinstance(response_body, dict):
            if isinstance(response_body.get("detail"), str):
                detail = str(response_body["detail"])
            else:
                detail = json.dumps(response_body.get("detail", response_body))
        raise ApiClientError(status_code=status_code, detail=detail)
    return response_body


async def submit_simulation_task(
    payload: SimulationTaskCreateRequest,
    *,
    client: Any | None = None,
) -> TaskDispatchResponse:
    """Submit one real simulation task through the public v1 API."""
    response_body = await _fetch_json(
        "POST",
        "/api/v1/tasks/simulation",
        body=payload.model_dump(mode="json"),
        client=client,
    )
    return TaskDispatchResponse.model_validate(response_body)


async def submit_post_processing_task(
    payload: PostProcessingTaskCreateRequest,
    *,
    client: Any | None = None,
) -> TaskDispatchResponse:
    """Submit one real post-processing task through the public v1 API."""
    response_body = await _fetch_json(
        "POST",
        "/api/v1/tasks/post-processing",
        body=payload.model_dump(mode="json"),
        client=client,
    )
    return TaskDispatchResponse.model_validate(response_body)


async def get_task(task_id: int, *, client: Any | None = None) -> TaskResponse:
    """Fetch one persisted task through the public v1 API."""
    response_body = await _fetch_json("GET", f"/api/v1/tasks/{int(task_id)}", client=client)
    return TaskResponse.model_validate(response_body)


async def get_design_tasks(design_id: int, *, client: Any | None = None) -> DesignTasksResponse:
    """Fetch persisted design tasks through the public v1 API."""
    response_body = await _fetch_json(
        "GET",
        f"/api/v1/designs/{int(design_id)}/tasks",
        client=client,
    )
    return DesignTasksResponse.model_validate(response_body)


async def get_latest_simulation_result(
    design_id: int,
    *,
    client: Any | None = None,
) -> LatestTraceBatchResponse | None:
    """Fetch the latest completed raw simulation batch for one design."""
    try:
        response_body = await _fetch_json(
            "GET",
            f"/api/v1/designs/{int(design_id)}/simulation/latest",
            client=client,
        )
    except ApiClientError as exc:
        if exc.status_code == 404:
            return None
        raise
    return LatestTraceBatchResponse.model_validate(response_body)


async def get_latest_post_processing_result(
    design_id: int,
    *,
    client: Any | None = None,
) -> LatestTraceBatchResponse | None:
    """Fetch the latest completed post-processing batch for one design."""
    try:
        response_body = await _fetch_json(
            "GET",
            f"/api/v1/designs/{int(design_id)}/post-processing/latest",
            client=client,
        )
    except ApiClientError as exc:
        if exc.status_code == 404:
            return None
        raise
    return LatestTraceBatchResponse.model_validate(response_body)
