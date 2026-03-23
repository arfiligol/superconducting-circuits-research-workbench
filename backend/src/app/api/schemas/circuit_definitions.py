from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class ValidationNoticeResponse(BaseModel):
    level: Literal["ok", "warning"]
    message: str


class CircuitDefinitionSummaryResponse(BaseModel):
    definition_id: str
    name: str
    created_at: str
    element_count: int
    validation_status: Literal["ok", "warning"]
    preview_artifact_count: int


class CircuitDefinitionValidationSummaryResponse(BaseModel):
    status: Literal["ok", "warning"]
    notice_count: int
    warning_count: int


class CircuitDefinitionDetailResponse(CircuitDefinitionSummaryResponse):
    source_text: str
    normalized_output: str
    validation_notices: list[ValidationNoticeResponse]
    validation_summary: CircuitDefinitionValidationSummaryResponse
    preview_artifacts: list[str]


class CircuitDefinitionCreateRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    name: str = Field(min_length=1)
    source_text: str = Field(min_length=1)


class CircuitDefinitionUpdateRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    name: str = Field(min_length=1)
    source_text: str = Field(min_length=1)


class CircuitDefinitionMutationResponse(BaseModel):
    operation: Literal["created", "updated"]
    definition: CircuitDefinitionDetailResponse
