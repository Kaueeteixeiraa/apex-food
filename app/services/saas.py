import hashlib
import json
import secrets
from datetime import datetime, timedelta

from flask import g, request

from ..database import get_db, query_one


LICENSE_ACCESS_STATUSES = {"trial", "active", "grace_period"}


def utcnow():
    return datetime.utcnow().isoformat(timespec="seconds")


def parse_dt(value):
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00").replace("+00:00", ""))
    except ValueError:
        return None


def setting(key, default=None):
    row = query_one("SELECT value FROM platform_settings WHERE key=?", (key,))
    return row["value"] if row else default


def set_setting(key, value):
    db = get_db()
    db.execute(
        """
        INSERT INTO platform_settings (key, value, updated_at)
        VALUES (?, ?, CURRENT_TIMESTAMP)
        ON CONFLICT(key) DO UPDATE SET value=excluded.value, updated_at=CURRENT_TIMESTAMP
        """,
        (key, str(value)),
    )
    db.commit()


def log_platform(action, target_type=None, target_id=None, company_id=None, details=None):
    admin = getattr(g, "platform_admin", None)
    db = get_db()
    db.execute(
        """
        INSERT INTO platform_audit_logs
        (admin_id, action, target_type, target_id, company_id, details, ip_address)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            admin["id"] if admin else None,
            action,
            target_type,
            target_id,
            company_id,
            json.dumps(details or {}, ensure_ascii=False),
            request.headers.get("X-Forwarded-For", request.remote_addr),
        ),
    )
    db.commit()


def license_context(company_id):
    row = query_one(
        """
        SELECT company_licenses.*, plans.name plan_name, plans.slug plan_slug,
               plans.max_users, plans.max_products, plans.max_tables, plans.features_json,
               companies.status company_status, companies.blocked_at company_blocked_at
        FROM company_licenses
        JOIN companies ON companies.id=company_licenses.company_id
        LEFT JOIN plans ON plans.id=company_licenses.plan_id
        WHERE company_licenses.company_id=?
        """,
        (company_id,),
    )
    if not row:
        return {"license": None, "allowed": False, "message": "Empresa sem licenca ativa."}

    expires = parse_dt(row["expires_at"])
    grace = parse_dt(row["grace_period_ends_at"])
    now = datetime.utcnow()
    days = (expires.date() - now.date()).days if expires else None
    status = row["status"]
    allowed = status in LICENSE_ACCESS_STATUSES and (not expires or expires >= now or (grace and grace >= now))
    if status in {"blocked", "cancelled", "expired"} or row["company_status"] == "blocked":
        allowed = False
    message = ""
    if status == "trial" and days is not None:
        message = f"Seu periodo de teste termina em {max(days, 0)} dia(s)."
    elif status == "grace_period":
        message = "Sua licenca esta no periodo de tolerancia."
    elif not allowed:
        message = "O acesso da sua empresa ao Apex Food esta temporariamente indisponivel."

    return {"license": row, "allowed": allowed, "days_remaining": days, "message": message}


def renew_license(license_id, days=30, reason="renovacao manual"):
    db = get_db()
    license_row = db.execute("SELECT * FROM company_licenses WHERE id=?", (license_id,)).fetchone()
    if not license_row:
        return None
    base = parse_dt(license_row["expires_at"]) or datetime.utcnow()
    if base < datetime.utcnow():
        base = datetime.utcnow()
    new_expiry = base + timedelta(days=int(days or 30))
    db.execute(
        """
        UPDATE company_licenses
        SET status='active', expires_at=?, blocked_at=NULL, block_reason=NULL, updated_at=CURRENT_TIMESTAMP
        WHERE id=?
        """,
        (new_expiry.isoformat(timespec="seconds"), license_id),
    )
    db.commit()
    log_platform("license_renewed", "license", license_id, license_row["company_id"], {"days": days, "reason": reason})
    return new_expiry


def token_hash(token):
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def create_client_invite(company_id, user_id, admin_id=None, hours=72):
    token = secrets.token_urlsafe(32)
    expires = (datetime.utcnow() + timedelta(hours=hours)).isoformat(timespec="seconds")
    db = get_db()
    db.execute(
        "UPDATE client_invites SET revoked_at=CURRENT_TIMESTAMP WHERE company_id=? AND user_id=? AND used_at IS NULL AND revoked_at IS NULL",
        (company_id, user_id),
    )
    db.execute(
        """
        INSERT INTO client_invites (company_id, user_id, token_hash, expires_at, created_by_admin_id)
        VALUES (?, ?, ?, ?, ?)
        """,
        (company_id, user_id, token_hash(token), expires, admin_id),
    )
    return token
