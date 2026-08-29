"""documentos_emitidos_created_by

Revision ID: bcab032c8ca7
Revises: 93f0a3c51a12
Create Date: 2026-08-29 12:25:46.746326

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'bcab032c8ca7'
down_revision: Union[str, Sequence[str], None] = '93f0a3c51a12'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('documentos_emitidos',
        sa.Column('created_by', sa.UUID(), nullable=True)
    )
    op.create_foreign_key(
        None, 'documentos_emitidos', 'profiles',
        ['created_by'], ['id'],
        ondelete='SET NULL'
    )

def downgrade() -> None:
    op.drop_constraint(None, 'documentos_emitidos', type_='foreignkey')
    op.drop_column('documentos_emitidos', 'created_by')
    
    # ### end Alembic commands ###
