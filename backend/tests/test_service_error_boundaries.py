import pytest
from fastapi import HTTPException
from src.app.domain.datasets import CharacterizationTaggingRequest
from src.app.domain.tasks import TaskSubmissionDraft
from src.app.infrastructure.rewrite_app_state_repository import InMemoryRewriteAppStateRepository
from src.app.infrastructure.rewrite_catalog_repository import InMemoryRewriteCatalogRepository
from src.app.infrastructure.session_jwt_transport import SessionJwtTransport
from src.app.services.circuit_definition_service import CircuitDefinitionService
from src.app.services.dataset_service import DatasetService
from src.app.services.service_errors import ServiceError
from src.app.services.session_service import SessionService
from src.app.services.task_service import TaskService


def _enter_online_owner_session(repository: InMemoryRewriteAppStateRepository) -> None:
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
    app_state_repository = InMemoryRewriteAppStateRepository()
    service = DatasetService(
        repository=InMemoryRewriteCatalogRepository(),
        session_repository=app_state_repository,
    )

    with pytest.raises(ServiceError) as exc_info:
        service.get_dataset_profile("missing-dataset")

    assert not isinstance(exc_info.value, HTTPException)
    assert exc_info.value.status_code == 404
    assert exc_info.value.code == "dataset_not_found"
    assert exc_info.value.category == "not_found"


def test_dataset_service_raises_framework_agnostic_error_for_missing_characterization_result() -> (
    None
):
    app_state_repository = InMemoryRewriteAppStateRepository()
    _enter_online_owner_session(app_state_repository)
    service = DatasetService(
        repository=InMemoryRewriteCatalogRepository(),
        session_repository=app_state_repository,
    )

    with pytest.raises(ServiceError) as exc_info:
        service.get_characterization_result(
            "fluxonium-2025-031",
            "design_flux_scan_a",
            "missing-result",
        )

    assert not isinstance(exc_info.value, HTTPException)
    assert exc_info.value.status_code == 404
    assert exc_info.value.code == "run_not_found"
    assert exc_info.value.category == "not_found"


def test_dataset_service_raises_conflict_for_characterization_tagging_collision() -> None:
    app_state_repository = InMemoryRewriteAppStateRepository()
    _enter_online_owner_session(app_state_repository)
    service = DatasetService(
        repository=InMemoryRewriteCatalogRepository(),
        session_repository=app_state_repository,
    )

    with pytest.raises(ServiceError) as exc_info:
        service.apply_characterization_tagging(
            "fluxonium-2025-031",
            "design_flux_scan_a",
            "char-fit-flux-a-01",
            CharacterizationTaggingRequest(
                artifact_id="artifact-fit-table-flux-a-01",
                source_parameter="EJ_fit",
                designated_metric="f01",
            ),
        )

    assert not isinstance(exc_info.value, HTTPException)
    assert exc_info.value.status_code == 409
    assert exc_info.value.code == "tagging_conflict"
    assert exc_info.value.category == "conflict"


def test_session_service_raises_framework_agnostic_error_for_missing_active_dataset() -> None:
    repository = InMemoryRewriteAppStateRepository()
    repository.switch_runtime_mode(
        runtime_mode="online",
        server_target_origin="http://127.0.0.1:8000",
    )
    token_transport = SessionJwtTransport(secret="test-session-secret-2026")
    service = SessionService(
        repository=repository,
        dataset_repository=InMemoryRewriteCatalogRepository(),
        token_transport=token_transport,
    )
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
    app_state_repository = InMemoryRewriteAppStateRepository()
    catalog_repository = InMemoryRewriteCatalogRepository()
    service = TaskService(
        repository=app_state_repository,
        session_repository=app_state_repository,
        dataset_repository=catalog_repository,
        circuit_definition_repository=catalog_repository,
    )

    with pytest.raises(ServiceError) as exc_info:
        service.submit_task(
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
    app_state_repository = InMemoryRewriteAppStateRepository(seed_tasks=False)
    service = CircuitDefinitionService(
        repository=InMemoryRewriteCatalogRepository(),
        session_repository=app_state_repository,
    )

    with pytest.raises(ServiceError) as exc_info:
        service.get_circuit_definition(999)

    assert not isinstance(exc_info.value, HTTPException)
    assert exc_info.value.status_code == 404
    assert exc_info.value.code == "definition_not_found"
    assert exc_info.value.category == "not_found"
