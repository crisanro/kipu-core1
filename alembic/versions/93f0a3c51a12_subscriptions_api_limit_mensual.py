"""subscriptions_api_limit_mensual

Revision ID: 93f0a3c51a12
Revises: 6d673835fa78
Create Date: 2026-08-29 12:03:08.672972

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '93f0a3c51a12'
down_revision: Union[str, Sequence[str], None] = '6d673835fa78'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('subscriptions',
        sa.Column('api_limit_mensual', sa.Integer(), nullable=True)
    )

def downgrade() -> None:
    op.drop_column('subscriptions', 'api_limit_mensual')

    # ### end Alembic commands ###
