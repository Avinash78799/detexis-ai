"""Indexes for tenant feeds and server-time retention."""
from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = depends_on = None


def upgrade():
    op.create_index("ix_events_site_received", "events", ["site_id", "received_at"])
    op.create_index("ix_events_received", "events", ["received_at"])
    op.create_index("ix_incidents_site_seen", "incidents", ["site_id", "last_seen"])


def downgrade():
    op.drop_index("ix_incidents_site_seen", table_name="incidents")
    op.drop_index("ix_events_received", table_name="events")
    op.drop_index("ix_events_site_received", table_name="events")
