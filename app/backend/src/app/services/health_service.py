from src.app.domain.health import HealthStatus


class HealthService:
    def __init__(self, app_name: str, environment: str) -> None:
        self._app_name = app_name
        self._environment = environment

    def get_status(self) -> HealthStatus:
        return HealthStatus(
            status="ok",
            service=self._app_name,
            environment=self._environment,
        )
