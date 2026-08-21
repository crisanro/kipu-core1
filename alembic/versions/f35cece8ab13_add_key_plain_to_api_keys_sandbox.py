"""add_key_plain_to_api_keys_sandbox

Revision ID: f35cece8ab13
Revises: d50649566409
Create Date: 2026-08-20 22:26:44.255825

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f35cece8ab13'
down_revision: Union[str, Sequence[str], None] = 'd50649566409'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("api_keys",
        sa.Column("key_plain", sa.Text(), nullable=True)
    )

def downgrade() -> None:
    op.drop_column("api_keys", "key_plain")