"""baseline sqlalchemy migration setup

Revision ID: b0ee62b5a0ed
Revises: 
Create Date: 2026-07-15 08:40:42.747234

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'b0ee62b5a0ed'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "users" in inspector.get_table_names():
        user_columns = {column["name"] for column in inspector.get_columns("users")}
        if "employee_id" not in user_columns:
            with op.batch_alter_table("users") as batch:
                batch.add_column(sa.Column("employee_id", sa.Integer(), nullable=True))
    if "audit_logs" not in inspector.get_table_names():
        op.create_table(
            "audit_logs",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("company_id", sa.Integer(), nullable=False),
            sa.Column("user_id", sa.Integer(), nullable=True),
            sa.Column("action", sa.String(), nullable=False),
            sa.Column("entity", sa.String(), nullable=True),
            sa.Column("entity_id", sa.Integer(), nullable=True),
            sa.Column("details", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        )


def downgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "audit_logs" in inspector.get_table_names():
        op.drop_table("audit_logs")
    if "users" in inspector.get_table_names():
        user_columns = {column["name"] for column in inspector.get_columns("users")}
        if "employee_id" in user_columns:
            with op.batch_alter_table("users") as batch:
                batch.drop_column("employee_id")
