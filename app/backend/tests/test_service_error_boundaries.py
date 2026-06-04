import pytest
from app_backend.domain.datasets import CharacterizationTaggingRequest
from app_backend.domain.tasks import TaskSubmissionDraft
from app_backend.infrastructure.casbin_authorization import CasbinAuthorizationAdapter
from app_backend.infrastructure.rewrite_app_state_repository import (
    InMemoryRewriteAppStateRepository,
)
from app_backend.infrastructure.rewrite_catalog_repository import InMemoryRewriteCatalogRepository
from app_backend.infrastructure.session_jwt_transport import SessionJwtTransport
from app_backend.services.authorization_service import AuthorizationService
from app_backend.services.circuit_definition_service import CircuitDefinitionService
from app_backend.services.dataset_catalog_service import DatasetCatalogService
from app_backend.services.dataset_characterization_service import (
    DatasetCharacterizationService,
)
from app_backend.services.dataset_service import DatasetService
from app_backend.services.dataset_trace_service import DatasetTraceService
from app_backend.services.result_trace_publication_service import (
    ResultTracePublicationService,
)
from app_backend.services.service_errors import ServiceError
from app_backend.services.session_mutation_service import SessionMutationService
from app_backend.services.session_projection_service import SessionProjectionService
from app_backend.services.session_service import SessionService
from app_backend.services.simulation_result_publication_service import (
    SimulationResultPublicationService,
)
from app_backend.services.task_control_service import TaskControlService
from app_backend.services.task_mutation_service import TaskMutationService
from app_backend.services.task_publication_service import TaskPublicationService
from app_backend.services.task_service import TaskService
from app_backend.services.task_submission_service import TaskSubmissionService
from fastapi import HTTPException


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


def _build_session_service(
    repository: InMemoryRewriteAppStateRepository,
    dataset_repository: InMemoryRewriteCatalogRepository,
    *,
    token_transport: SessionJwtTransport | None = None,
) -> SessionService:
    resolved_transport = token_transport or SessionJwtTransport(secret="test-session-secret-2026")
    authorization_service = AuthorizationService(CasbinAuthorizationAdapter())
    projection_service = SessionProjectionService(
        repository=repository,
        dataset_repository=dataset_repository,
        token_transport=resolved_transport,
        authorization_service=authorization_service,
    )
    return SessionService(
        repository=repository,
        dataset_repository=dataset_repository,
        token_transport=resolved_transport,
        projection_service=projection_service,
        mutation_service=SessionMutationService(
            repository=repository,
            dataset_repository=dataset_repository,
            token_transport=resolved_transport,
            authorization_service=authorization_service,
            projection_service=projection_service,
        ),
    )


def _build_dataset_service(
    app_state_repository: InMemoryRewriteAppStateRepository,
    catalog_repository: InMemoryRewriteCatalogRepository,
) -> DatasetService:
    return DatasetService(
        catalog_service=DatasetCatalogService(
            repository=catalog_repository,
            session_repository=app_state_repository,
        ),
        trace_service=DatasetTraceService(
            repository=catalog_repository,
            session_repository=app_state_repository,
        ),
        characterization_service=DatasetCharacterizationService(
            repository=catalog_repository,
            session_repository=app_state_repository,
        ),
    )


def _build_task_service(
    app_state_repository: InMemoryRewriteAppStateRepository,
    catalog_repository: InMemoryRewriteCatalogRepository,
) -> TaskService:
    return TaskService(
        repository=app_state_repository,
        session_repository=app_state_repository,
        dataset_repository=catalog_repository,
        circuit_definition_repository=catalog_repository,
        mutation_service=TaskMutationService(
            submission_service=TaskSubmissionService(
                repository=app_state_repository,
                session_repository=app_state_repository,
                dataset_repository=catalog_repository,
                circuit_definition_repository=catalog_repository,
            ),
            control_service=TaskControlService(
                repository=app_state_repository,
                session_repository=app_state_repository,
            ),
        ),
        publication_service=TaskPublicationService(
            simulation_result_service=SimulationResultPublicationService(
                repository=app_state_repository,
                dataset_repository=catalog_repository,
                session_repository=app_state_repository,
            ),
            result_trace_service=ResultTracePublicationService(
                repository=app_state_repository,
                dataset_repository=catalog_repository,
                session_repository=app_state_repository,
            ),
        ),
    )


def test_dataset_service_raises_framework_agnostic_error_for_missing_dataset() -> None:
    app_state_repository = InMemoryRewriteAppStateRepository()
    service = _build_dataset_service(
        app_state_repository,
        InMemoryRewriteCatalogRepository(),
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
    service = _build_dataset_service(
        app_state_repository,
        InMemoryRewriteCatalogRepository(),
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
    service = _build_dataset_service(
        app_state_repository,
        InMemoryRewriteCatalogRepository(),
    )

    with pytest.raises(ServiceError) as exc_info:
        service.apply_characterization_tagging(
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
    repository = InMemoryRewriteAppStateRepository()
    repository.switch_runtime_mode(
        runtime_mode="online",
        server_target_origin="http://127.0.0.1:8000",
    )
    token_transport = SessionJwtTransport(secret="test-session-secret-2026")
    service = _build_session_service(
        repository,
        InMemoryRewriteCatalogRepository(),
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
    service = _build_task_service(app_state_repository, catalog_repository)

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
