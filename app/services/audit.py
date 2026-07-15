import json

from flask import g

from ..database import get_db


def log_audit(company_id, action, entity=None, entity_id=None, details=None):
    user_id = g.user["id"] if getattr(g, "user", None) else None
    payload = json.dumps(details or {}, ensure_ascii=False)
    db = get_db()
    db.execute(
        """
        INSERT INTO audit_logs (company_id, user_id, action, entity, entity_id, details)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (company_id, user_id, action, entity, entity_id, payload),
    )
    db.commit()
