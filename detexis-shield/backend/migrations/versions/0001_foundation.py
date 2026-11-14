"""Initial Shield schema; event IDs are scoped to their authenticated site."""
from alembic import op
import sqlalchemy as sa

revision = "0001"
down_revision = None
branch_labels = depends_on = None


def upgrade():
    op.create_table("sites", sa.Column("id", sa.String(36), primary_key=True),
                    sa.Column("domain", sa.String(255), nullable=False),
                    sa.Column("mode", sa.String(16), nullable=False),
                    sa.Column("last_heartbeat", sa.DateTime(timezone=True)),
                    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False))
    op.create_table("api_keys", sa.Column("id", sa.Integer(), primary_key=True),
                    sa.Column("site_id", sa.String(36), sa.ForeignKey("sites.id"), nullable=False),
                    sa.Column("prefix", sa.String(12), nullable=False),
                    sa.Column("key_hash", sa.String(64), nullable=False),
                    sa.Column("revoked", sa.Boolean(), nullable=False))
    op.create_index("ix_api_keys_site_id", "api_keys", ["site_id"])
    op.create_index("ix_api_keys_prefix", "api_keys", ["prefix"], unique=True)
    op.create_table("events",
                    sa.Column("site_id", sa.String(36), sa.ForeignKey("sites.id"), primary_key=True),
                    sa.Column("event_id", sa.String(36), primary_key=True),
                    sa.Column("received_at", sa.DateTime(timezone=True), nullable=False),
                    sa.Column("ts", sa.DateTime(timezone=True), nullable=False),
                    sa.Column("ip_hash", sa.String(64), nullable=False),
                    sa.Column("method", sa.String(10), nullable=False),
                    sa.Column("path", sa.String(2048), nullable=False),
                    sa.Column("query_redacted", sa.String(2048), nullable=False),
                    sa.Column("ua", sa.String(512), nullable=False),
                    sa.Column("status", sa.Integer(), nullable=False),
                    sa.Column("latency_ms", sa.Float(), nullable=False),
                    sa.Column("flags", sa.JSON(), nullable=False),
                    sa.Column("features", sa.JSON(), nullable=False))
    op.create_index("ix_events_site_ts", "events", ["site_id", "ts"])
    op.create_index("ix_events_site_ip", "events", ["site_id", "ip_hash"])


def downgrade():
    op.drop_table("events")
    op.drop_table("api_keys")
    op.drop_table("sites")
