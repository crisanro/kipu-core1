"""add_secuenciales_por_tipo_to_puntos_emision
Revision ID: d608daac08f9
Revises: 7abacb4a9d2d
Create Date: 2026-08-19 10:03:21.694050
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = 'd608daac08f9'
down_revision: Union[str, Sequence[str], None] = '7abacb4a9d2d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Agregar columna secuenciales JSONB
    op.add_column("puntos_emision",
        sa.Column(
            "secuenciales",
            postgresql.JSONB(),
            nullable=False,
            server_default='{"FAC":0,"LIQ":0,"NCR":0,"NDB":0,"RET":0}'
        )
    )
    # Migrar secuencial_actual → FAC
    op.execute("""
        UPDATE puntos_emision
        SET secuenciales = jsonb_build_object(
            'FAC', COALESCE(secuencial_actual, 0),
            'LIQ', 0,
            'NCR', 0,
            'NDB', 0,
            'RET', 0
        )
    """)


def downgrade() -> None:
    op.drop_column("puntos_emision", "secuenciales")