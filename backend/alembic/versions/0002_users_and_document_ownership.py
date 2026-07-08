"""add users table and document ownership

Revision ID: 0002
Revises: 0001
Create Date: 2026-07-08

"""
from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("hashed_password", sa.String(length=255), nullable=False),
        sa.Column("full_name", sa.String(length=255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)

    # batch mode is required for SQLite (no ALTER for constraints) and works
    # transparently on Postgres too.
    with op.batch_alter_table("documents") as batch_op:
        batch_op.add_column(sa.Column("user_id", sa.Uuid(), nullable=False))
        batch_op.create_index("ix_documents_user_id", ["user_id"])
        batch_op.create_foreign_key(
            "fk_documents_user_id", "users", ["user_id"], ["id"], ondelete="CASCADE"
        )


def downgrade() -> None:
    with op.batch_alter_table("documents") as batch_op:
        batch_op.drop_constraint("fk_documents_user_id", type_="foreignkey")
        batch_op.drop_index("ix_documents_user_id")
        batch_op.drop_column("user_id")

    op.drop_index("ix_users_email", table_name="users")
    op.drop_table("users")
