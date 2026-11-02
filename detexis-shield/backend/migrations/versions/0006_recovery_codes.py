"""One-use offline account recovery verifiers; never store the raw code."""
from alembic import op
import sqlalchemy as sa

revision = "0006"
down_revision = "0005"
branch_labels = depends_on = None


def upgrade():
    op.add_column("users", sa.Column("recovery_hash", sa.String(64), nullable=True))


def downgrade():
    op.drop_column("users", "recovery_hash")
