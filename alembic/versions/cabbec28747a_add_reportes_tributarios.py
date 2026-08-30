"""add_reportes_tributarios

Revision ID: cabbec28747a
Revises: bcab032c8ca7
Create Date: 2026-08-29 20:45:35.058906

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from sqlalchemy.dialects.postgresql import UUID, JSONB

# revision identifiers, used by Alembic.
revision: str = 'cabbec28747a'
down_revision: Union[str, Sequence[str], None] = 'bcab032c8ca7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade():
    op.create_table(
        "reportes_tributarios",
        sa.Column("id",              UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("emisor_id",       sa.Integer, sa.ForeignKey("emisores.id", ondelete="CASCADE"), nullable=False),
        sa.Column("tipo",            sa.String(10), nullable=False),
        sa.Column("tipo_periodo",    sa.String(10), nullable=False),
        sa.Column("periodo",         sa.Date, nullable=False),
        sa.Column("casilleros",      JSONB, nullable=False, server_default="{}"),
        sa.Column("preguntas",       JSONB, nullable=False, server_default="{}"),
        sa.Column("desglose",        JSONB, nullable=False, server_default="{}"),
        sa.Column("resumen",         JSONB, nullable=False, server_default="{}"),
        sa.Column("doc_emitidos_ids",    JSONB, nullable=False, server_default="[]"),
        sa.Column("doc_recibidos_ids",   JSONB, nullable=False, server_default="[]"),
        sa.Column("total_doc_emitidos",  sa.Integer, nullable=False, server_default="0"),
        sa.Column("total_doc_recibidos", sa.Integer, nullable=False, server_default="0"),
        sa.Column("generado_at",     sa.TIMESTAMP(timezone=True), server_default=sa.text("NOW()")),
        sa.Column("generado_por",    UUID(as_uuid=True), sa.ForeignKey("profiles.id", ondelete="SET NULL"), nullable=True),
        sa.Column("regenerado_at",   sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("regenerado_por",  UUID(as_uuid=True), sa.ForeignKey("profiles.id", ondelete="SET NULL"), nullable=True),
        sa.UniqueConstraint("emisor_id", "tipo", "periodo", name="uq_reporte_emisor_tipo_periodo"),
    )
    op.create_index(
        "idx_reportes_tributarios_emisor",
        "reportes_tributarios",
        ["emisor_id", "tipo", "periodo"],
        postgresql_ops={"periodo": "DESC"},
    )

def downgrade():
    op.drop_index("idx_reportes_tributarios_emisor")
    op.drop_table("reportes_tributarios")