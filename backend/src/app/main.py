from fastapi import FastAPI

from src.app.api.errors import install_error_handlers
from src.app.api.router import api_router
from src.app.infrastructure.request_debug import configure_backend_logging
from src.app.infrastructure.request_debug_middleware import install_request_debug_middleware
from src.app.infrastructure.request_session_middleware import install_request_session_middleware
from src.app.infrastructure.runtime import (
    get_app_state_repository,
    get_session_token_transport,
)
from src.app.infrastructure.secret_management import validate_secret_management_baseline
from src.app.settings import AppSettings, get_settings


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
