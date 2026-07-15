"""saas platform admin

Revision ID: 20260715_saas
Revises: b0ee62b5a0ed
Create Date: 2026-07-15
"""
from alembic import op
import sqlalchemy as sa


revision = "20260715_saas"
down_revision = "b0ee62b5a0ed"
branch_labels = None
depends_on = None


def _add_missing(table, columns):
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if table not in inspector.get_table_names():
        return
    existing = {column["name"] for column in inspector.get_columns(table)}
    with op.batch_alter_table(table) as batch:
        for name, column in columns.items():
            if name not in existing:
                batch.add_column(column)


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())

    _add_missing("companies", {
        "responsible_name": sa.Column("responsible_name", sa.String(), nullable=True),
        "responsible_email": sa.Column("responsible_email", sa.String(), nullable=True),
        "address_number": sa.Column("address_number", sa.String(), nullable=True),
        "address_complement": sa.Column("address_complement", sa.String(), nullable=True),
        "neighborhood": sa.Column("neighborhood", sa.String(), nullable=True),
        "operation_modes": sa.Column("operation_modes", sa.Text(), nullable=True),
        "team_size": sa.Column("team_size", sa.String(), nullable=True),
        "status": sa.Column("status", sa.String(), nullable=False, server_default="active"),
        "onboarding_completed": sa.Column("onboarding_completed", sa.Integer(), nullable=False, server_default="0"),
        "last_access_at": sa.Column("last_access_at", sa.DateTime(), nullable=True),
        "blocked_at": sa.Column("blocked_at", sa.DateTime(), nullable=True),
    })
    _add_missing("users", {
        "phone": sa.Column("phone", sa.String(), nullable=True),
        "active": sa.Column("active", sa.Integer(), nullable=False, server_default="1"),
        "last_login_at": sa.Column("last_login_at", sa.DateTime(), nullable=True),
    })

    if "platform_admins" not in tables:
        op.create_table(
            "platform_admins",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("name", sa.String(), nullable=False),
            sa.Column("email", sa.String(), nullable=False, unique=True),
            sa.Column("password_hash", sa.String(), nullable=False),
            sa.Column("role", sa.String(), nullable=False, server_default="Suporte"),
            sa.Column("active", sa.Integer(), nullable=False, server_default="1"),
            sa.Column("last_login_at", sa.DateTime(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        )
    if "plans" not in tables:
        op.create_table(
            "plans",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("name", sa.String(), nullable=False),
            sa.Column("slug", sa.String(), nullable=False, unique=True),
            sa.Column("description", sa.Text(), nullable=True),
            sa.Column("monthly_price", sa.Numeric(), nullable=False, server_default="0"),
            sa.Column("annual_price", sa.Numeric(), nullable=False, server_default="0"),
            sa.Column("active", sa.Integer(), nullable=False, server_default="1"),
            sa.Column("archived", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("trial_days", sa.Integer(), nullable=False, server_default="7"),
            sa.Column("max_users", sa.Integer(), nullable=True),
            sa.Column("max_products", sa.Integer(), nullable=True),
            sa.Column("max_tables", sa.Integer(), nullable=True),
            sa.Column("features_json", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        )
    if "company_licenses" not in tables:
        op.create_table(
            "company_licenses",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("company_id", sa.Integer(), nullable=False, unique=True),
            sa.Column("plan_id", sa.Integer(), nullable=True),
            sa.Column("status", sa.String(), nullable=False, server_default="trial"),
            sa.Column("starts_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.Column("expires_at", sa.DateTime(), nullable=True),
            sa.Column("trial_ends_at", sa.DateTime(), nullable=True),
            sa.Column("auto_renew", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("grace_period_ends_at", sa.DateTime(), nullable=True),
            sa.Column("blocked_at", sa.DateTime(), nullable=True),
            sa.Column("block_reason", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        )
    if "subscription_payments" not in tables:
        op.create_table(
            "subscription_payments",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("company_id", sa.Integer(), nullable=False),
            sa.Column("license_id", sa.Integer(), nullable=True),
            sa.Column("amount", sa.Numeric(), nullable=False, server_default="0"),
            sa.Column("currency", sa.String(), nullable=False, server_default="BRL"),
            sa.Column("status", sa.String(), nullable=False, server_default="pending"),
            sa.Column("payment_method", sa.String(), nullable=True),
            sa.Column("external_reference", sa.String(), nullable=True),
            sa.Column("admin_note", sa.Text(), nullable=True),
            sa.Column("due_at", sa.DateTime(), nullable=True),
            sa.Column("paid_at", sa.DateTime(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        )
    if "platform_settings" not in tables:
        op.create_table("platform_settings", sa.Column("key", sa.String(), primary_key=True), sa.Column("value", sa.Text()), sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()))
    if "platform_audit_logs" not in tables:
        op.create_table("platform_audit_logs", sa.Column("id", sa.Integer(), primary_key=True), sa.Column("admin_id", sa.Integer()), sa.Column("action", sa.String(), nullable=False), sa.Column("target_type", sa.String()), sa.Column("target_id", sa.Integer()), sa.Column("company_id", sa.Integer()), sa.Column("details", sa.Text()), sa.Column("ip_address", sa.String()), sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()))
    if "password_reset_tokens" not in tables:
        op.create_table("password_reset_tokens", sa.Column("id", sa.Integer(), primary_key=True), sa.Column("user_type", sa.String(), nullable=False), sa.Column("user_id", sa.Integer(), nullable=False), sa.Column("token_hash", sa.String(), nullable=False, unique=True), sa.Column("expires_at", sa.DateTime(), nullable=False), sa.Column("used_at", sa.DateTime()), sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()))
    if "client_invites" not in tables:
        op.create_table(
            "client_invites",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("company_id", sa.Integer(), nullable=False),
            sa.Column("user_id", sa.Integer(), nullable=False),
            sa.Column("token_hash", sa.String(), nullable=False, unique=True),
            sa.Column("expires_at", sa.DateTime(), nullable=False),
            sa.Column("used_at", sa.DateTime()),
            sa.Column("revoked_at", sa.DateTime()),
            sa.Column("created_by_admin_id", sa.Integer()),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        )


def downgrade():
    for table in ("client_invites", "password_reset_tokens", "platform_audit_logs", "platform_settings", "subscription_payments", "company_licenses", "plans", "platform_admins"):
        op.drop_table(table)
