from __future__ import annotations

from app_backend.domain.tasks import TaskSubmissionDraft
from app_backend.services.task_control_service import (
    TaskControlHost,
    TaskControlService,
)
from app_backend.services.task_submission_service import TaskSubmissionService


class TaskMutationService:
    def __init__(
        self,
        submission_service: TaskSubmissionService,
        control_service: TaskControlService,
    ) -> None:
        self._submission_service = submission_service
        self._control_service = control_service

    def submit_task(self, draft: TaskSubmissionDraft) -> int:
        return self._submission_service.submit_task(draft)

    def cancel_task(self, task_id: int, *, host: TaskControlHost) -> int:
        return self._control_service.cancel_task(task_id, host=host)

    def terminate_task(self, task_id: int, *, host: TaskControlHost) -> int:
        return self._control_service.terminate_task(task_id, host=host)

    def retry_task(self, task_id: int, *, host: TaskControlHost) -> int:
        return self._control_service.retry_task(task_id, host=host)
