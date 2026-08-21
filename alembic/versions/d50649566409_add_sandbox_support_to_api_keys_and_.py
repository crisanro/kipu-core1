"""add_sandbox_support_to_api_keys_and_documentos

Revision ID: d50649566409
Revises: d6a954bc58f3
Create Date: 2026-08-20 21:58:59.597983

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd50649566409'
down_revision: Union[str, Sequence[str], None] = 'd6a954bc58f3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # api_keys — agregar es_sandbox
    op.add_column("api_keys",
        sa.Column("es_sandbox", sa.Boolean(), nullable=False, server_default="false")
    )

    # documentos_emitidos — agregar es_sandbox y auto-delete
    op.add_column("documentos_emitidos",
        sa.Column("es_sandbox", sa.Boolean(), nullable=False, server_default="false")
    )

    # Índice para queries de sandbox y para el job de limpieza
    op.create_index(
        "ix_documentos_emitidos_es_sandbox",
        "documentos_emitidos",
        ["es_sandbox", "created_at"]
    )

def downgrade() -> None:
    op.drop_index("ix_documentos_emitidos_es_sandbox", "documentos_emitidos")
    op.drop_column("documentos_emitidos", "es_sandbox")
    op.drop_column("api_keys", "es_sandbox")