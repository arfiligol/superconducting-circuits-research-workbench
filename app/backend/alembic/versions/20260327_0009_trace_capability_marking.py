"""add durable per-trace analysis capability records

Revision ID: 20260327_0009
Revises: 20260325_0008
Create Date: 2026-03-27 14:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20260327_0009"
down_revision: str | None = "20260325_0008"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    table_names = set(inspector.get_table_names())

    if "rewrite_trace_capability_records" not in table_names:
        op.create_table(
            "rewrite_trace_capability_records",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("dataset_id", sa.String(length=128), nullable=False),
            sa.Column("design_id", sa.String(length=128), nullable=False),
            sa.Column("trace_id", sa.String(length=128), nullable=False),
            sa.Column("capability_id", sa.String(length=128), nullable=False),
            sa.Column("analysis_id", sa.String(length=128), nullable=False),
            sa.Column("analysis_label", sa.String(length=255), nullable=False),
            sa.Column("input_role", sa.String(length=128), nullable=False),
            sa.Column("input_role_label", sa.String(length=255), nullable=False),
            sa.Column("status", sa.String(length=32), nullable=False),
            sa.Column("summary", sa.String(length=255), nullable=False),
            sa.Column("reasons_json", sa.JSON(), nullable=False),
            sa.Column(
                "created_at",
                sa.DateTime(),
                server_default=sa.func.current_timestamp(),
                nullable=False,
            ),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index(
            "ix_rewrite_trace_capability_dataset_design_trace_capability",
            "rewrite_trace_capability_records",
            ["dataset_id", "design_id", "trace_id", "capability_id"],
            unique=True,
        )
        op.create_index(
            "ix_rewrite_trace_capability_dataset_design_analysis",
            "rewrite_trace_capability_records",
            ["dataset_id", "design_id", "analysis_id"],
            unique=False,
        )


def downgrade() -> None:
    op.drop_index(
        "ix_rewrite_trace_capability_dataset_design_analysis",
        table_name="rewrite_trace_capability_records",
    )
    op.drop_index(
        "ix_rewrite_trace_capability_dataset_design_trace_capability",
        table_name="rewrite_trace_capability_records",
    )
    op.drop_table("rewrite_trace_capability_records")
