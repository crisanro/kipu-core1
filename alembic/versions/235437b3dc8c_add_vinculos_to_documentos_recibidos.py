"""add_vinculos_to_documentos_recibidos

Revision ID: 235437b3dc8c
Revises: 68fd914a1984
Create Date: 2026-08-19 23:41:11.080366

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = '235437b3dc8c'
down_revision: Union[str, Sequence[str], None] = '68fd914a1984'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("documentos_recibidos",
        sa.Column("doc_origen_recibido_id",
            postgresql.UUID(as_uuid=True), nullable=True)
    )
    op.add_column("documentos_recibidos",
        sa.Column("doc_origen_emitido_id",
            postgresql.UUID(as_uuid=True), nullable=True)
    )
    op.create_foreign_key(
        "fk_doc_recibido_origen_recibido",
        "documentos_recibidos", "documentos_recibidos",
        ["doc_origen_recibido_id"], ["id"],
        ondelete="SET NULL"
    )
    op.create_foreign_key(
        "fk_doc_recibido_origen_emitido",
        "documentos_recibidos", "documentos_emitidos",
        ["doc_origen_emitido_id"], ["id"],
        ondelete="SET NULL"
    )

def downgrade() -> None:
    op.drop_constraint("fk_doc_recibido_origen_recibido", "documentos_recibidos", type_="foreignkey")
    op.drop_constraint("fk_doc_recibido_origen_emitido",  "documentos_recibidos", type_="foreignkey")
    op.drop_column("documentos_recibidos", "doc_origen_recibido_id")
    op.drop_column("documentos_recibidos", "doc_origen_emitido_id")