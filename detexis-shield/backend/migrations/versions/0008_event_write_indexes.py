"""Index only pending recovery work and remove duplicate receipt-time coverage."""
from contextlib import nullcontext
from alembic import op
import sqlalchemy as sa

revision = "0008"
down_revision = "0007"
branch_labels = depends_on = None


def upgrade():
    postgres = op.get_bind().dialect.name == "postgresql"
    context = op.get_context().autocommit_block() if postgres else nullcontext()
    with context:
        options = ({"postgresql_where": sa.text("processed_at IS NULL"),
                    "postgresql_include": ["site_id", "event_id"], "postgresql_concurrently": True}
                   if postgres else {"sqlite_where": sa.text("processed_at IS NULL")})
        op.create_index("ix_events_unprocessed", "events", ["received_at"], **options)
        concurrent = {"postgresql_concurrently": True} if postgres else {}
        op.drop_index("ix_events_pending", table_name="events", **concurrent)
        # 0007 already covers this prefix, including the processing timestamp.
        op.drop_index("ix_events_site_received", table_name="events", **concurrent)


def downgrade():
    postgres = op.get_bind().dialect.name == "postgresql"
    context = op.get_context().autocommit_block() if postgres else nullcontext()
    with context:
        concurrent = {"postgresql_concurrently": True} if postgres else {}
        op.create_index("ix_events_pending", "events", ["processed_at", "received_at"], **concurrent)
        op.create_index("ix_events_site_received", "events", ["site_id", "received_at"], **concurrent)
        op.drop_index("ix_events_unprocessed", table_name="events", **concurrent)
