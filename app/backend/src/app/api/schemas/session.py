from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class SessionUserResponse(BaseModel):
    user_id: str
    display_name: str
    email: str | None


class SessionAuthResponse(BaseModel):
    state: Literal["authenticated", "anonymous"]
    mode: Literal["development_stub"]
    scopes: list[str]
    can_submit_tasks: bool
    can_manage_datasets: bool


class ActiveDatasetResponse(BaseModel):
    dataset_id: str
    name: str
    family: str
    status: Literal["Ready", "Queued", "Review"]
    owner: str
    access_scope: Literal["workspace", "shared"]


class WorkspaceContextResponse(BaseModel):
    workspace_id: str
    slug: str
    display_name: str
    role: Literal["owner", "member", "viewer"]
    default_task_scope: Literal["workspace", "owned"]
    active_dataset: ActiveDatasetResponse | None


class SessionResponse(BaseModel):
    session_id: str
    auth: SessionAuthResponse
    identity: SessionUserResponse | None
    workspace: WorkspaceContextResponse


class ActiveDatasetUpdateRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    dataset_id: str | None = Field(default=None, min_length=1)
