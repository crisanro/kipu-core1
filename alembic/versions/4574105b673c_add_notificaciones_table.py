"""add_notificaciones_table

Revision ID: 4574105b673c
Revises: ed2060ddb24f
Create Date: 2026-08-18 17:47:58.691242
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = '4574105b673c'
down_revision: Union[str, Sequence[str], None] = 'ed2060ddb24f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "notificaciones",
        sa.Column("id",         sa.BigInteger(),              primary_key=True, autoincrement=True),
        sa.Column("emisor_id",  sa.Integer(),                 nullable=False),
        sa.Column("tipo",       sa.String(50),                nullable=False, server_default="SISTEMA"),
        sa.Column("titulo",     sa.String(255),               nullable=False),
        sa.Column("mensaje",    sa.Text(),                    nullable=False),
        sa.Column("referencia", sa.String(255),               nullable=True),
        sa.Column("leida",      sa.Boolean(),                 nullable=False, server_default="false"),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True),  server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["emisor_id"], ["emisores.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_notificaciones_emisor", "notificaciones", ["emisor_id"])
    op.create_index("ix_notificaciones_leida",  "notificaciones", ["emisor_id", "leida"])


def downgrade() -> None:
    op.drop_index("ix_notificaciones_leida",  table_name="notificaciones")
    op.drop_index("ix_notificaciones_emisor", table_name="notificaciones")
    op.drop_table("notificaciones")