from functools import lru_cache

from src.app.infrastructure.audit_store import (
    SqliteAuditLogRepository,
    bootstrap_audit_store,
    create_audit_session_factory,
)
from src.app.infrastructure.casbin_authorization import CasbinAuthorizationAdapter
from src.app.infrastructure.invitation_delivery import WorkspaceInvitationDeliveryService
from src.app.infrastructure.persistence import (
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
    InMemoryProcessorRuntimeRepository,
)
from src.app.infrastructure.rewrite_task_repository import PersistedRewriteTaskRepository
from src.app.infrastructure.session_jwt_transport import SessionJwtTransport
from src.app.services.audit_log_service import AuditLogService
from src.app.services.authorization_service import AuthorizationService
from src.app.services.circuit_definition_service import CircuitDefinitionService
from src.app.services.dataset_service import DatasetService
from src.app.services.health_service import HealthService
from src.app.services.schemdraw_render_service import SchemdrawRenderService
from src.app.services.session_service import SessionService
from src.app.services.task_service import TaskService
from src.app.services.workspace_collaboration_service import WorkspaceCollaborationService
from src.app.settings import get_settings


@lru_cache(maxsize=1)
def get_rewrite_catalog_repository() -> InMemoryRewriteCatalogRepository:
    return InMemoryRewriteCatalogRepository()


@lru_cache(maxsize=1)
def get_rewrite_app_state_repository() -> InMemoryRewriteAppStateRepository:
    return InMemoryRewriteAppStateRepository(
        include_task_scaffold=False,
    )


@lru_cache(maxsize=1)
def get_storage_metadata_repository() -> SqliteRewriteStorageMetadataRepository:
    settings = get_settings()
    bootstrap_metadata_schema(settings.database_path)
    return SqliteRewriteStorageMetadataRepository(
        create_metadata_session_factory(settings.database_path)
    )


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
def get_processor_runtime_repository() -> InMemoryProcessorRuntimeRepository:
    return InMemoryProcessorRuntimeRepository(get_rewrite_task_repository())


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
    settings = get_settings()
    return SessionService(
        repository=get_rewrite_app_state_repository(),
        dataset_repository=get_rewrite_catalog_repository(),
        token_transport=SessionJwtTransport(
            secret=settings.session_secret.get_secret_value(),
        ),
        authorization_service=get_authorization_service(),
        audit_repository=get_task_audit_repository(),
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
def get_task_service() -> TaskService:
    return TaskService(
        repository=get_rewrite_task_repository(),
        audit_repository=get_task_audit_repository(),
        processor_summary_repository=get_processor_runtime_repository(),
        session_repository=get_rewrite_app_state_repository(),
        dataset_repository=get_rewrite_catalog_repository(),
        circuit_definition_repository=get_rewrite_catalog_repository(),
        authorization_service=get_authorization_service(),
    )


@lru_cache(maxsize=1)
def get_task_execution_runtime() -> RewriteExecutionRuntime:
    return RewriteExecutionRuntime(
        task_service=get_task_service(),
        task_repository=get_rewrite_task_repository(),
        audit_repository=get_task_audit_repository(),
        processor_runtime_repository=get_processor_runtime_repository(),
    )


def reset_runtime_state() -> None:
    get_settings.cache_clear()
    get_rewrite_catalog_repository.cache_clear()
    get_rewrite_app_state_repository.cache_clear()
    get_storage_metadata_repository.cache_clear()
    get_task_snapshot_repository.cache_clear()
    get_rewrite_task_repository.cache_clear()
    get_task_audit_repository.cache_clear()
    get_processor_runtime_repository.cache_clear()
    get_dataset_service.cache_clear()
    get_authorization_service.cache_clear()
    get_circuit_definition_service.cache_clear()
    get_schemdraw_render_service.cache_clear()
    get_session_service.cache_clear()
    get_workspace_collaboration_service.cache_clear()
    get_audit_log_service.cache_clear()
    get_task_service.cache_clear()
    get_task_execution_runtime.cache_clear()
