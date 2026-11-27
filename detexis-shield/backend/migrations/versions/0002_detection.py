"""Detection, baseline, alert outbox and verified scanner records."""
from alembic import op
import sqlalchemy as sa

revision = "0002"
down_revision = "0001"
branch_labels = depends_on = None


def upgrade():
    op.add_column("sites", sa.Column("honeytokens", sa.JSON(), nullable=False, server_default='["/.env", "/admin-backup"]'))
    op.add_column("sites", sa.Column("settings", sa.JSON(), nullable=False, server_default='{}'))
    op.add_column("sites", sa.Column("verification_hash", sa.String(64)))
    op.add_column("sites", sa.Column("verified_at", sa.DateTime(timezone=True)))
    op.add_column("events", sa.Column("processed_at", sa.DateTime(timezone=True)))
    op.add_column("events", sa.Column("findings", sa.JSON(), nullable=False, server_default='[]'))
    op.create_index("ix_events_pending", "events", ["processed_at", "received_at"])
    op.create_table("incidents", sa.Column("id", sa.String(36), primary_key=True),
                    sa.Column("site_id", sa.String(36), sa.ForeignKey("sites.id"), nullable=False),
                    sa.Column("ip_hash", sa.String(64), nullable=False),
                    sa.Column("bucket", sa.Integer(), nullable=False),
                    sa.Column("severity", sa.String(16), nullable=False),
                    sa.Column("rules", sa.JSON(), nullable=False),
                    sa.Column("correlations", sa.JSON(), nullable=False),
                    sa.Column("event_count", sa.Integer(), nullable=False),
                    sa.Column("first_seen", sa.DateTime(timezone=True), nullable=False),
                    sa.Column("last_seen", sa.DateTime(timezone=True), nullable=False),
                    sa.UniqueConstraint("site_id", "ip_hash", "bucket", name="uq_incident_group"))
    op.create_index("ix_incidents_site_id", "incidents", ["site_id"])
    op.create_table("alerts", sa.Column("id", sa.String(36), primary_key=True),
                    sa.Column("site_id", sa.String(36), sa.ForeignKey("sites.id"), nullable=False),
                    sa.Column("incident_id", sa.String(36), sa.ForeignKey("incidents.id"), nullable=False, unique=True),
                    sa.Column("status", sa.String(16), nullable=False),
                    sa.Column("attempts", sa.Integer(), nullable=False),
                    sa.Column("delivered", sa.JSON(), nullable=False),
                    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False))
    op.create_index("ix_alerts_site_id", "alerts", ["site_id"])
    op.create_table("hour_buckets", sa.Column("site_id", sa.String(36), sa.ForeignKey("sites.id"), primary_key=True),
                    sa.Column("hour", sa.DateTime(timezone=True), primary_key=True),
                    sa.Column("count", sa.Integer(), nullable=False))
    op.create_table("scans", sa.Column("id", sa.String(36), primary_key=True),
                    sa.Column("site_id", sa.String(36), sa.ForeignKey("sites.id"), nullable=False),
                    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
                    sa.Column("status", sa.String(16), nullable=False),
                    sa.Column("result", sa.JSON(), nullable=False))
    op.create_index("ix_scans_site_id", "scans", ["site_id"])


def downgrade():
    for table in ("scans", "hour_buckets", "alerts", "incidents"):
        op.drop_table(table)
    op.drop_index("ix_events_pending", table_name="events")
    for name in ("findings", "processed_at"):
        op.drop_column("events", name)
    for name in ("verified_at", "verification_hash", "settings", "honeytokens"):
        op.drop_column("sites", name)
