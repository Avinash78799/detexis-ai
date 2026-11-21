"""Cover the latest-event connection lookup for quiet, high-volume tenants."""
from alembic import op

revision = "0007"
down_revision = "0006"
branch_labels = depends_on = None


def upgrade():
    # Includes avoid heap reads for this status-only lookup in PostgreSQL. SQLite
    # ignores the dialect option and remains usable for local functional tests.
    if op.get_bind().dialect.name == "postgresql":
        # Building a large index must not hold a write-blocking table lock.
        with op.get_context().autocommit_block():
            op.create_index("ix_events_site_connection", "events", ["site_id", "received_at"],
                            postgresql_include=["processed_at"], postgresql_concurrently=True)
    else:
        op.create_index("ix_events_site_connection", "events", ["site_id", "received_at"])


def downgrade():
    if op.get_bind().dialect.name == "postgresql":
        with op.get_context().autocommit_block():
            op.drop_index("ix_events_site_connection", table_name="events", postgresql_concurrently=True)
    else:
        op.drop_index("ix_events_site_connection", table_name="events")
