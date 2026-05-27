"""rewrite storage metadata baseline

Revision ID: 20260312_0001
Revises:
Create Date: 2026-03-12 12:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "20260312_0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "rewrite_storage_records",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("record_type", sa.String(length=32), nullable=False),
        sa.Column("record_id", sa.String(length=128), nullable=False),
        sa.Column("schema_version", sa.String(length=32), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.func.current_timestamp(),
            nullable=False,
        ),
        sa.UniqueConstraint("record_id", name="uq_rewrite_storage_records_record_id"),
    )
    op.create_index(
        "ix_rewrite_storage_records_record_type",
        "rewrite_storage_records",
        ["record_type"],
        unique=False,
    )

    op.create_table(
        "rewrite_trace_payloads",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("owner_record_id", sa.Integer(), nullable=False),
        sa.Column("contract_version", sa.String(length=32), nullable=False),
        sa.Column("backend", sa.String(length=32), nullable=False),
        sa.Column("payload_role", sa.String(length=32), nullable=False),
        sa.Column("store_key", sa.String(length=255), nullable=False),
        sa.Column("store_uri", sa.String(length=255), nullable=True),
        sa.Column("group_path", sa.String(length=255), nullable=False),
        sa.Column("array_path", sa.String(length=255), nullable=False),
        sa.Column("dtype", sa.String(length=32), nullable=False),
        sa.Column("shape", sa.JSON(), nullable=False),
        sa.Column("chunk_shape", sa.JSON(), nullable=False),
        sa.Column("schema_version", sa.String(length=32), nullable=False),
        sa.Column("writer_version", sa.String(length=64), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.func.current_timestamp(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["owner_record_id"],
            ["rewrite_storage_records.id"],
            ondelete="CASCADE",
        ),
    )
    op.create_index(
        "ix_rewrite_trace_payloads_payload_role",
        "rewrite_trace_payloads",
        ["payload_role"],
        unique=False,
    )
    op.create_index(
        "ix_rewrite_trace_payloads_store_key",
        "rewrite_trace_payloads",
        ["store_key"],
        unique=True,
    )

    op.create_table(
        "rewrite_result_handles",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("metadata_record_id", sa.Integer(), nullable=False),
        sa.Column("handle_id", sa.String(length=128), nullable=False),
        sa.Column("contract_version", sa.String(length=32), nullable=False),
        sa.Column("kind", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("label", sa.String(length=255), nullable=False),
        sa.Column("payload_backend", sa.String(length=64), nullable=True),
        sa.Column("payload_format", sa.String(length=32), nullable=True),
        sa.Column("payload_role", sa.String(length=32), nullable=True),
        sa.Column("payload_locator", sa.String(length=255), nullable=True),
        sa.Column("provenance_task_id", sa.Integer(), nullable=True),
        sa.Column("source_dataset_id", sa.String(length=128), nullable=True),
        sa.Column("source_task_id", sa.Integer(), nullable=True),
        sa.Column("trace_batch_record_id", sa.Integer(), nullable=True),
        sa.Column("analysis_run_record_id", sa.Integer(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.func.current_timestamp(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["analysis_run_record_id"],
            ["rewrite_storage_records.id"],
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["metadata_record_id"],
            ["rewrite_storage_records.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["trace_batch_record_id"],
            ["rewrite_storage_records.id"],
            ondelete="SET NULL",
        ),
        sa.UniqueConstraint("handle_id", name="uq_rewrite_result_handles_handle_id"),
        sa.UniqueConstraint(
            "metadata_record_id",
            name="uq_rewrite_result_handles_metadata_record_id",
        ),
    )
    op.create_index(
        "ix_rewrite_result_handles_kind",
        "rewrite_result_handles",
        ["kind"],
        unique=False,
    )
    op.create_index(
        "ix_rewrite_result_handles_handle_id",
        "rewrite_result_handles",
        ["handle_id"],
        unique=True,
    )


def downgrade() -> None:
    index_names: Sequence[str] = (
        "ix_rewrite_result_handles_handle_id",
        "ix_rewrite_result_handles_kind",
    )
    for index_name in index_names:
        op.drop_index(index_name, table_name="rewrite_result_handles")
    op.drop_table("rewrite_result_handles")

    trace_indexes: Sequence[str] = (
        "ix_rewrite_trace_payloads_store_key",
        "ix_rewrite_trace_payloads_payload_role",
    )
    for index_name in trace_indexes:
        op.drop_index(index_name, table_name="rewrite_trace_payloads")
    op.drop_table("rewrite_trace_payloads")

    op.drop_index(
        "ix_rewrite_storage_records_record_type",
        table_name="rewrite_storage_records",
    )
    op.drop_table("rewrite_storage_records")
