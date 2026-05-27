"""Add dataset-local design scope lifecycle fields.

Revision ID: 20260430_0010
Revises: 20260327_0009
Create Date: 2026-04-30 00:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision = "20260430_0010"
down_revision = "20260327_0009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("rewrite_dataset_designs") as batch_op:
        batch_op.drop_index("ix_rewrite_dataset_designs_dataset_normalized_name")
        batch_op.add_column(
            sa.Column(
                "lifecycle_state",
                sa.String(length=32),
                nullable=False,
                server_default="active",
            )
        )
        batch_op.add_column(sa.Column("redirect_design_id", sa.String(length=128)))
        batch_op.create_index(
            "ix_rewrite_dataset_designs_dataset_normalized_name",
            ["dataset_id", "normalized_name", "lifecycle_state"],
            unique=True,
        )


def downgrade() -> None:
    with op.batch_alter_table("rewrite_dataset_designs") as batch_op:
        batch_op.drop_index("ix_rewrite_dataset_designs_dataset_normalized_name")
        batch_op.drop_column("redirect_design_id")
        batch_op.drop_column("lifecycle_state")
        batch_op.create_index(
            "ix_rewrite_dataset_designs_dataset_normalized_name",
            ["dataset_id", "normalized_name"],
            unique=True,
        )
