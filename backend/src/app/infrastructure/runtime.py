from collections.abc import Callable
from dataclasses import dataclass
from functools import lru_cache
from typing import Any

from src.app.infrastructure.app_state_repository import AppStateRepository
from src.app.infrastructure.audit_store import (
    SqliteAuditLogRepository,
    bootstrap_audit_store,
    create_audit_session_factory,
)
from src.app.infrastructure.casbin_authorization import CasbinAuthorizationAdapter
from src.app.infrastructure.durable_catalog_repository import DurableCatalogRepository
from src.app.infrastructure.invitation_delivery import WorkspaceInvitationDeliveryService
from src.app.infrastructure.local_simulation_execution_driver import (
    LocalCharacterizationExecutionDriver,
    LocalPostProcessingExecutionDriver,
    LocalSimulationExecutionDriver,
)
from src.app.infrastructure.persisted_characterization_runtime import (
    PersistedCharacterizationRepository,
)
from src.app.infrastructure.persistence import (
    SqliteCircuitDefinitionRepository,
    SqliteResearchDataPublicationRepository,
    SqliteRewriteStorageMetadataRepository,
    SqliteRewriteTaskSnapshotRepository,
    bootstrap_metadata_schema,
    create_metadata_session_factory,
)
from src.app.infrastructure.processor_runtime_repository import (
    RedisProcessorRuntimeRepository,
)
from src.app.infrastructure.request_debug import configure_backend_logging
from src.app.infrastructure.rewrite_task_repository import PersistedRewriteTaskRepository
from src.app.infrastructure.session_jwt_transport import SessionJwtTransport
from src.app.infrastructure.task_execution_runtime import TaskExecutionRuntime
from src.app.infrastructure.trace_store_axis_value_loader import (
    TraceStoreAxisValueLoader,
)
from src.app.infrastructure.worker_runtime.dispatcher import (
    LocalTaskQueueDispatcher,
)
from src.app.infrastructure.worker_runtime.recovery import (
    LocalExecutionRecoveryService,
)
from src.app.infrastructure.worker_runtime.redis_connection import (
    build_queue_connection_factory,
)
from src.app.infrastructure.worker_runtime.settings import (
    WorkerRuntimeSettings,
    build_worker_runtime_settings,
)
from src.app.services.audit_log_service import AuditLogService
from src.app.services.authorization_service import AuthorizationService
from src.app.services.circuit_definition_service import CircuitDefinitionService
from src.app.services.dataset_catalog_service import DatasetCatalogService
from src.app.services.dataset_characterization_service import (
    DatasetCharacterizationService,
)
from src.app.services.dataset_service import DatasetService
from src.app.services.dataset_trace_service import DatasetTraceService
from src.app.services.health_service import HealthService
from src.app.services.result_trace_publication_service import (
    ResultTracePublicationService,
)
from src.app.services.schemdraw_render_service import SchemdrawRenderService
from src.app.services.session_mutation_service import SessionMutationService
from src.app.services.session_projection_service import SessionProjectionService
from src.app.services.session_service import SessionService
from src.app.services.simulation_result_explorer_query_service import (
    SimulationResultExplorerQueryService,
)
from src.app.services.simulation_result_explorer_service import (
    SimulationResultExplorerService,
)
from src.app.services.simulation_result_explorer_view_service import (
    SimulationResultExplorerViewService,
)
from src.app.services.simulation_result_publication_service import (
    SimulationResultPublicationService,
)
from src.app.services.task_control_service import TaskControlService
from src.app.services.task_mutation_service import TaskMutationService
from src.app.services.task_publication_service import TaskPublicationService
from src.app.services.task_service import TaskService
from src.app.services.task_submission_service import TaskSubmissionService
from src.app.services.trace_collection_service import TraceCollectionService
from src.app.services.workspace_collaboration_service import WorkspaceCollaborationService
from src.app.services.workspace_invitation_service import WorkspaceInvitationService
from src.app.services.workspace_membership_service import WorkspaceMembershipService
from src.app.settings import get_settings


@dataclass(frozen=True)
class _TaskRuntimeBundle:
    task_service: TaskService
    execution_runtime: TaskExecutionRuntime
    simulation_execution_driver: LocalSimulationExecutionDriver
    post_processing_execution_driver: LocalPostProcessingExecutionDriver
    characterization_execution_driver: LocalCharacterizationExecutionDriver
    queue_dispatcher: LocalTaskQueueDispatcher
    recovery_service: LocalExecutionRecoveryService


@lru_cache(maxsize=1)
def get_worker_runtime_settings() -> WorkerRuntimeSettings:
    return build_worker_runtime_settings(get_settings())


@lru_cache(maxsize=1)
def get_queue_connection_factory() -> Callable[[], Any]:
    return build_queue_connection_factory(get_worker_runtime_settings().redis_url)


@lru_cache(maxsize=1)
def get_research_data_publication_repository() -> SqliteResearchDataPublicationRepository:
    settings = get_settings()
    bootstrap_metadata_schema(settings.database_path)
    return SqliteResearchDataPublicationRepository(
        create_metadata_session_factory(settings.database_path),
        get_storage_metadata_repository(),
    )


@lru_cache(maxsize=1)
def get_circuit_definition_persistence_repository() -> SqliteCircuitDefinitionRepository:
    settings = get_settings()
    bootstrap_metadata_schema(settings.database_path)
    return SqliteCircuitDefinitionRepository(
        create_metadata_session_factory(settings.database_path)
    )


@lru_cache(maxsize=1)
def get_catalog_repository() -> DurableCatalogRepository:
    settings = get_settings()
    bootstrap_metadata_schema(settings.database_path)
    return DurableCatalogRepository(
        session_factory=create_metadata_session_factory(settings.database_path),
        storage_metadata_repository=get_storage_metadata_repository(),
        publication_repository=get_research_data_publication_repository(),
        characterization_repository=get_persisted_characterization_repository(),
        circuit_definition_repository=get_circuit_definition_persistence_repository(),
        task_repository=get_task_repository(),
    )


@lru_cache(maxsize=1)
def get_app_state_repository() -> AppStateRepository:
    settings = get_settings()
    bootstrap_metadata_schema(settings.database_path)
    return AppStateRepository(
        create_metadata_session_factory(settings.database_path)
    )


@lru_cache(maxsize=1)
def get_storage_metadata_repository() -> SqliteRewriteStorageMetadataRepository:
    settings = get_settings()
    bootstrap_metadata_schema(settings.database_path)
    return SqliteRewriteStorageMetadataRepository(
        create_metadata_session_factory(settings.database_path)
    )


@lru_cache(maxsize=1)
def get_persisted_characterization_repository() -> PersistedCharacterizationRepository:
    return PersistedCharacterizationRepository(get_storage_metadata_repository())


@lru_cache(maxsize=1)
def get_task_snapshot_repository() -> SqliteRewriteTaskSnapshotRepository:
    settings = get_settings()
    bootstrap_metadata_schema(settings.database_path)
    return SqliteRewriteTaskSnapshotRepository(
        create_metadata_session_factory(settings.database_path)
    )


@lru_cache(maxsize=1)
def get_task_repository() -> PersistedRewriteTaskRepository:
    return PersistedRewriteTaskRepository(
        task_snapshot_repository=get_task_snapshot_repository(),
        storage_metadata_repository=get_storage_metadata_repository(),
    )


@lru_cache(maxsize=1)
def get_task_audit_repository() -> SqliteAuditLogRepository:
    settings = get_settings()
    bootstrap_audit_store(settings.audit_database_path)
    return SqliteAuditLogRepository(create_audit_session_factory(settings.audit_database_path))


@lru_cache(maxsize=1)
def get_processor_runtime_repository() -> RedisProcessorRuntimeRepository:
    return RedisProcessorRuntimeRepository(
        task_repository=get_task_repository(),
        settings=get_worker_runtime_settings(),
        connection_factory=get_queue_connection_factory(),
    )


@lru_cache(maxsize=1)
def get_task_queue_dispatcher() -> LocalTaskQueueDispatcher:
    return LocalTaskQueueDispatcher(
        settings=get_worker_runtime_settings(),
        connection_factory=get_queue_connection_factory(),
    )


def get_health_service() -> HealthService:
    configure_backend_logging()
    settings = get_settings()
    return HealthService(
        app_name=settings.app_name,
        environment=settings.environment,
    )


@lru_cache(maxsize=1)
def get_authorization_service() -> AuthorizationService:
    return AuthorizationService(CasbinAuthorizationAdapter())


@lru_cache(maxsize=1)
def get_session_token_transport() -> SessionJwtTransport:
    settings = get_settings()
    return SessionJwtTransport(
        secret=settings.session_secret.get_secret_value(),
    )


@lru_cache(maxsize=1)
def get_trace_collection_service() -> TraceCollectionService:
    return TraceCollectionService(
        axis_value_loader=TraceStoreAxisValueLoader(),
    )


@lru_cache(maxsize=1)
def get_dataset_service() -> DatasetService:
    catalog_repository = get_catalog_repository()
    session_repository = get_app_state_repository()
    authorization_service = get_authorization_service()
    audit_repository = get_task_audit_repository()
    return DatasetService(
        catalog_service=DatasetCatalogService(
            repository=catalog_repository,
            session_repository=session_repository,
            authorization_service=authorization_service,
            audit_repository=audit_repository,
        ),
        trace_service=DatasetTraceService(
            repository=catalog_repository,
            session_repository=session_repository,
            authorization_service=authorization_service,
            audit_repository=audit_repository,
        ),
        characterization_service=DatasetCharacterizationService(
            repository=catalog_repository,
            session_repository=session_repository,
            authorization_service=authorization_service,
            trace_collection_service=get_trace_collection_service(),
        ),
    )


@lru_cache(maxsize=1)
def get_circuit_definition_service() -> CircuitDefinitionService:
    return CircuitDefinitionService(
        repository=get_circuit_definition_persistence_repository(),
        session_repository=get_app_state_repository(),
        authorization_service=get_authorization_service(),
        audit_repository=get_task_audit_repository(),
    )


@lru_cache(maxsize=1)
def get_schemdraw_render_service() -> SchemdrawRenderService:
    return SchemdrawRenderService(
        definition_repository=get_circuit_definition_persistence_repository(),
        session_repository=get_app_state_repository(),
    )


@lru_cache(maxsize=1)
def get_session_service() -> SessionService:
    repository = get_app_state_repository()
    dataset_repository = get_catalog_repository()
    token_transport = get_session_token_transport()
    authorization_service = get_authorization_service()
    audit_repository = get_task_audit_repository()
    task_repository = get_task_repository()
    projection_service = SessionProjectionService(
        repository=repository,
        dataset_repository=dataset_repository,
        token_transport=token_transport,
        authorization_service=authorization_service,
        task_repository=task_repository,
    )
    return SessionService(
        repository=repository,
        dataset_repository=dataset_repository,
        token_transport=token_transport,
        projection_service=projection_service,
        mutation_service=SessionMutationService(
            repository=repository,
            dataset_repository=dataset_repository,
            token_transport=token_transport,
            authorization_service=authorization_service,
            projection_service=projection_service,
            audit_repository=audit_repository,
        ),
        audit_repository=audit_repository,
        task_repository=task_repository,
    )


@lru_cache(maxsize=1)
def get_workspace_collaboration_service() -> WorkspaceCollaborationService:
    repository = get_app_state_repository()
    session_service = get_session_service()
    authorization_service = get_authorization_service()
    audit_repository = get_task_audit_repository()
    return WorkspaceCollaborationService(
        invitation_service=WorkspaceInvitationService(
            repository=repository,
            session_service=session_service,
            authorization_service=authorization_service,
            delivery_service=WorkspaceInvitationDeliveryService(get_settings()),
            audit_repository=audit_repository,
        ),
        membership_service=WorkspaceMembershipService(
            repository=repository,
            session_service=session_service,
            authorization_service=authorization_service,
            audit_repository=audit_repository,
        ),
    )


@lru_cache(maxsize=1)
def get_audit_log_service() -> AuditLogService:
    return AuditLogService(
        repository=get_task_audit_repository(),
        session_repository=get_app_state_repository(),
        authorization_service=get_authorization_service(),
    )


@lru_cache(maxsize=1)
def _get_task_runtime_bundle() -> _TaskRuntimeBundle:
    task_repository = get_task_repository()
    session_repository = get_app_state_repository()
    dataset_repository = get_catalog_repository()
    circuit_definition_repository = get_circuit_definition_persistence_repository()
    authorization_service = get_authorization_service()
    audit_repository = get_task_audit_repository()
    queue_dispatcher = get_task_queue_dispatcher()
    mutation_service = TaskMutationService(
        submission_service=TaskSubmissionService(
            repository=task_repository,
            session_repository=session_repository,
            dataset_repository=dataset_repository,
            circuit_definition_repository=circuit_definition_repository,
            authorization_service=authorization_service,
            audit_repository=audit_repository,
            queue_dispatcher=queue_dispatcher,
            trace_collection_service=get_trace_collection_service(),
        ),
        control_service=TaskControlService(
            repository=task_repository,
            session_repository=session_repository,
            authorization_service=authorization_service,
            audit_repository=audit_repository,
            queue_dispatcher=queue_dispatcher,
        ),
    )
    publication_service = TaskPublicationService(
        simulation_result_service=SimulationResultPublicationService(
            repository=task_repository,
            dataset_repository=dataset_repository,
            session_repository=session_repository,
            authorization_service=authorization_service,
            audit_repository=audit_repository,
        ),
        result_trace_service=ResultTracePublicationService(
            repository=task_repository,
            dataset_repository=dataset_repository,
            session_repository=session_repository,
            authorization_service=authorization_service,
            audit_repository=audit_repository,
        ),
    )
    task_service = TaskService(
        repository=task_repository,
        processor_summary_repository=get_processor_runtime_repository(),
        session_repository=session_repository,
        dataset_repository=dataset_repository,
        circuit_definition_repository=circuit_definition_repository,
        mutation_service=mutation_service,
        publication_service=publication_service,
        authorization_service=authorization_service,
    )
    execution_runtime = TaskExecutionRuntime(
        task_service=task_service,
        task_repository=task_repository,
        audit_repository=audit_repository,
        processor_runtime_repository=get_processor_runtime_repository(),
    )
    simulation_execution_driver = LocalSimulationExecutionDriver(
        task_repository=task_repository,
        circuit_definition_repository=circuit_definition_repository,
        execution_runtime_factory=lambda: execution_runtime,
    )
    post_processing_execution_driver = LocalPostProcessingExecutionDriver(
        task_repository=task_repository,
        execution_runtime_factory=lambda: execution_runtime,
    )
    characterization_execution_driver = LocalCharacterizationExecutionDriver(
        task_repository=task_repository,
        dataset_repository=dataset_repository,
        characterization_repository=get_persisted_characterization_repository(),
        execution_runtime_factory=lambda: execution_runtime,
    )
    recovery_service = LocalExecutionRecoveryService(
        task_repository=task_repository,
        execution_runtime=execution_runtime,
        processor_repository=get_processor_runtime_repository(),
        queue_dispatcher=queue_dispatcher,
    )
    return _TaskRuntimeBundle(
        task_service=task_service,
        execution_runtime=execution_runtime,
        simulation_execution_driver=simulation_execution_driver,
        post_processing_execution_driver=post_processing_execution_driver,
        characterization_execution_driver=characterization_execution_driver,
        queue_dispatcher=queue_dispatcher,
        recovery_service=recovery_service,
    )


def get_simulation_execution_driver() -> LocalSimulationExecutionDriver:
    return _get_task_runtime_bundle().simulation_execution_driver


def get_post_processing_execution_driver() -> LocalPostProcessingExecutionDriver:
    return _get_task_runtime_bundle().post_processing_execution_driver


def get_characterization_execution_driver() -> LocalCharacterizationExecutionDriver:
    return _get_task_runtime_bundle().characterization_execution_driver


def get_execution_recovery_service() -> LocalExecutionRecoveryService:
    return _get_task_runtime_bundle().recovery_service


def get_task_service() -> TaskService:
    return _get_task_runtime_bundle().task_service


@lru_cache(maxsize=1)
def get_simulation_result_explorer_service() -> SimulationResultExplorerService:
    task_service = get_task_service()
    return SimulationResultExplorerService(
        query_service=SimulationResultExplorerQueryService(task_service),
        view_service=SimulationResultExplorerViewService(),
    )


def get_task_execution_runtime() -> TaskExecutionRuntime:
    return _get_task_runtime_bundle().execution_runtime


def reset_runtime_state() -> None:
    get_settings.cache_clear()
    get_worker_runtime_settings.cache_clear()
    get_queue_connection_factory.cache_clear()
    get_circuit_definition_persistence_repository.cache_clear()
    get_catalog_repository.cache_clear()
    get_app_state_repository.cache_clear()
    get_storage_metadata_repository.cache_clear()
    get_persisted_characterization_repository.cache_clear()
    get_research_data_publication_repository.cache_clear()
    get_task_snapshot_repository.cache_clear()
    get_task_repository.cache_clear()
    get_task_audit_repository.cache_clear()
    get_processor_runtime_repository.cache_clear()
    get_task_queue_dispatcher.cache_clear()
    get_dataset_service.cache_clear()
    get_authorization_service.cache_clear()
    get_session_token_transport.cache_clear()
    get_circuit_definition_service.cache_clear()
    get_schemdraw_render_service.cache_clear()
    get_session_service.cache_clear()
    get_workspace_collaboration_service.cache_clear()
    get_audit_log_service.cache_clear()
    _get_task_runtime_bundle.cache_clear()
    get_simulation_result_explorer_service.cache_clear()
