"""normalize local runtime queue backend and probe execution naming

Revision ID: 20260321_0005
Revises: 20260313_0004
Create Date: 2026-03-21 16:40:00
"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20260321_0005"
down_revision: str | None = "20260313_0004"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        UPDATE rewrite_task_records
        SET queue_backend = 'local_runtime'
        WHERE queue_backend = 'in_memory_scaffold'
        """
    )
    op.execute(
        """
        UPDATE rewrite_task_records
        SET execution_mode = 'probe'
        WHERE execution_mode = 'smoke'
        """
    )
    op.execute(
        """
        UPDATE rewrite_task_records
        SET worker_task_name = REPLACE(worker_task_name, '_smoke_task', '_probe_task')
        WHERE worker_task_name LIKE '%_smoke_task'
        """
    )
    op.execute(
        """
        UPDATE rewrite_task_records
        SET progress_summary = 'Task accepted by the local runtime.'
        WHERE progress_summary = 'Task accepted by rewrite in-memory scaffold.'
        """
    )
    op.execute(
        """
        UPDATE rewrite_task_dispatch_records
        SET dispatch_key = REPLACE(dispatch_key, '_smoke_task', '_probe_task')
        WHERE dispatch_key LIKE '%_smoke_task'
        """
    )


def downgrade() -> None:
    op.execute(
        """
        UPDATE rewrite_task_dispatch_records
        SET dispatch_key = REPLACE(dispatch_key, '_probe_task', '_smoke_task')
        WHERE dispatch_key LIKE '%_probe_task'
        """
    )
    op.execute(
        """
        UPDATE rewrite_task_records
        SET progress_summary = 'Task accepted by rewrite in-memory scaffold.'
        WHERE progress_summary = 'Task accepted by the local runtime.'
        """
    )
    op.execute(
        """
        UPDATE rewrite_task_records
        SET worker_task_name = REPLACE(worker_task_name, '_probe_task', '_smoke_task')
        WHERE worker_task_name LIKE '%_probe_task'
        """
    )
    op.execute(
        """
        UPDATE rewrite_task_records
        SET execution_mode = 'smoke'
        WHERE execution_mode = 'probe'
        """
    )
    op.execute(
        """
        UPDATE rewrite_task_records
        SET queue_backend = 'in_memory_scaffold'
        WHERE queue_backend = 'local_runtime'
        """
    )
