"""add_emisor_id_to_auth_challenges

Revision ID: d6a954bc58f3
Revises: 235437b3dc8c
Create Date: 2026-08-20 14:58:06.036487

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd6a954bc58f3'
down_revision: Union[str, Sequence[str], None] = '235437b3dc8c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("auth_challenges",
        sa.Column("emisor_id", sa.Integer(), nullable=True)
    )
    op.create_foreign_key(
        "fk_auth_challenges_emisor",
        "auth_challenges", "emisores",
        ["emisor_id"], ["id"],
        ondelete="CASCADE"
    )

def downgrade() -> None:
    op.drop_constraint("fk_auth_challenges_emisor", "auth_challenges", type_="foreignkey")
    op.drop_column("auth_challenges", "emisor_id")