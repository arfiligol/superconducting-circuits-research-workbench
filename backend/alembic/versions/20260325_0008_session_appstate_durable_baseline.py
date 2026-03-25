"""add durable session and app-state metadata tables

Revision ID: 20260325_0008
Revises: 20260325_0007
Create Date: 2026-03-25 19:30:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20260325_0008"
down_revision: str | None = "20260325_0007"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    table_names = set(inspector.get_table_names())

    if "rewrite_app_context_records" not in table_names:
        op.create_table(
            "rewrite_app_context_records",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("app_context_id", sa.String(length=128), nullable=False),
            sa.Column("bound_session_id", sa.String(length=128), nullable=True),
            sa.Column("runtime_mode", sa.String(length=32), nullable=False),
            sa.Column("state_json", sa.JSON(), nullable=False),
            sa.Column(
                "created_at",
                sa.DateTime(),
                server_default=sa.func.current_timestamp(),
                nullable=False,
            ),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index(
            "ix_rewrite_app_context_records_app_context_id",
            "rewrite_app_context_records",
            ["app_context_id"],
            unique=True,
        )
        op.create_index(
            "ix_rewrite_app_context_records_bound_session_id",
            "rewrite_app_context_records",
            ["bound_session_id"],
            unique=False,
        )
        op.create_index(
            "ix_rewrite_app_context_records_runtime_mode",
            "rewrite_app_context_records",
            ["runtime_mode"],
            unique=False,
        )

    if "rewrite_server_target_records" not in table_names:
        op.create_table(
            "rewrite_server_target_records",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("origin", sa.String(length=255), nullable=False),
            sa.Column("label", sa.String(length=255), nullable=False),
            sa.Column("validation_status", sa.String(length=32), nullable=False),
            sa.Column("last_checked_at", sa.String(length=32), nullable=True),
            sa.Column(
                "created_at",
                sa.DateTime(),
                server_default=sa.func.current_timestamp(),
                nullable=False,
            ),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index(
            "ix_rewrite_server_target_records_origin",
            "rewrite_server_target_records",
            ["origin"],
            unique=True,
        )
        op.create_index(
            "ix_rewrite_server_target_records_validation_status",
            "rewrite_server_target_records",
            ["validation_status"],
            unique=False,
        )

    if "rewrite_auth_account_records" not in table_names:
        op.create_table(
            "rewrite_auth_account_records",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("email", sa.String(length=255), nullable=False),
            sa.Column("password_hash", sa.String(length=255), nullable=False),
            sa.Column("user_id", sa.String(length=64), nullable=True),
            sa.Column("prototype_state_json", sa.JSON(), nullable=False),
            sa.Column(
                "created_at",
                sa.DateTime(),
                server_default=sa.func.current_timestamp(),
                nullable=False,
            ),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index(
            "ix_rewrite_auth_account_records_email",
            "rewrite_auth_account_records",
            ["email"],
            unique=True,
        )
        op.create_index(
            "ix_rewrite_auth_account_records_user_id",
            "rewrite_auth_account_records",
            ["user_id"],
            unique=True,
        )

    if "rewrite_authenticated_session_records" not in table_names:
        op.create_table(
            "rewrite_authenticated_session_records",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("session_id", sa.String(length=128), nullable=False),
            sa.Column("user_id", sa.String(length=64), nullable=False),
            sa.Column("state_json", sa.JSON(), nullable=False),
            sa.Column("last_active_dataset_ids_json", sa.JSON(), nullable=False),
            sa.Column(
                "created_at",
                sa.DateTime(),
                server_default=sa.func.current_timestamp(),
                nullable=False,
            ),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index(
            "ix_rewrite_authenticated_session_records_session_id",
            "rewrite_authenticated_session_records",
            ["session_id"],
            unique=True,
        )
        op.create_index(
            "ix_rewrite_authenticated_session_records_user_id",
            "rewrite_authenticated_session_records",
            ["user_id"],
            unique=False,
        )

    if "rewrite_refresh_token_records" not in table_names:
        op.create_table(
            "rewrite_refresh_token_records",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("token", sa.String(length=255), nullable=False),
            sa.Column("session_id", sa.String(length=128), nullable=False),
            sa.Column("family_id", sa.String(length=128), nullable=False),
            sa.Column("expires_at", sa.String(length=32), nullable=False),
            sa.Column("revoked", sa.Boolean(), nullable=False),
            sa.Column(
                "created_at",
                sa.DateTime(),
                server_default=sa.func.current_timestamp(),
                nullable=False,
            ),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index(
            "ix_rewrite_refresh_token_records_token",
            "rewrite_refresh_token_records",
            ["token"],
            unique=True,
        )
        op.create_index(
            "ix_rewrite_refresh_token_records_session_id",
            "rewrite_refresh_token_records",
            ["session_id"],
            unique=False,
        )
        op.create_index(
            "ix_rewrite_refresh_token_records_family_id",
            "rewrite_refresh_token_records",
            ["family_id"],
            unique=False,
        )

    if "rewrite_workspace_invitation_records" not in table_names:
        op.create_table(
            "rewrite_workspace_invitation_records",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("invite_id", sa.String(length=128), nullable=False),
            sa.Column("invite_token", sa.String(length=255), nullable=False),
            sa.Column("workspace_id", sa.String(length=64), nullable=False),
            sa.Column("workspace_name", sa.String(length=255), nullable=False),
            sa.Column("email", sa.String(length=255), nullable=False),
            sa.Column("role", sa.String(length=32), nullable=False),
            sa.Column("state", sa.String(length=32), nullable=False),
            sa.Column("expires_at", sa.String(length=32), nullable=False),
            sa.Column("created_at_iso", sa.String(length=32), nullable=False),
            sa.Column("delivery_status", sa.String(length=32), nullable=False),
            sa.Column("delivery_channel", sa.String(length=32), nullable=False),
            sa.Column("invite_url", sa.String(length=255), nullable=True),
            sa.Column("created_by_user_id", sa.String(length=64), nullable=False),
            sa.Column("delivery_error", sa.String(length=255), nullable=True),
            sa.Column(
                "created_at",
                sa.DateTime(),
                server_default=sa.func.current_timestamp(),
                nullable=False,
            ),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index(
            "ix_rewrite_workspace_invitation_records_invite_id",
            "rewrite_workspace_invitation_records",
            ["invite_id"],
            unique=True,
        )
        op.create_index(
            "ix_rewrite_workspace_invitation_records_invite_token",
            "rewrite_workspace_invitation_records",
            ["invite_token"],
            unique=True,
        )
        op.create_index(
            "ix_rewrite_workspace_invitation_records_workspace_id",
            "rewrite_workspace_invitation_records",
            ["workspace_id"],
            unique=False,
        )
        op.create_index(
            "ix_rewrite_workspace_invitation_records_state",
            "rewrite_workspace_invitation_records",
            ["state"],
            unique=False,
        )

    if "rewrite_pending_invitation_acceptance_records" not in table_names:
        op.create_table(
            "rewrite_pending_invitation_acceptance_records",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("continuation_token", sa.String(length=255), nullable=False),
            sa.Column("invite_token", sa.String(length=255), nullable=False),
            sa.Column("created_at_iso", sa.String(length=32), nullable=False),
            sa.Column(
                "created_at",
                sa.DateTime(),
                server_default=sa.func.current_timestamp(),
                nullable=False,
            ),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index(
            "ix_rewrite_pending_invitation_acceptance_records_continuation_token",
            "rewrite_pending_invitation_acceptance_records",
            ["continuation_token"],
            unique=True,
        )

    if "rewrite_workspace_default_dataset_records" not in table_names:
        op.create_table(
            "rewrite_workspace_default_dataset_records",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("workspace_id", sa.String(length=64), nullable=False),
            sa.Column("default_dataset_id", sa.String(length=128), nullable=False),
            sa.Column(
                "created_at",
                sa.DateTime(),
                server_default=sa.func.current_timestamp(),
                nullable=False,
            ),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index(
            "ix_rewrite_workspace_default_dataset_records_workspace_id",
            "rewrite_workspace_default_dataset_records",
            ["workspace_id"],
            unique=True,
        )


def downgrade() -> None:
    op.drop_index(
        "ix_rewrite_workspace_default_dataset_records_workspace_id",
        table_name="rewrite_workspace_default_dataset_records",
    )
    op.drop_table("rewrite_workspace_default_dataset_records")
    op.drop_index(
        "ix_rewrite_pending_invitation_acceptance_records_continuation_token",
        table_name="rewrite_pending_invitation_acceptance_records",
    )
    op.drop_table("rewrite_pending_invitation_acceptance_records")
    op.drop_index(
        "ix_rewrite_workspace_invitation_records_state",
        table_name="rewrite_workspace_invitation_records",
    )
    op.drop_index(
        "ix_rewrite_workspace_invitation_records_workspace_id",
        table_name="rewrite_workspace_invitation_records",
    )
    op.drop_index(
        "ix_rewrite_workspace_invitation_records_invite_token",
        table_name="rewrite_workspace_invitation_records",
    )
    op.drop_index(
        "ix_rewrite_workspace_invitation_records_invite_id",
        table_name="rewrite_workspace_invitation_records",
    )
    op.drop_table("rewrite_workspace_invitation_records")
    op.drop_index(
        "ix_rewrite_refresh_token_records_family_id",
        table_name="rewrite_refresh_token_records",
    )
    op.drop_index(
        "ix_rewrite_refresh_token_records_session_id",
        table_name="rewrite_refresh_token_records",
    )
    op.drop_index(
        "ix_rewrite_refresh_token_records_token",
        table_name="rewrite_refresh_token_records",
    )
    op.drop_table("rewrite_refresh_token_records")
    op.drop_index(
        "ix_rewrite_authenticated_session_records_user_id",
        table_name="rewrite_authenticated_session_records",
    )
    op.drop_index(
        "ix_rewrite_authenticated_session_records_session_id",
        table_name="rewrite_authenticated_session_records",
    )
    op.drop_table("rewrite_authenticated_session_records")
    op.drop_index(
        "ix_rewrite_auth_account_records_user_id",
        table_name="rewrite_auth_account_records",
    )
    op.drop_index(
        "ix_rewrite_auth_account_records_email",
        table_name="rewrite_auth_account_records",
    )
    op.drop_table("rewrite_auth_account_records")
    op.drop_index(
        "ix_rewrite_server_target_records_validation_status",
        table_name="rewrite_server_target_records",
    )
    op.drop_index(
        "ix_rewrite_server_target_records_origin",
        table_name="rewrite_server_target_records",
    )
    op.drop_table("rewrite_server_target_records")
    op.drop_index(
        "ix_rewrite_app_context_records_runtime_mode",
        table_name="rewrite_app_context_records",
    )
    op.drop_index(
        "ix_rewrite_app_context_records_bound_session_id",
        table_name="rewrite_app_context_records",
    )
    op.drop_index(
        "ix_rewrite_app_context_records_app_context_id",
        table_name="rewrite_app_context_records",
    )
    op.drop_table("rewrite_app_context_records")
