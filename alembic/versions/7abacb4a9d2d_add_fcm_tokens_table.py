"""add_fcm_tokens_table
Revision ID: 7abacb4a9d2d
Revises: 4574105b673c
Create Date: 2026-08-18 23:11:34.091373
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = '7abacb4a9d2d'
down_revision: Union[str, Sequence[str], None] = '4574105b673c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "fcm_tokens",
        sa.Column("id",         sa.Integer(),                primary_key=True, autoincrement=True),
        sa.Column("profile_id", sa.UUID(as_uuid=True),       nullable=False),
        sa.Column("emisor_id",  sa.Integer(),                nullable=False),
        sa.Column("token",      sa.Text(),                   nullable=False),
        sa.Column("device_id",  sa.String(100),              nullable=False, server_default="default"),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["profile_id"], ["profiles.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["emisor_id"],  ["emisores.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("profile_id", "emisor_id", "device_id", name="uq_fcm_profile_emisor_device"),
    )
    op.create_index("ix_fcm_tokens_emisor",  "fcm_tokens", ["emisor_id"])
    op.create_index("ix_fcm_tokens_profile", "fcm_tokens", ["profile_id"])


def downgrade() -> None:
    op.drop_index("ix_fcm_tokens_profile", table_name="fcm_tokens")
    op.drop_index("ix_fcm_tokens_emisor",  table_name="fcm_tokens")
    op.drop_table("fcm_tokens")