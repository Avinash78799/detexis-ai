"""Owner accounts and revocable browser sessions; existing sites remain unclaimed."""
from alembic import op
import sqlalchemy as sa

revision = "0004"
down_revision = "0003"
branch_labels = depends_on = None


def upgrade():
    op.create_table("users", sa.Column("id", sa.String(36), primary_key=True),
                    sa.Column("email", sa.String(254), nullable=False),
                    sa.Column("password_hash", sa.String(255), nullable=False),
                    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False))
    op.create_index("ix_users_email", "users", ["email"], unique=True)
    op.create_table("browser_sessions", sa.Column("token_hash", sa.String(64), primary_key=True),
                    sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
                    sa.Column("csrf_hash", sa.String(64), nullable=False),
                    sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False))
    op.create_index("ix_browser_sessions_user_id", "browser_sessions", ["user_id"])
    op.create_index("ix_browser_sessions_expires_at", "browser_sessions", ["expires_at"])
    with op.batch_alter_table("sites") as batch:
        batch.add_column(sa.Column("owner_id", sa.String(36), nullable=True))
        batch.create_foreign_key("fk_sites_owner", "users", ["owner_id"], ["id"])
        batch.create_index("ix_sites_owner_id", ["owner_id"])


def downgrade():
    with op.batch_alter_table("sites") as batch:
        batch.drop_index("ix_sites_owner_id")
        batch.drop_constraint("fk_sites_owner", type_="foreignkey")
        batch.drop_column("owner_id")
    op.drop_table("browser_sessions")
    op.drop_table("users")
