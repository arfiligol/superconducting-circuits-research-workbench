from fastapi import FastAPI

from app_backend.api.errors import install_error_handlers
from app_backend.api.router import api_router
from app_backend.infrastructure.request_debug import configure_backend_logging
from app_backend.infrastructure.request_debug_middleware import install_request_debug_middleware
from app_backend.infrastructure.request_session_middleware import install_request_session_middleware
from app_backend.infrastructure.runtime import (
    get_app_state_repository,
    get_session_token_transport,
)
from app_backend.infrastructure.secret_management import validate_secret_management_baseline
from app_backend.settings import AppSettings, get_settings


def create_application(settings: AppSettings | None = None) -> FastAPI:
    app_settings = settings or get_settings()
    validate_secret_management_baseline(app_settings)
    configure_backend_logging()
    app = FastAPI(
        title=app_settings.app_name,
        version=app_settings.app_version,
        docs_url="/docs",
        redoc_url="/redoc",
    )
    install_request_debug_middleware(app)
    install_request_session_middleware(
        app,
        session_repository_factory=get_app_state_repository,
        token_transport_factory=get_session_token_transport,
    )
    install_error_handlers(app)
    app.include_router(api_router)
    return app


app = create_application()
