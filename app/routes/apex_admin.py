import sqlite3
from datetime import datetime, timedelta

from flask import Blueprint, abort, flash, g, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash

from ..database import get_db, query_all, query_one
from ..services.saas import create_client_invite, log_platform, parse_dt, renew_license, set_setting, setting
from .auth import platform_admin_required

bp = Blueprint("apex_admin", __name__, url_prefix="/apex-admin")


def _value(sql, params=()):
    row = query_one(sql, params)
    return row["value"] if row else 0


def _plans():
    return query_all("SELECT * FROM plans WHERE archived=0 ORDER BY active DESC, id")


def _license_rows(where="", params=()):
    return query_all(
        f"""
        SELECT company_licenses.*, companies.trade_name, companies.responsible_name,
               companies.email, companies.phone, plans.name plan_name,
               CAST(julianday(company_licenses.expires_at)-julianday('now') AS INTEGER) days_remaining
        FROM company_licenses
        JOIN companies ON companies.id=company_licenses.company_id
        LEFT JOIN plans ON plans.id=company_licenses.plan_id
        {where}
        ORDER BY company_licenses.expires_at IS NULL, company_licenses.expires_at
        """,
        params,
    )


@bp.route("/login", methods=("GET", "POST"))
def login():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        admin = query_one("SELECT * FROM platform_admins WHERE lower(email)=? AND active=1", (email,))
        if not admin or not check_password_hash(admin["password_hash"], password):
            flash("E-mail ou senha invalidos.", "error")
        else:
            session.clear()
            session["platform_admin_id"] = admin["id"]
            session["platform_admin_role"] = admin["role"]
            db = get_db()
            db.execute("UPDATE platform_admins SET last_login_at=CURRENT_TIMESTAMP WHERE id=?", (admin["id"],))
            db.commit()
            g.platform_admin = admin
            log_platform("platform_admin_login", "platform_admin", admin["id"])
            return redirect(url_for("apex_admin.dashboard"))
    return render_template("apex_admin/login.html")


@bp.get("/logout")
def logout():
    session.clear()
    flash("Sessao Apex Admin encerrada.", "success")
    return redirect(url_for("apex_admin.login"))


@bp.get("/")
@platform_admin_required
def dashboard():
    soon = (datetime.utcnow() + timedelta(days=7)).isoformat(timespec="seconds")
    now = datetime.utcnow()
    period_label = f"01/{now:%m/%Y} - {now:%d/%m/%Y}"
    stats = {
        "active_clients": _value("SELECT COUNT(*) value FROM companies WHERE status='active'"),
        "trial_clients": _value("SELECT COUNT(*) value FROM company_licenses WHERE status='trial'"),
        "expiring": _value("SELECT COUNT(*) value FROM company_licenses WHERE expires_at BETWEEN CURRENT_TIMESTAMP AND ?", (soon,)),
        "expired": _value("SELECT COUNT(*) value FROM company_licenses WHERE status IN ('expired','blocked') OR expires_at < CURRENT_TIMESTAMP"),
        "monthly_revenue": _value("SELECT COALESCE(SUM(amount),0) value FROM subscription_payments WHERE status='paid' AND date(paid_at)>=date('now','start of month')"),
        "pending_payments": _value("SELECT COUNT(*) value FROM subscription_payments WHERE status IN ('pending','overdue')"),
        "overdue_payments": _value("SELECT COUNT(*) value FROM subscription_payments WHERE status='overdue'"),
        "new_clients": _value("SELECT COUNT(*) value FROM companies WHERE date(created_at)>=date('now','start of month')"),
        "blocked": _value("SELECT COUNT(*) value FROM companies WHERE status='blocked'"),
        "grace": _value("SELECT COUNT(*) value FROM company_licenses WHERE status='grace_period'"),
        "pending_invites": _value("SELECT COUNT(*) value FROM client_invites WHERE used_at IS NULL AND revoked_at IS NULL"),
    }
    attention = _license_rows("WHERE company_licenses.status IN ('past_due','expired','blocked') OR company_licenses.expires_at <= ?", (soon,))
    recent_clients = query_all(
        """
        SELECT companies.id, companies.trade_name, companies.responsible_name, companies.last_access_at,
               company_licenses.status license_status, company_licenses.expires_at, plans.name plan_name
        FROM companies
        LEFT JOIN company_licenses ON company_licenses.company_id=companies.id
        LEFT JOIN plans ON plans.id=company_licenses.plan_id
        ORDER BY companies.created_at DESC
        LIMIT 6
        """
    )
    pending_invites = query_all(
        """
        SELECT companies.trade_name, users.email, client_invites.expires_at
        FROM client_invites
        JOIN companies ON companies.id=client_invites.company_id
        JOIN users ON users.id=client_invites.user_id
        WHERE client_invites.used_at IS NULL AND client_invites.revoked_at IS NULL
        ORDER BY client_invites.created_at DESC
        LIMIT 5
        """
    )
    return render_template("apex_admin/dashboard.html", stats=stats, attention=attention[:8], recent_clients=recent_clients, pending_invites=pending_invites, period_label=period_label)


@bp.get("/clients")
@platform_admin_required
def clients():
    q = request.args.get("q", "").strip()
    status = request.args.get("status", "all")
    plan = request.args.get("plan", "all")
    clauses = []
    params = []
    if status != "all":
        if status == "trial":
            clauses.append("company_licenses.status='trial'")
        elif status == "expiring":
            clauses.append("company_licenses.expires_at BETWEEN CURRENT_TIMESTAMP AND date('now','+7 days')")
        elif status == "expired":
            clauses.append("(company_licenses.status IN ('expired','blocked') OR company_licenses.expires_at < CURRENT_TIMESTAMP)")
        else:
            clauses.append("companies.status=?")
            params.append(status)
    if q:
        clauses.append("(companies.trade_name LIKE ? OR companies.responsible_name LIKE ? OR companies.email LIKE ? OR companies.cnpj LIKE ?)")
        params.extend([f"%{q}%"] * 4)
    if plan != "all":
        clauses.append("plans.slug=?")
        params.append(plan)
    where = "WHERE " + " AND ".join(clauses) if clauses else ""
    rows = query_all(
        f"""
        SELECT companies.*, company_licenses.status license_status, company_licenses.expires_at,
               plans.name plan_name
        FROM companies
        LEFT JOIN company_licenses ON company_licenses.company_id=companies.id
        LEFT JOIN plans ON plans.id=company_licenses.plan_id
        {where}
        ORDER BY companies.created_at DESC
        """,
        params,
    )
    return render_template("apex_admin/clients.html", clients=rows, status=status, q=q, plan=plan, plans=_plans())


@bp.route("/clients/new", methods=("GET", "POST"))
@platform_admin_required
def new_client():
    plans = _plans()
    if request.method == "POST":
        form = request.form
        required = ["trade_name", "legal_name", "document", "segment", "email", "phone", "cep", "address", "address_number", "neighborhood", "city", "state", "responsible_name", "responsible_email", "responsible_phone", "responsible_role", "plan_id", "starts_at", "expires_at", "license_status"]
        missing = [field for field in required if not form.get(field, "").strip()]
        if missing:
            flash("Preencha todos os campos obrigatorios.", "error")
            return render_template("apex_admin/client_form.html", plans=plans, form=form)
        if form["license_status"] not in {"trial", "active", "grace_period", "expired", "blocked", "cancelled"}:
            flash("Status de licenca invalido.", "error")
            return render_template("apex_admin/client_form.html", plans=plans, form=form)

        db = get_db()
        try:
            db.execute("BEGIN")
            company = db.execute(
                """
                INSERT INTO companies
                (legal_name, trade_name, cnpj, email, phone, segment, address, city, state, cep,
                 responsible_name, responsible_email, address_number, address_complement, neighborhood,
                 team_size, status)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'active')
                """,
                (
                    form["legal_name"].strip(),
                    form["trade_name"].strip(),
                    form["document"].strip(),
                    form["email"].strip().lower(),
                    form["phone"].strip(),
                    form["segment"].strip(),
                    form["address"].strip(),
                    form["city"].strip(),
                    form["state"].strip().upper(),
                    form["cep"].strip(),
                    form["responsible_name"].strip(),
                    form["responsible_email"].strip().lower(),
                    form["address_number"].strip(),
                    form.get("address_complement", "").strip(),
                    form["neighborhood"].strip(),
                    form.get("team_size", "").strip(),
                ),
            )
            company_id = company.lastrowid
            employee = db.execute(
                "INSERT INTO employees (company_id, name, role, email, phone, permission) VALUES (?, ?, ?, ?, ?, 'Administrador')",
                (company_id, form["responsible_name"].strip(), form["responsible_role"].strip(), form["responsible_email"].strip().lower(), form["responsible_phone"].strip()),
            )
            user = db.execute(
                """
                INSERT INTO users (company_id, employee_id, name, email, password_hash, role, phone, active)
                VALUES (?, ?, ?, ?, ?, 'Administrador', ?, 0)
                """,
                (company_id, employee.lastrowid, form["responsible_name"].strip(), form["responsible_email"].strip().lower(), generate_password_hash("__invite_pending__"), form["responsible_phone"].strip()),
            )
            db.execute(
                """
                INSERT INTO company_licenses
                (company_id, plan_id, status, starts_at, expires_at, trial_ends_at, auto_renew, block_reason)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    company_id,
                    form["plan_id"],
                    form["license_status"],
                    form["starts_at"],
                    form["expires_at"],
                    form.get("trial_ends_at") or None,
                    1 if form.get("auto_renew") else 0,
                    form.get("admin_note", "").strip(),
                ),
            )
            token = create_client_invite(company_id, user.lastrowid, session.get("platform_admin_id"))
            db.commit()
        except sqlite3.IntegrityError:
            db.rollback()
            flash("Empresa ou usuario ja cadastrado com esses dados.", "error")
            return render_template("apex_admin/client_form.html", plans=plans, form=form)
        except Exception:
            db.rollback()
            raise

        log_platform("client_created", "company", company_id, company_id, {"plan_id": form["plan_id"], "status": form["license_status"]})
        invite_link = url_for("auth.accept_invite", token=token, _external=True)
        flash(f"Cliente criado. Link de convite: {invite_link}", "success")
        return redirect(url_for("apex_admin.client_detail", company_id=company_id, invite=token))
    return render_template("apex_admin/client_form.html", plans=plans, form={})


@bp.get("/clients/<int:company_id>")
@platform_admin_required
def client_detail(company_id):
    company = query_one("SELECT * FROM companies WHERE id=?", (company_id,))
    if not company:
        abort(404)
    users = query_all("SELECT id, name, email, role, active, last_login_at, created_at FROM users WHERE company_id=? ORDER BY name", (company_id,))
    license_row = query_one(
        "SELECT company_licenses.*, plans.name plan_name FROM company_licenses LEFT JOIN plans ON plans.id=company_licenses.plan_id WHERE company_id=?",
        (company_id,),
    )
    payments = query_all("SELECT * FROM subscription_payments WHERE company_id=? ORDER BY created_at DESC LIMIT 10", (company_id,))
    audit = query_all("SELECT * FROM platform_audit_logs WHERE company_id=? ORDER BY created_at DESC LIMIT 12", (company_id,))
    invite = query_one(
        """
        SELECT client_invites.*, users.email
        FROM client_invites
        JOIN users ON users.id=client_invites.user_id
        WHERE client_invites.company_id=? AND client_invites.used_at IS NULL AND client_invites.revoked_at IS NULL
        ORDER BY client_invites.created_at DESC
        LIMIT 1
        """,
        (company_id,),
    )
    invite_token = request.args.get("invite", "")
    invite_link = url_for("auth.accept_invite", token=invite_token, _external=True) if invite_token else ""
    return render_template("apex_admin/client_detail.html", company=company, users=users, license=license_row, payments=payments, audit=audit, plans=_plans(), invite=invite, invite_link=invite_link)


@bp.post("/clients/<int:company_id>/invite")
@platform_admin_required
def generate_invite(company_id):
    user = query_one("SELECT id FROM users WHERE company_id=? AND role='Administrador' ORDER BY id LIMIT 1", (company_id,))
    if not user:
        abort(404)
    token = create_client_invite(company_id, user["id"], session.get("platform_admin_id"))
    get_db().commit()
    log_platform("client_invite_created", "company", company_id, company_id)
    flash("Novo convite gerado.", "success")
    return redirect(url_for("apex_admin.client_detail", company_id=company_id, invite=token))


@bp.post("/clients/<int:company_id>/invite/revoke")
@platform_admin_required
def revoke_invite(company_id):
    db = get_db()
    db.execute("UPDATE client_invites SET revoked_at=CURRENT_TIMESTAMP WHERE company_id=? AND used_at IS NULL AND revoked_at IS NULL", (company_id,))
    db.commit()
    log_platform("client_invite_revoked", "company", company_id, company_id)
    flash("Convite invalidado.", "success")
    return redirect(url_for("apex_admin.client_detail", company_id=company_id))


@bp.post("/clients/<int:company_id>/block")
@platform_admin_required
def block_client(company_id):
    reason = request.form.get("reason", "Bloqueio administrativo").strip()
    db = get_db()
    db.execute("UPDATE companies SET status='blocked', blocked_at=CURRENT_TIMESTAMP WHERE id=?", (company_id,))
    db.execute("UPDATE company_licenses SET status='blocked', blocked_at=CURRENT_TIMESTAMP, block_reason=?, updated_at=CURRENT_TIMESTAMP WHERE company_id=?", (reason, company_id))
    db.commit()
    log_platform("client_blocked", "company", company_id, company_id, {"reason": reason})
    flash("Cliente bloqueado.", "success")
    return redirect(url_for("apex_admin.client_detail", company_id=company_id))


@bp.post("/clients/<int:company_id>/unblock")
@platform_admin_required
def unblock_client(company_id):
    db = get_db()
    db.execute("UPDATE companies SET status='active', blocked_at=NULL WHERE id=?", (company_id,))
    db.execute("UPDATE company_licenses SET status='active', blocked_at=NULL, block_reason=NULL, updated_at=CURRENT_TIMESTAMP WHERE company_id=?", (company_id,))
    db.commit()
    log_platform("client_unblocked", "company", company_id, company_id)
    flash("Cliente liberado.", "success")
    return redirect(url_for("apex_admin.client_detail", company_id=company_id))


@bp.post("/clients/<int:company_id>/impersonate")
@platform_admin_required
def impersonate(company_id):
    if session.get("platform_admin_role") != "Super Admin":
        abort(403)
    user = query_one("SELECT * FROM users WHERE company_id=? AND role='Administrador' AND active=1 ORDER BY id LIMIT 1", (company_id,))
    company = query_one("SELECT trade_name FROM companies WHERE id=?", (company_id,))
    if not user or not company:
        abort(404)
    session["user_id"] = user["id"]
    session["company_id"] = user["company_id"]
    session["user_name"] = user["name"]
    session["company_name"] = company["trade_name"]
    session["role"] = user["role"]
    session["impersonated_by"] = session["platform_admin_id"]
    session["impersonated_company_id"] = company_id
    log_platform("impersonation_started", "company", company_id, company_id)
    return redirect(url_for("dashboard.index"))


@bp.post("/impersonation/stop")
@platform_admin_required
def stop_impersonation():
    company_id = session.get("impersonated_company_id")
    for key in ("user_id", "company_id", "user_name", "company_name", "role", "impersonated_by", "impersonated_company_id"):
        session.pop(key, None)
    log_platform("impersonation_finished", "company", company_id, company_id)
    return redirect(url_for("apex_admin.client_detail", company_id=company_id))


@bp.route("/plans", methods=("GET", "POST"))
@platform_admin_required
def plans():
    if request.method == "POST":
        form = request.form
        db = get_db()
        db.execute(
            """
            INSERT INTO plans
            (name, slug, description, monthly_price, annual_price, trial_days, max_users, max_products, max_tables, active, features_json)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                form.get("name", "").strip(),
                form.get("slug", "").strip().lower(),
                form.get("description", "").strip(),
                float(form.get("monthly_price") or 0),
                float(form.get("annual_price") or 0),
                int(form.get("trial_days") or 7),
                int(form.get("max_users") or 0),
                int(form.get("max_products") or 0),
                int(form.get("max_tables") or 0),
                1 if form.get("active") else 0,
                form.get("features_json", "[]").strip() or "[]",
            ),
        )
        db.commit()
        log_platform("plan_created", "plan")
        return redirect(url_for("apex_admin.plans"))
    return render_template("apex_admin/plans.html", plans=_plans())


@bp.post("/plans/<int:plan_id>/toggle")
@platform_admin_required
def toggle_plan(plan_id):
    db = get_db()
    db.execute("UPDATE plans SET active=CASE active WHEN 1 THEN 0 ELSE 1 END, updated_at=CURRENT_TIMESTAMP WHERE id=?", (plan_id,))
    db.commit()
    log_platform("plan_toggled", "plan", plan_id)
    return redirect(url_for("apex_admin.plans"))


@bp.get("/licenses")
@platform_admin_required
def licenses():
    return render_template("apex_admin/licenses.html", licenses=_license_rows(), plans=_plans())


@bp.post("/licenses/<int:license_id>/renew")
@platform_admin_required
def renew(license_id):
    renew_license(license_id, int(request.form.get("days") or 30), request.form.get("reason", "renovacao manual"))
    flash("Licenca renovada.", "success")
    return redirect(request.referrer or url_for("apex_admin.licenses"))


@bp.post("/licenses/<int:license_id>/plan")
@platform_admin_required
def change_plan(license_id):
    db = get_db()
    plan_id = request.form.get("plan_id")
    license_row = db.execute("SELECT company_id FROM company_licenses WHERE id=?", (license_id,)).fetchone()
    db.execute("UPDATE company_licenses SET plan_id=?, updated_at=CURRENT_TIMESTAMP WHERE id=?", (plan_id, license_id))
    db.commit()
    log_platform("license_plan_changed", "license", license_id, license_row["company_id"] if license_row else None, {"plan_id": plan_id})
    return redirect(request.referrer or url_for("apex_admin.licenses"))


@bp.post("/licenses/<int:license_id>/days")
@platform_admin_required
def adjust_license_days(license_id):
    days = int(request.form.get("days") or 0)
    reason = request.form.get("reason", "").strip()
    if not reason or not days:
        flash("Informe dias e motivo.", "error")
        return redirect(request.referrer or url_for("apex_admin.licenses"))
    db = get_db()
    license_row = db.execute("SELECT * FROM company_licenses WHERE id=?", (license_id,)).fetchone()
    if not license_row:
        abort(404)
    base = parse_dt(license_row["expires_at"]) or datetime.utcnow()
    new_expiry = base + timedelta(days=days)
    db.execute("UPDATE company_licenses SET expires_at=?, updated_at=CURRENT_TIMESTAMP WHERE id=?", (new_expiry.isoformat(timespec="seconds"), license_id))
    db.commit()
    log_platform("license_days_adjusted", "license", license_id, license_row["company_id"], {"days": days, "reason": reason})
    flash("Licenca ajustada.", "success")
    return redirect(request.referrer or url_for("apex_admin.licenses"))


@bp.post("/licenses/<int:license_id>/status")
@platform_admin_required
def set_license_status(license_id):
    status = request.form.get("status", "")
    reason = request.form.get("reason", "").strip()
    allowed = {"trial", "active", "grace_period", "expired", "blocked", "cancelled"}
    if status not in allowed or status in {"blocked", "cancelled"} and not reason:
        flash("Status ou motivo invalido.", "error")
        return redirect(request.referrer or url_for("apex_admin.licenses"))
    db = get_db()
    license_row = db.execute("SELECT company_id FROM company_licenses WHERE id=?", (license_id,)).fetchone()
    if not license_row:
        abort(404)
    db.execute(
        """
        UPDATE company_licenses
        SET status=?, block_reason=?, blocked_at=CASE WHEN ?='blocked' THEN CURRENT_TIMESTAMP ELSE blocked_at END, updated_at=CURRENT_TIMESTAMP
        WHERE id=?
        """,
        (status, reason, status, license_id),
    )
    if status == "blocked":
        db.execute("UPDATE companies SET status='blocked', blocked_at=CURRENT_TIMESTAMP WHERE id=?", (license_row["company_id"],))
    elif status == "active":
        db.execute("UPDATE companies SET status='active', blocked_at=NULL WHERE id=?", (license_row["company_id"],))
    db.commit()
    log_platform("license_status_changed", "license", license_id, license_row["company_id"], {"status": status, "reason": reason})
    flash("Status da licenca atualizado.", "success")
    return redirect(request.referrer or url_for("apex_admin.licenses"))


@bp.route("/payments", methods=("GET", "POST"))
@platform_admin_required
def payments():
    db = get_db()
    if request.method == "POST":
        company_id = request.form.get("company_id")
        license_row = db.execute("SELECT id FROM company_licenses WHERE company_id=?", (company_id,)).fetchone()
        db.execute(
            """
            INSERT INTO subscription_payments
            (company_id, license_id, amount, status, payment_method, external_reference, admin_note, due_at)
            VALUES (?, ?, ?, 'pending', ?, ?, ?, ?)
            """,
            (
                company_id,
                license_row["id"] if license_row else None,
                float(request.form.get("amount") or 0),
                request.form.get("payment_method", "manual"),
                request.form.get("external_reference", "").strip(),
                request.form.get("admin_note", "").strip(),
                request.form.get("due_at") or None,
            ),
        )
        db.commit()
        log_platform("payment_created", "payment", company_id, company_id)
        return redirect(url_for("apex_admin.payments"))
    rows = query_all(
        """
        SELECT subscription_payments.*, companies.trade_name
        FROM subscription_payments
        JOIN companies ON companies.id=subscription_payments.company_id
        ORDER BY subscription_payments.created_at DESC
        """
    )
    companies = query_all("SELECT id, trade_name FROM companies ORDER BY trade_name")
    return render_template("apex_admin/payments.html", payments=rows, companies=companies)


@bp.post("/payments/<int:payment_id>/confirm")
@platform_admin_required
def confirm_payment(payment_id):
    db = get_db()
    payment = db.execute("SELECT * FROM subscription_payments WHERE id=?", (payment_id,)).fetchone()
    if payment and payment["status"] != "paid":
        db.execute("UPDATE subscription_payments SET status='paid', paid_at=CURRENT_TIMESTAMP, updated_at=CURRENT_TIMESTAMP WHERE id=?", (payment_id,))
        db.commit()
        if payment["license_id"]:
            renew_license(payment["license_id"], 30, f"pagamento #{payment_id}")
        log_platform("payment_confirmed", "payment", payment_id, payment["company_id"])
    return redirect(url_for("apex_admin.payments"))


@bp.post("/payments/<int:payment_id>/cancel")
@platform_admin_required
def cancel_payment(payment_id):
    db = get_db()
    payment = db.execute("SELECT company_id FROM subscription_payments WHERE id=?", (payment_id,)).fetchone()
    db.execute("UPDATE subscription_payments SET status='cancelled', updated_at=CURRENT_TIMESTAMP WHERE id=? AND status!='paid'", (payment_id,))
    db.commit()
    log_platform("payment_cancelled", "payment", payment_id, payment["company_id"] if payment else None)
    return redirect(url_for("apex_admin.payments"))


@bp.post("/payments/<int:payment_id>/overdue")
@platform_admin_required
def overdue_payment(payment_id):
    db = get_db()
    payment = db.execute("SELECT company_id FROM subscription_payments WHERE id=?", (payment_id,)).fetchone()
    db.execute("UPDATE subscription_payments SET status='overdue', updated_at=CURRENT_TIMESTAMP WHERE id=? AND status='pending'", (payment_id,))
    db.commit()
    log_platform("payment_overdue", "payment", payment_id, payment["company_id"] if payment else None)
    return redirect(url_for("apex_admin.payments"))


@bp.post("/payments/<int:payment_id>/refund")
@platform_admin_required
def refund_payment(payment_id):
    db = get_db()
    payment = db.execute("SELECT company_id FROM subscription_payments WHERE id=?", (payment_id,)).fetchone()
    db.execute("UPDATE subscription_payments SET status='refunded', updated_at=CURRENT_TIMESTAMP WHERE id=? AND status='paid'", (payment_id,))
    db.commit()
    log_platform("payment_refunded", "payment", payment_id, payment["company_id"] if payment else None)
    return redirect(url_for("apex_admin.payments"))


@bp.route("/settings", methods=("GET", "POST"))
@platform_admin_required
def settings():
    keys = ["product_name", "support_email", "default_grace_days", "default_plan_slug", "maintenance_mode", "maintenance_message"]
    if request.method == "POST":
        for key in keys:
            set_setting(key, request.form.get(key, "0" if key.endswith("_enabled") or key == "maintenance_mode" else ""))
        log_platform("platform_settings_updated", "settings")
        flash("Configuracoes salvas.", "success")
        return redirect(url_for("apex_admin.settings"))
    values = {key: setting(key, "") for key in keys}
    return render_template("apex_admin/settings.html", settings=values, plans=_plans())


@bp.route("/admins", methods=("GET", "POST"))
@platform_admin_required
def admins():
    if request.method == "POST":
        if session.get("platform_admin_role") != "Super Admin":
            abort(403)
        form = request.form
        db = get_db()
        db.execute(
            "INSERT INTO platform_admins (name, email, password_hash, role, active) VALUES (?, ?, ?, ?, 1)",
            (form["name"].strip(), form["email"].strip().lower(), generate_password_hash(form["password"]), form.get("role", "Suporte")),
        )
        db.commit()
        log_platform("platform_admin_created", "platform_admin")
        return redirect(url_for("apex_admin.admins"))
    rows = query_all("SELECT id, name, email, role, active, last_login_at, created_at FROM platform_admins ORDER BY id")
    return render_template("apex_admin/admins.html", admins=rows)


@bp.get("/audit")
@platform_admin_required
def audit():
    rows = query_all(
        """
        SELECT platform_audit_logs.*, platform_admins.name admin_name, companies.trade_name
        FROM platform_audit_logs
        LEFT JOIN platform_admins ON platform_admins.id=platform_audit_logs.admin_id
        LEFT JOIN companies ON companies.id=platform_audit_logs.company_id
        ORDER BY platform_audit_logs.created_at DESC
        LIMIT 150
        """
    )
    return render_template("apex_admin/audit.html", rows=rows)
