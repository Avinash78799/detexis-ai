"""Store bounded timestamps to establish incident correlation order."""
from alembic import op
import sqlalchemy as sa

revision = "0010"
down_revision = "0009"
branch_labels = depends_on = None


def upgrade():
    op.add_column("incidents", sa.Column("first_recon_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("incidents", sa.Column("last_exploit_at", sa.DateTime(timezone=True), nullable=True))


def downgrade():
    op.drop_column("incidents", "last_exploit_at")
    op.drop_column("incidents", "first_recon_at")
