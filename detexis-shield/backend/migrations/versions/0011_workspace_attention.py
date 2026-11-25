"""Index the small subset of incidents displayed in workspace attention."""

from alembic import op
from sqlalchemy import text


revision = "0011"
down_revision = "0010"
branch_labels = depends_on = None
INDEX_NAME = "ix_incidents_workspace_attention"


def upgrade():
    predicate = text("status = 'open' AND severity IN ('high', 'critical')")
    columns = ["site_id", "last_seen", "id"]
    if op.get_bind().dialect.name == "postgresql":
        # Keep incident ingestion writable while an existing history is indexed.
        with op.get_context().autocommit_block():
            op.create_index(INDEX_NAME, "incidents", columns, postgresql_where=predicate,
                            postgresql_concurrently=True)
    else:
        op.create_index(INDEX_NAME, "incidents", columns, sqlite_where=predicate)


def downgrade():
    if op.get_bind().dialect.name == "postgresql":
        with op.get_context().autocommit_block():
            op.drop_index(INDEX_NAME, table_name="incidents", postgresql_concurrently=True)
    else:
        op.drop_index(INDEX_NAME, table_name="incidents")
