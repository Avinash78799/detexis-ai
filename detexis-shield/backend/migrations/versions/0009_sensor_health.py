"""Deduplicated sensor heartbeat-gap history, separate from attack incidents."""
from alembic import op
import sqlalchemy as sa

revision = "0009"
down_revision = "0008"
branch_labels = depends_on = None


def upgrade():
    with op.batch_alter_table("api_keys") as batch:
        batch.add_column(sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")))
    op.create_table("sensor_health_alerts",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("site_id", sa.String(36), sa.ForeignKey("sites.id"), nullable=False),
        sa.Column("opened_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("heartbeat_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resolution", sa.String(24), nullable=True))
    op.create_index("ix_sensor_health_site_opened", "sensor_health_alerts", ["site_id", "opened_at"])
    op.create_index("uq_sensor_health_open_site", "sensor_health_alerts", ["site_id"], unique=True,
                    postgresql_where=sa.text("resolved_at IS NULL"), sqlite_where=sa.text("resolved_at IS NULL"))


def downgrade():
    op.drop_table("sensor_health_alerts")
    with op.batch_alter_table("api_keys") as batch:
        batch.drop_column("created_at")
