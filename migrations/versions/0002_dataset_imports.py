"""Rastreia cargas concluídas por arquivo, preservando duplicatas da origem."""

from alembic import op
import sqlalchemy as sa

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "dataset_imports",
        sa.Column("table_name", sa.String(64), nullable=False),
        sa.Column("file_sha256", sa.String(64), nullable=False),
        sa.Column("row_count", sa.BigInteger(), nullable=False),
        sa.Column("imported_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("table_name", name="pk_dataset_imports"),
        schema="historical",
    )


def downgrade():
    op.drop_table("dataset_imports", schema="historical")
