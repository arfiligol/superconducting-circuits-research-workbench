from collections.abc import Callable
from dataclasses import dataclass
from functools import lru_cache
from typing import Any

from src.app.infrastructure.audit_store import (
    SqliteAuditLogRepository,
    bootstrap_audit_store,
    create_audit_session_factory,
)
from src.app.infrastructure.casbin_authorization import CasbinAuthorizationAdapter
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
from src.app.infrastructure.request_debug import configure_backend_logging
from src.app.infrastructure.rewrite_app_state_repository import InMemoryRewriteAppStateRepository
from src.app.infrastructure.rewrite_catalog_repository import InMemoryRewriteCatalogRepository
from src.app.infrastructure.rewrite_execution_runtime import RewriteExecutionRuntime
from src.app.infrastructure.rewrite_processor_runtime_repository import (
    RedisProcessorRuntimeRepository,
)
from src.app.infrastructure.rewrite_task_repository import PersistedRewriteTaskRepository
from src.app.infrastructure.session_jwt_transport import SessionJwtTransport
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
from src.app.services.dataset_service import DatasetService
from src.app.services.health_service import HealthService
from src.app.services.schemdraw_render_service import SchemdrawRenderService
from src.app.services.session_service import SessionService
from src.app.services.simulation_result_explorer_service import (
    SimulationResultExplorerService,
)
from src.app.services.task_service import TaskService
from src.app.services.workspace_collaboration_service import WorkspaceCollaborationService
from src.app.settings import get_settings


@dataclass(frozen=True)
class _TaskRuntimeBundle:
    task_service: TaskService
    execution_runtime: RewriteExecutionRuntime
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
def get_rewrite_catalog_repository() -> InMemoryRewriteCatalogRepository:
    return InMemoryRewriteCatalogRepository(
        durable_definition_repository=get_circuit_definition_persistence_repository(),
        durable_publication_repository=get_research_data_publication_repository(),
        durable_characterization_repository=get_persisted_characterization_repository(),
        task_repository=get_rewrite_task_repository(),
    )


@lru_cache(maxsize=1)
def get_rewrite_app_state_repository() -> InMemoryRewriteAppStateRepository:
    return InMemoryRewriteAppStateRepository(
        seed_tasks=False,
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
def get_rewrite_task_repository() -> PersistedRewriteTaskRepository:
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
        task_repository=get_rewrite_task_repository(),
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
def get_dataset_service() -> DatasetService:
    return DatasetService(
        repository=get_rewrite_catalog_repository(),
        session_repository=get_rewrite_app_state_repository(),
        authorization_service=get_authorization_service(),
        audit_repository=get_task_audit_repository(),
    )


@lru_cache(maxsize=1)
def get_circuit_definition_service() -> CircuitDefinitionService:
    return CircuitDefinitionService(
        repository=get_rewrite_catalog_repository(),
        session_repository=get_rewrite_app_state_repository(),
        authorization_service=get_authorization_service(),
        audit_repository=get_task_audit_repository(),
    )


@lru_cache(maxsize=1)
def get_schemdraw_render_service() -> SchemdrawRenderService:
    return SchemdrawRenderService(
        definition_repository=get_rewrite_catalog_repository(),
        session_repository=get_rewrite_app_state_repository(),
    )


@lru_cache(maxsize=1)
def get_session_service() -> SessionService:
    return SessionService(
        repository=get_rewrite_app_state_repository(),
        dataset_repository=get_rewrite_catalog_repository(),
        token_transport=get_session_token_transport(),
        authorization_service=get_authorization_service(),
        audit_repository=get_task_audit_repository(),
        task_repository=get_rewrite_task_repository(),
    )


@lru_cache(maxsize=1)
def get_workspace_collaboration_service() -> WorkspaceCollaborationService:
    return WorkspaceCollaborationService(
        repository=get_rewrite_app_state_repository(),
        session_service=get_session_service(),
        authorization_service=get_authorization_service(),
        delivery_service=WorkspaceInvitationDeliveryService(get_settings()),
        audit_repository=get_task_audit_repository(),
    )


@lru_cache(maxsize=1)
def get_audit_log_service() -> AuditLogService:
    return AuditLogService(
        repository=get_task_audit_repository(),
        session_repository=get_rewrite_app_state_repository(),
        authorization_service=get_authorization_service(),
    )


@lru_cache(maxsize=1)
def _get_task_runtime_bundle() -> _TaskRuntimeBundle:
    task_service = TaskService(
        repository=get_rewrite_task_repository(),
        audit_repository=get_task_audit_repository(),
        processor_summary_repository=get_processor_runtime_repository(),
        session_repository=get_rewrite_app_state_repository(),
        dataset_repository=get_rewrite_catalog_repository(),
        circuit_definition_repository=get_rewrite_catalog_repository(),
        authorization_service=get_authorization_service(),
        queue_dispatcher=get_task_queue_dispatcher(),
    )
    execution_runtime = RewriteExecutionRuntime(
        task_service=task_service,
        task_repository=get_rewrite_task_repository(),
        audit_repository=get_task_audit_repository(),
        processor_runtime_repository=get_processor_runtime_repository(),
    )
    simulation_execution_driver = LocalSimulationExecutionDriver(
        task_repository=get_rewrite_task_repository(),
        circuit_definition_repository=get_rewrite_catalog_repository(),
        execution_runtime_factory=lambda: execution_runtime,
    )
    post_processing_execution_driver = LocalPostProcessingExecutionDriver(
        task_repository=get_rewrite_task_repository(),
        execution_runtime_factory=lambda: execution_runtime,
    )
    characterization_execution_driver = LocalCharacterizationExecutionDriver(
        task_repository=get_rewrite_task_repository(),
        dataset_repository=get_rewrite_catalog_repository(),
        characterization_repository=get_persisted_characterization_repository(),
        execution_runtime_factory=lambda: execution_runtime,
    )
    recovery_service = LocalExecutionRecoveryService(
        task_repository=get_rewrite_task_repository(),
        execution_runtime=execution_runtime,
        processor_repository=get_processor_runtime_repository(),
        queue_dispatcher=get_task_queue_dispatcher(),
    )
    return _TaskRuntimeBundle(
        task_service=task_service,
        execution_runtime=execution_runtime,
        simulation_execution_driver=simulation_execution_driver,
        post_processing_execution_driver=post_processing_execution_driver,
        characterization_execution_driver=characterization_execution_driver,
        queue_dispatcher=get_task_queue_dispatcher(),
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
    return SimulationResultExplorerService(get_task_service())


def get_task_execution_runtime() -> RewriteExecutionRuntime:
    return _get_task_runtime_bundle().execution_runtime


def reset_runtime_state() -> None:
    get_settings.cache_clear()
    get_worker_runtime_settings.cache_clear()
    get_queue_connection_factory.cache_clear()
    get_circuit_definition_persistence_repository.cache_clear()
    get_rewrite_catalog_repository.cache_clear()
    get_rewrite_app_state_repository.cache_clear()
    get_storage_metadata_repository.cache_clear()
    get_persisted_characterization_repository.cache_clear()
    get_research_data_publication_repository.cache_clear()
    get_task_snapshot_repository.cache_clear()
    get_rewrite_task_repository.cache_clear()
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
