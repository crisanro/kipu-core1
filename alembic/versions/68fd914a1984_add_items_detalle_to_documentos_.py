"""add_items_detalle_to_documentos_recibidos
Revision ID: 68fd914a1984
Revises: d608daac08f9
Create Date: 2026-08-19 23:32:57.143125
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql  # ← agregar

revision: str = '68fd914a1984'
down_revision: Union[str, Sequence[str], None] = 'd608daac08f9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    op.add_column("documentos_recibidos",
        sa.Column(
            "items_detalle",
            postgresql.JSONB(),
            nullable=True,
        )
    )

def downgrade() -> None:
    op.drop_column("documentos_recibidos", "items_detalle")