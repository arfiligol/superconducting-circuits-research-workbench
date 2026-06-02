"""cut schema definition identity over to uuid-backed metadata

Revision ID: 20260324_0006
Revises: 20260321_0005
Create Date: 2026-03-24 04:20:00
"""

from __future__ import annotations

import json
import re
from collections.abc import Sequence
from uuid import uuid4

import sqlalchemy as sa
from alembic import op
from sqlalchemy.engine import Connection

# revision identifiers, used by Alembic.
revision: str = "20260324_0006"
down_revision: str | None = "20260321_0005"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None

_UUID_V4_PATTERN = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$",
    re.IGNORECASE,
)


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    table_names = set(inspector.get_table_names())

    _create_dataset_designs_table_if_missing(table_names)
    _create_circuit_definitions_table_if_missing(table_names)
    _create_published_simulation_results_table_if_missing(table_names)
    _create_published_simulation_traces_table_if_missing(table_names)

    inspector = sa.inspect(bind)
    table_names = set(inspector.get_table_names())
    definition_id_mapping = _build_definition_id_mapping(bind, table_names)

    if "rewrite_circuit_definitions" in table_names and definition_id_mapping:
        _rewrite_circuit_definition_identity_values(bind, definition_id_mapping)
    if "rewrite_task_records" in table_names and definition_id_mapping:
        _rewrite_task_definition_identity_values(bind, definition_id_mapping)
    if "rewrite_task_event_records" in table_names and definition_id_mapping:
        _rewrite_task_event_definition_identity_values(bind, definition_id_mapping)

    inspector = sa.inspect(bind)
    if _column_has_integer_affinity(inspector, "rewrite_circuit_definitions", "definition_id"):
        with op.batch_alter_table("rewrite_circuit_definitions", recreate="always") as batch_op:
            batch_op.alter_column(
                "definition_id",
                existing_type=sa.Integer(),
                type_=sa.String(length=36),
                existing_nullable=False,
            )
            batch_op.alter_column(
                "lineage_parent_id",
                existing_type=sa.Integer(),
                type_=sa.String(length=36),
                existing_nullable=True,
            )

    inspector = sa.inspect(bind)
    if _column_has_integer_affinity(inspector, "rewrite_task_records", "definition_id"):
        op.execute(sa.text("PRAGMA foreign_keys=OFF"))
        try:
            with op.batch_alter_table("rewrite_task_records", recreate="always") as batch_op:
                batch_op.alter_column(
                    "definition_id",
                    existing_type=sa.Integer(),
                    type_=sa.String(length=36),
                    existing_nullable=True,
                )
        finally:
            op.execute(sa.text("PRAGMA foreign_keys=ON"))


def downgrade() -> None:
    raise NotImplementedError("Definition identity UUID migration is not downgrade-safe.")


def _create_dataset_designs_table_if_missing(table_names: set[str]) -> None:
    if "rewrite_dataset_designs" in table_names:
        return
    op.create_table(
        "rewrite_dataset_designs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("dataset_id", sa.String(length=128), nullable=False),
        sa.Column("design_id", sa.String(length=128), nullable=False),
        sa.Column("normalized_name", sa.String(length=255), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
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
        "ix_rewrite_dataset_designs_dataset_design",
        "rewrite_dataset_designs",
        ["dataset_id", "design_id"],
        unique=True,
    )
    op.create_index(
        "ix_rewrite_dataset_designs_dataset_normalized_name",
        "rewrite_dataset_designs",
        ["dataset_id", "normalized_name"],
        unique=True,
    )


def _create_circuit_definitions_table_if_missing(table_names: set[str]) -> None:
    if "rewrite_circuit_definitions" in table_names:
        return
    op.create_table(
        "rewrite_circuit_definitions",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("definition_id", sa.String(length=36), nullable=False),
        sa.Column("workspace_id", sa.String(length=64), nullable=False),
        sa.Column("visibility_scope", sa.String(length=32), nullable=False),
        sa.Column("lifecycle_state", sa.String(length=32), nullable=False),
        sa.Column("owner_user_id", sa.String(length=64), nullable=False),
        sa.Column("owner_display_name", sa.String(length=128), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("created_at_iso", sa.String(length=32), nullable=False),
        sa.Column("updated_at_iso", sa.String(length=32), nullable=False),
        sa.Column("concurrency_token", sa.String(length=64), nullable=False),
        sa.Column("source_hash", sa.String(length=64), nullable=False),
        sa.Column("source_text", sa.Text(), nullable=False),
        sa.Column("normalized_output", sa.Text(), nullable=False),
        sa.Column("validation_notices_json", sa.JSON(), nullable=False),
        sa.Column("validation_summary_json", sa.JSON(), nullable=False),
        sa.Column("preview_artifacts_json", sa.JSON(), nullable=False),
        sa.Column("lineage_parent_id", sa.String(length=36), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.func.current_timestamp(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_rewrite_circuit_definitions_definition_id",
        "rewrite_circuit_definitions",
        ["definition_id"],
        unique=True,
    )
    op.create_index(
        "ix_rewrite_circuit_definitions_workspace_visibility",
        "rewrite_circuit_definitions",
        ["workspace_id", "visibility_scope"],
        unique=False,
    )
    op.create_index(
        "ix_rewrite_circuit_definitions_lifecycle_state",
        "rewrite_circuit_definitions",
        ["lifecycle_state"],
        unique=False,
    )


def _create_published_simulation_results_table_if_missing(table_names: set[str]) -> None:
    if "rewrite_published_simulation_results" in table_names:
        return
    op.create_table(
        "rewrite_published_simulation_results",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("publication_key", sa.String(length=255), nullable=False),
        sa.Column("source_task_id", sa.Integer(), nullable=False),
        sa.Column("source_dataset_id", sa.String(length=128), nullable=True),
        sa.Column("source_result_handle_ids", sa.JSON(), nullable=False),
        sa.Column("target_dataset_id", sa.String(length=128), nullable=False),
        sa.Column("target_design_id", sa.String(length=128), nullable=False),
        sa.Column("target_design_name", sa.String(length=255), nullable=False),
        sa.Column("published_at", sa.String(length=32), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.func.current_timestamp(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_rewrite_published_simulation_results_publication_key",
        "rewrite_published_simulation_results",
        ["publication_key"],
        unique=True,
    )
    op.create_index(
        "ix_rewrite_published_simulation_results_source_task_id",
        "rewrite_published_simulation_results",
        ["source_task_id"],
        unique=True,
    )
    op.create_index(
        "ix_rewrite_published_simulation_results_target_dataset_id",
        "rewrite_published_simulation_results",
        ["target_dataset_id"],
        unique=False,
    )
    op.create_index(
        "ix_rewrite_published_simulation_results_target_design_id",
        "rewrite_published_simulation_results",
        ["target_design_id"],
        unique=False,
    )


def _create_published_simulation_traces_table_if_missing(table_names: set[str]) -> None:
    if "rewrite_published_simulation_traces" in table_names:
        return
    op.create_table(
        "rewrite_published_simulation_traces",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("publication_id", sa.Integer(), nullable=False),
        sa.Column("dataset_id", sa.String(length=128), nullable=False),
        sa.Column("design_id", sa.String(length=128), nullable=False),
        sa.Column("trace_id", sa.String(length=128), nullable=False),
        sa.Column("family", sa.String(length=32), nullable=False),
        sa.Column("parameter", sa.String(length=64), nullable=False),
        sa.Column("representation", sa.String(length=64), nullable=False),
        sa.Column("trace_mode_group", sa.String(length=32), nullable=False),
        sa.Column("source_kind", sa.String(length=64), nullable=False),
        sa.Column("stage_kind", sa.String(length=32), nullable=False),
        sa.Column("provenance_summary", sa.String(length=255), nullable=False),
        sa.Column("axes_json", sa.JSON(), nullable=False),
        sa.Column("preview_payload_json", sa.JSON(), nullable=False),
        sa.Column("payload_store_key", sa.String(length=255), nullable=False),
        sa.Column("result_handle_id", sa.String(length=128), nullable=False),
        sa.Column("published_at", sa.String(length=32), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.func.current_timestamp(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["publication_id"],
            ["rewrite_published_simulation_results.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_rewrite_published_simulation_traces_dataset_design_trace",
        "rewrite_published_simulation_traces",
        ["dataset_id", "design_id", "trace_id"],
        unique=True,
    )
    op.create_index(
        "ix_rewrite_published_simulation_traces_publication_id",
        "rewrite_published_simulation_traces",
        ["publication_id"],
        unique=False,
    )


def _build_definition_id_mapping(
    bind: Connection,
    table_names: set[str],
) -> dict[str, str]:
    mapping: dict[str, str] = {}
    for raw_value in _iter_legacy_definition_id_values(bind, table_names):
        normalized_value = _normalize_definition_id_value(raw_value)
        if normalized_value is None:
            continue
        if normalized_value in mapping:
            continue
        if _UUID_V4_PATTERN.match(normalized_value):
            mapping[normalized_value] = normalized_value.lower()
            continue
        mapping[normalized_value] = str(uuid4())
    return mapping


def _iter_legacy_definition_id_values(bind: Connection, table_names: set[str]) -> Sequence[object]:
    values: list[object] = []
    if "rewrite_circuit_definitions" in table_names:
        rows = bind.execute(
            sa.text(
                """
                SELECT definition_id, lineage_parent_id
                FROM rewrite_circuit_definitions
                """
            )
        ).mappings()
        for row in rows:
            values.append(row["definition_id"])
            values.append(row["lineage_parent_id"])
    if "rewrite_task_records" in table_names:
        rows = bind.execute(
            sa.text(
                """
                SELECT definition_id
                FROM rewrite_task_records
                WHERE definition_id IS NOT NULL
                """
            )
        ).scalars()
        values.extend(rows)
    if "rewrite_task_event_records" in table_names:
        rows = bind.execute(
            sa.text(
                """
                SELECT metadata_json
                FROM rewrite_task_event_records
                WHERE metadata_json IS NOT NULL
                """
            )
        ).scalars()
        for payload in rows:
            if isinstance(payload, str):
                try:
                    parsed_payload = json.loads(payload)
                except json.JSONDecodeError:
                    continue
            else:
                parsed_payload = payload
            if isinstance(parsed_payload, dict):
                values.append(parsed_payload.get("definition_id"))
    return values


def _normalize_definition_id_value(value: object) -> str | None:
    if value is None:
        return None
    normalized_value = str(value).strip()
    return normalized_value or None


def _rewrite_circuit_definition_identity_values(
    bind: Connection,
    definition_id_mapping: dict[str, str],
) -> None:
    for legacy_value, uuid_value in definition_id_mapping.items():
        bind.execute(
            sa.text(
                """
                UPDATE rewrite_circuit_definitions
                SET definition_id = :uuid_value
                WHERE CAST(definition_id AS TEXT) = :legacy_value
                """
            ),
            {"uuid_value": uuid_value, "legacy_value": legacy_value},
        )
        bind.execute(
            sa.text(
                """
                UPDATE rewrite_circuit_definitions
                SET lineage_parent_id = :uuid_value
                WHERE lineage_parent_id IS NOT NULL
                  AND CAST(lineage_parent_id AS TEXT) = :legacy_value
                """
            ),
            {"uuid_value": uuid_value, "legacy_value": legacy_value},
        )


def _rewrite_task_definition_identity_values(
    bind: Connection,
    definition_id_mapping: dict[str, str],
) -> None:
    for legacy_value, uuid_value in definition_id_mapping.items():
        bind.execute(
            sa.text(
                """
                UPDATE rewrite_task_records
                SET definition_id = :uuid_value
                WHERE definition_id IS NOT NULL
                  AND CAST(definition_id AS TEXT) = :legacy_value
                """
            ),
            {"uuid_value": uuid_value, "legacy_value": legacy_value},
        )


def _rewrite_task_event_definition_identity_values(
    bind: Connection,
    definition_id_mapping: dict[str, str],
) -> None:
    rows = bind.execute(
        sa.text(
            """
            SELECT id, metadata_json
            FROM rewrite_task_event_records
            WHERE metadata_json IS NOT NULL
            """
        )
    ).mappings()
    for row in rows:
        payload = row["metadata_json"]
        if isinstance(payload, str):
            try:
                metadata = json.loads(payload)
            except json.JSONDecodeError:
                continue
        else:
            metadata = payload
        if not isinstance(metadata, dict) or "definition_id" not in metadata:
            continue
        normalized_value = _normalize_definition_id_value(metadata.get("definition_id"))
        if normalized_value is None:
            continue
        uuid_value = definition_id_mapping.get(normalized_value)
        if uuid_value is None or uuid_value == metadata.get("definition_id"):
            continue
        metadata["definition_id"] = uuid_value
        bind.execute(
            sa.text(
                """
                UPDATE rewrite_task_event_records
                SET metadata_json = :metadata_json
                WHERE id = :row_id
                """
            ),
            {"metadata_json": json.dumps(metadata), "row_id": row["id"]},
        )


def _column_has_integer_affinity(
    inspector: sa.Inspector,
    table_name: str,
    column_name: str,
) -> bool:
    if table_name not in inspector.get_table_names():
        return False
    for column in inspector.get_columns(table_name):
        if column["name"] != column_name:
            continue
        return "INT" in type(column["type"]).__name__.upper()
    return False
