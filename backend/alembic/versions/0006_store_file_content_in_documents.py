"""store uploaded file bytes in the documents row instead of local disk

Revision ID: 0006
Revises: 0005
Create Date: 2026-07-30

"""
from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

revision: str = "0006"
down_revision: Union[str, None] = "0005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("documents") as batch_op:
        batch_op.add_column(sa.Column("file_content", sa.LargeBinary(), nullable=True))
        batch_op.drop_column("stored_filename")


def downgrade() -> None:
    with op.batch_alter_table("documents") as batch_op:
        # The original file bytes for anything uploaded under 0006 have
        # nowhere to go on downgrade - a placeholder keeps the column
        # NOT NULL-compatible with the pre-0006 schema without pretending a
        # real on-disk file still exists for old rows.
        batch_op.add_column(sa.Column("stored_filename", sa.String(length=255), nullable=True))
        batch_op.drop_column("file_content")
