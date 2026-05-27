"""rewrite task dispatch baseline

Revision ID: 20260312_0003
Revises: 20260312_0002
Create Date: 2026-03-12 21:20:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20260312_0003"
down_revision: str | None = "20260312_0002"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "rewrite_task_dispatch_records",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("task_id", sa.Integer(), nullable=False),
        sa.Column("dispatch_key", sa.String(length=128), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("submission_source", sa.String(length=32), nullable=False),
        sa.Column("accepted_at", sa.String(length=32), nullable=False),
        sa.Column("last_updated_at", sa.String(length=32), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["task_id"], ["rewrite_task_records.task_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_rewrite_task_dispatch_records_task_id",
        "rewrite_task_dispatch_records",
        ["task_id"],
        unique=True,
    )
    op.create_index(
        "ix_rewrite_task_dispatch_records_dispatch_key",
        "rewrite_task_dispatch_records",
        ["dispatch_key"],
        unique=True,
    )
    op.create_index(
        "ix_rewrite_task_dispatch_records_status",
        "rewrite_task_dispatch_records",
        ["status"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_rewrite_task_dispatch_records_status",
        table_name="rewrite_task_dispatch_records",
    )
    op.drop_index(
        "ix_rewrite_task_dispatch_records_dispatch_key",
        table_name="rewrite_task_dispatch_records",
    )
    op.drop_index(
        "ix_rewrite_task_dispatch_records_task_id",
        table_name="rewrite_task_dispatch_records",
    )
    op.drop_table("rewrite_task_dispatch_records")
