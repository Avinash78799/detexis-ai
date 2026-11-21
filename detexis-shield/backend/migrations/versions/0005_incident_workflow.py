"""Incident triage and append-only action history."""
from alembic import op
import sqlalchemy as sa

revision = "0005"
down_revision = "0004"
branch_labels = depends_on = None


def upgrade():
    op.add_column("incidents", sa.Column("status", sa.String(20), nullable=False, server_default="open"))
    op.create_table("incident_actions", sa.Column("id", sa.Integer(), primary_key=True),
                    sa.Column("incident_id", sa.String(36), sa.ForeignKey("incidents.id"), nullable=False),
                    sa.Column("actor_id", sa.String(36), sa.ForeignKey("users.id"), nullable=True),
                    sa.Column("previous_status", sa.String(20), nullable=False),
                    sa.Column("status", sa.String(20), nullable=False),
                    sa.Column("note", sa.String(1000), nullable=False),
                    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False))
    op.create_index("ix_incident_actions_incident_id", "incident_actions", ["incident_id"])


def downgrade():
    op.drop_table("incident_actions")
    op.drop_column("incidents", "status")
