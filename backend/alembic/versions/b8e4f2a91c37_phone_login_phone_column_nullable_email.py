"""phone login: phone column, nullable email

Revision ID: b8e4f2a91c37
Revises: 56a7e1557e43
Create Date: 2026-10-21 12:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b8e4f2a91c37"
down_revision: str | Sequence[str] | None = "56a7e1557e43"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column("users", sa.Column("phone", sa.String(length=15), nullable=True))
    op.create_index(op.f("ix_users_phone"), "users", ["phone"], unique=True)
    op.alter_column(
        "users", "email", existing_type=sa.VARCHAR(length=255), nullable=True
    )
    # Every account still has a way to sign in: an email, a phone, or both.
    op.create_check_constraint(
        "ck_users_email_or_phone", "users", "email IS NOT NULL OR phone IS NOT NULL"
    )


def downgrade() -> None:
    """Downgrade schema."""
    # Fails if phone-only accounts exist; delete or give them an email first.
    op.drop_constraint("ck_users_email_or_phone", "users", type_="check")
    op.alter_column(
        "users", "email", existing_type=sa.VARCHAR(length=255), nullable=False
    )
    op.drop_index(op.f("ix_users_phone"), table_name="users")
    op.drop_column("users", "phone")
