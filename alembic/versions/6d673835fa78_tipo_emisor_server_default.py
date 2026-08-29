"""tipo_emisor_server_default

Revision ID: 6d673835fa78
Revises: f35cece8ab13
Create Date: 2026-08-29 11:37:52.565684

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '6d673835fa78'
down_revision: Union[str, Sequence[str], None] = 'f35cece8ab13'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column('emisores', 'tipo_emisor',
        existing_type=sa.String(length=10),
        nullable=False,
        server_default='NATURAL'
    )

def downgrade() -> None:
    op.alter_column('emisores', 'tipo_emisor',
        existing_type=sa.String(length=10),
        nullable=False,
        server_default=None
    )