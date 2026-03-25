"""add durable dataset and raw trace metadata tables

Revision ID: 20260325_0007
Revises: 20260324_0006
Create Date: 2026-03-25 13:40:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20260325_0007"
down_revision: str | None = "20260324_0006"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    table_names = set(inspector.get_table_names())

    if "rewrite_dataset_records" not in table_names:
        op.create_table(
            "rewrite_dataset_records",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("dataset_id", sa.String(length=128), nullable=False),
            sa.Column("name", sa.String(length=255), nullable=False),
            sa.Column("family", sa.String(length=64), nullable=False),
            sa.Column("owner_display_name", sa.String(length=128), nullable=False),
            sa.Column("owner_user_id", sa.String(length=64), nullable=False),
            sa.Column("workspace_id", sa.String(length=64), nullable=False),
            sa.Column("visibility_scope", sa.String(length=32), nullable=False),
            sa.Column("lifecycle_state", sa.String(length=32), nullable=False),
            sa.Column("updated_at", sa.String(length=32), nullable=False),
            sa.Column("device_type", sa.String(length=64), nullable=False),
            sa.Column("capabilities_json", sa.JSON(), nullable=False),
            sa.Column("source", sa.String(length=64), nullable=False),
            sa.Column("status", sa.String(length=32), nullable=False),
            sa.Column(
                "created_at",
                sa.DateTime(),
                server_default=sa.func.current_timestamp(),
                nullable=False,
            ),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index(
            "ix_rewrite_dataset_records_dataset_id",
            "rewrite_dataset_records",
            ["dataset_id"],
            unique=True,
        )
        op.create_index(
            "ix_rewrite_dataset_records_workspace_id",
            "rewrite_dataset_records",
            ["workspace_id"],
            unique=False,
        )
        op.create_index(
            "ix_rewrite_dataset_records_lifecycle_state",
            "rewrite_dataset_records",
            ["lifecycle_state"],
            unique=False,
        )

    if "rewrite_dataset_traces" not in table_names:
        op.create_table(
            "rewrite_dataset_traces",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("dataset_id", sa.String(length=128), nullable=False),
            sa.Column("design_id", sa.String(length=128), nullable=False),
            sa.Column("trace_id", sa.String(length=128), nullable=False),
            sa.Column("family", sa.String(length=32), nullable=False),
            sa.Column("parameter", sa.String(length=128), nullable=False),
            sa.Column("representation", sa.String(length=64), nullable=False),
            sa.Column("trace_mode_group", sa.String(length=32), nullable=False),
            sa.Column("source_kind", sa.String(length=64), nullable=False),
            sa.Column("stage_kind", sa.String(length=32), nullable=False),
            sa.Column("provenance_summary", sa.String(length=255), nullable=False),
            sa.Column("axes_json", sa.JSON(), nullable=False),
            sa.Column("preview_payload_json", sa.JSON(), nullable=False),
            sa.Column("numeric_payload_json", sa.JSON(), nullable=False),
            sa.Column("payload_store_key", sa.String(length=255), nullable=False),
            sa.Column("result_handle_ids_json", sa.JSON(), nullable=False),
            sa.Column("editable", sa.Boolean(), nullable=False),
            sa.Column("mutation_policy_summary", sa.String(length=255), nullable=False),
            sa.Column("updated_at", sa.String(length=32), nullable=False),
            sa.Column(
                "created_at",
                sa.DateTime(),
                server_default=sa.func.current_timestamp(),
                nullable=False,
            ),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index(
            "ix_rewrite_dataset_traces_dataset_design_trace",
            "rewrite_dataset_traces",
            ["dataset_id", "design_id", "trace_id"],
            unique=True,
        )
        op.create_index(
            "ix_rewrite_dataset_traces_dataset_design",
            "rewrite_dataset_traces",
            ["dataset_id", "design_id"],
            unique=False,
        )

    if "rewrite_characterization_registry_records" not in table_names:
        op.create_table(
            "rewrite_characterization_registry_records",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("dataset_id", sa.String(length=128), nullable=False),
            sa.Column("design_id", sa.String(length=128), nullable=False),
            sa.Column("analysis_id", sa.String(length=128), nullable=False),
            sa.Column("label", sa.String(length=255), nullable=False),
            sa.Column("availability_state", sa.String(length=32), nullable=False),
            sa.Column("required_config_fields_json", sa.JSON(), nullable=False),
            sa.Column("matched_trace_count", sa.Integer(), nullable=False),
            sa.Column("recommended_trace_modes_json", sa.JSON(), nullable=False),
            sa.Column("summary", sa.String(length=255), nullable=False),
            sa.Column("sort_order", sa.Integer(), nullable=False),
            sa.Column(
                "created_at",
                sa.DateTime(),
                server_default=sa.func.current_timestamp(),
                nullable=False,
            ),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index(
            "ix_rewrite_characterization_registry_dataset_design_analysis",
            "rewrite_characterization_registry_records",
            ["dataset_id", "design_id", "analysis_id"],
            unique=True,
        )
        op.create_index(
            "ix_rewrite_characterization_registry_dataset_design_sort",
            "rewrite_characterization_registry_records",
            ["dataset_id", "design_id", "sort_order"],
            unique=False,
        )


def downgrade() -> None:
    op.drop_index(
        "ix_rewrite_characterization_registry_dataset_design_sort",
        table_name="rewrite_characterization_registry_records",
    )
    op.drop_index(
        "ix_rewrite_characterization_registry_dataset_design_analysis",
        table_name="rewrite_characterization_registry_records",
    )
    op.drop_table("rewrite_characterization_registry_records")
    op.drop_index(
        "ix_rewrite_dataset_traces_dataset_design",
        table_name="rewrite_dataset_traces",
    )
    op.drop_index(
        "ix_rewrite_dataset_traces_dataset_design_trace",
        table_name="rewrite_dataset_traces",
    )
    op.drop_table("rewrite_dataset_traces")
    op.drop_index(
        "ix_rewrite_dataset_records_lifecycle_state",
        table_name="rewrite_dataset_records",
    )
    op.drop_index(
        "ix_rewrite_dataset_records_workspace_id",
        table_name="rewrite_dataset_records",
    )
    op.drop_index(
        "ix_rewrite_dataset_records_dataset_id",
        table_name="rewrite_dataset_records",
    )
    op.drop_table("rewrite_dataset_records")
