"""rewrite task event log baseline

Revision ID: 20260313_0004
Revises: 20260312_0003
Create Date: 2026-03-13 09:55:00
"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "20260313_0004"
down_revision = "20260312_0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "rewrite_task_event_records",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("task_id", sa.Integer(), nullable=False),
        sa.Column("event_key", sa.String(length=128), nullable=False),
        sa.Column("event_type", sa.String(length=32), nullable=False),
        sa.Column("level", sa.String(length=16), nullable=False),
        sa.Column("occurred_at", sa.String(length=32), nullable=False),
        sa.Column("message", sa.String(length=255), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.func.current_timestamp(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["task_id"],
            ["rewrite_task_records.task_id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_rewrite_task_event_records_task_id",
        "rewrite_task_event_records",
        ["task_id"],
        unique=False,
    )
    op.create_index(
        "ix_rewrite_task_event_records_event_key",
        "rewrite_task_event_records",
        ["task_id", "event_key"],
        unique=True,
    )
    op.create_index(
        "ix_rewrite_task_event_records_occurred_at",
        "rewrite_task_event_records",
        ["occurred_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_rewrite_task_event_records_occurred_at",
        table_name="rewrite_task_event_records",
    )
    op.drop_index(
        "ix_rewrite_task_event_records_event_key",
        table_name="rewrite_task_event_records",
    )
    op.drop_index("ix_rewrite_task_event_records_task_id", table_name="rewrite_task_event_records")
    op.drop_table("rewrite_task_event_records")
