"""initial empty schema

Revision ID: 6a801d4ce6d5
Revises:
Create Date: 2026-10-30 17:16:35.543354

"""

from typing import Sequence, Union


# revision identifiers, used by Alembic.
revision: str = "6a801d4ce6d5"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
