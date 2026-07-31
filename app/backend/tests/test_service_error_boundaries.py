import pytest
from app_backend.domain.datasets import CharacterizationTaggingRequest
from app_backend.domain.tasks import TaskSubmissionDraft
from app_backend.infrastructure.app_state_repository import AppStateRepository
from app_backend.infrastructure.runtime import (
    get_app_state_repository,
    get_circuit_definition_service,
    get_dataset_service,
    get_session_service,
    get_task_service,
)
from app_backend.services.service_errors import ServiceError
from fastapi import HTTPException


def _enter_online_owner_session(repository: AppStateRepository) -> None:
    repository.switch_runtime_mode(
        runtime_mode="online",
        server_target_origin="http://127.0.0.1:8000",
    )
    session = repository.create_authenticated_session(
        email="rewrite.local@example.com",
        password="rewrite-local-password",
    )
    assert session is not None


def test_dataset_service_raises_framework_agnostic_error_for_missing_dataset() -> None:
    with pytest.raises(ServiceError) as exc_info:
        get_dataset_service().get_dataset_profile("missing-dataset")

    assert not isinstance(exc_info.value, HTTPException)
    assert exc_info.value.status_code == 404
    assert exc_info.value.code == "dataset_not_found"
    assert exc_info.value.category == "not_found"


def test_dataset_service_raises_framework_agnostic_error_for_missing_characterization_result() -> (
    None
):
    _enter_online_owner_session(get_app_state_repository())

    with pytest.raises(ServiceError) as exc_info:
        get_dataset_service().get_characterization_result(
            "fluxonium-2025-031",
            "design_flux_scan_a",
            "missing-result",
        )

    assert not isinstance(exc_info.value, HTTPException)
    assert exc_info.value.status_code == 404
    assert exc_info.value.code == "run_not_found"
    assert exc_info.value.category == "not_found"


def test_dataset_service_raises_conflict_for_characterization_tagging_collision() -> None:
    _enter_online_owner_session(get_app_state_repository())

    with pytest.raises(ServiceError) as exc_info:
        get_dataset_service().apply_characterization_tagging(
            "fluxonium-2025-031",
            "design_flux_scan_a",
            "char-fit-flux-a-01",
            CharacterizationTaggingRequest(
                artifact_id="char-fit-flux-a-01:identify-summary",
                source_parameter="highest_observed_frequency_ghz",
                designated_metric="lowest_observed_frequency_ghz",
            ),
        )

    assert not isinstance(exc_info.value, HTTPException)
    assert exc_info.value.status_code == 409
    assert exc_info.value.code == "tagging_conflict"
    assert exc_info.value.category == "conflict"


def test_session_service_raises_framework_agnostic_error_for_missing_active_dataset() -> None:
    repository = get_app_state_repository()
    repository.switch_runtime_mode(
        runtime_mode="online",
        server_target_origin="http://127.0.0.1:8000",
    )
    service = get_session_service()
    login_result = service.login(
        email="rewrite.local@example.com",
        password="rewrite-local-password",
    )

    with pytest.raises(ServiceError) as exc_info:
        service.set_active_dataset(login_result.access_token, "missing-dataset")

    assert not isinstance(exc_info.value, HTTPException)
    assert exc_info.value.status_code == 404
    assert exc_info.value.code == "dataset_not_found"


def test_task_service_raises_framework_agnostic_validation_error() -> None:
    with pytest.raises(ServiceError) as exc_info:
        get_task_service().submit_task(
            draft=TaskSubmissionDraft(
                kind="simulation",
                dataset_id=None,
                definition_id=None,
                summary=None,
            )
        )

    assert not isinstance(exc_info.value, HTTPException)
    assert exc_info.value.status_code == 422
    assert exc_info.value.code == "simulation_definition_required"
    assert exc_info.value.category == "validation"


def test_circuit_definition_service_raises_framework_agnostic_error_for_missing_definition() -> (
    None
):
    with pytest.raises(ServiceError) as exc_info:
        get_circuit_definition_service().get_circuit_definition("missing-definition")

    assert not isinstance(exc_info.value, HTTPException)
    assert exc_info.value.status_code == 404
    assert exc_info.value.code == "definition_not_found"
    assert exc_info.value.category == "not_found"
