"""initial documents table

Revision ID: 0001
Revises:
Create Date: 2026-07-08

"""
from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "documents",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("original_filename", sa.String(length=255), nullable=False),
        sa.Column("stored_filename", sa.String(length=255), nullable=False, unique=True),
        sa.Column("mime_type", sa.String(length=100), nullable=False),
        sa.Column("file_size", sa.Integer(), nullable=False),
        sa.Column(
            "status",
            sa.Enum("pending", "processing", "done", "error", name="document_status"),
            nullable=False,
            server_default="pending",
        ),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("ocr_text", sa.Text(), nullable=True),
        sa.Column("ocr_confidence", sa.Float(), nullable=True),
        sa.Column("detected_language", sa.String(length=50), nullable=True),
        sa.Column("document_type", sa.String(length=100), nullable=True),
        sa.Column("document_number", sa.String(length=150), nullable=True),
        sa.Column("issuing_authority", sa.String(length=255), nullable=True),
        sa.Column("issue_date", sa.String(length=50), nullable=True),
        sa.Column("expiry_date", sa.String(length=50), nullable=True),
        sa.Column("key_fields", sa.JSON(), nullable=True),
        sa.Column("summary_original", sa.Text(), nullable=True),
        sa.Column("summary_english", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_documents_created_at", "documents", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_documents_created_at", table_name="documents")
    op.drop_table("documents")
    sa.Enum(name="document_status").drop(op.get_bind(), checkfirst=True)
