"""rewrite task snapshot baseline

Revision ID: 20260312_0002
Revises: 20260312_0001
Create Date: 2026-03-12 20:15:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20260312_0002"
down_revision: str | None = "20260312_0001"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "rewrite_task_records",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("task_id", sa.Integer(), nullable=False),
        sa.Column("kind", sa.String(length=32), nullable=False),
        sa.Column("lane", sa.String(length=32), nullable=False),
        sa.Column("execution_mode", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("submitted_at", sa.String(length=32), nullable=False),
        sa.Column("owner_user_id", sa.String(length=64), nullable=False),
        sa.Column("owner_display_name", sa.String(length=128), nullable=False),
        sa.Column("workspace_id", sa.String(length=64), nullable=False),
        sa.Column("workspace_slug", sa.String(length=64), nullable=False),
        sa.Column("visibility_scope", sa.String(length=32), nullable=False),
        sa.Column("dataset_id", sa.String(length=128), nullable=True),
        sa.Column("definition_id", sa.Integer(), nullable=True),
        sa.Column("summary", sa.String(length=255), nullable=False),
        sa.Column("queue_backend", sa.String(length=64), nullable=False),
        sa.Column("worker_task_name", sa.String(length=64), nullable=False),
        sa.Column("request_ready", sa.Boolean(), nullable=False),
        sa.Column("submitted_from_active_dataset", sa.Boolean(), nullable=False),
        sa.Column("progress_phase", sa.String(length=32), nullable=False),
        sa.Column("progress_percent_complete", sa.Integer(), nullable=False),
        sa.Column("progress_summary", sa.String(length=255), nullable=False),
        sa.Column("progress_updated_at", sa.String(length=32), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_rewrite_task_records_task_id",
        "rewrite_task_records",
        ["task_id"],
        unique=True,
    )
    op.create_index(
        "ix_rewrite_task_records_workspace_id",
        "rewrite_task_records",
        ["workspace_id"],
        unique=False,
    )
    op.create_index(
        "ix_rewrite_task_records_status",
        "rewrite_task_records",
        ["status"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_rewrite_task_records_status", table_name="rewrite_task_records")
    op.drop_index("ix_rewrite_task_records_workspace_id", table_name="rewrite_task_records")
    op.drop_index("ix_rewrite_task_records_task_id", table_name="rewrite_task_records")
    op.drop_table("rewrite_task_records")
