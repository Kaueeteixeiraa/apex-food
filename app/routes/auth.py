import secrets
from datetime import datetime, timedelta
from functools import wraps

from flask import Blueprint, abort, current_app, flash, g, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash

from ..database import get_db, query_one
from ..services.saas import license_context, setting, token_hash

bp = Blueprint("auth", __name__, url_prefix="/auth")

ROLE_HOME = {
    "Administrador": "dashboard.index",
    "Gerente": "dashboard.index",
    "Caixa": "pos.index",
    "Garcom": "floor.index",
    "Cozinha": "kitchen.index",
    "Estoque": "inventory.index",
    "Entregador": "pages.delivery",
}

ROLE_ENDPOINTS = {
    "Gerente": ("dashboard.", "orders.", "floor.", "kitchen.", "products.", "inventory.", "clients.", "pages.reports", "pages.categories", "pages.delivery", "pos."),
    "Caixa": ("pos.", "orders."),
    "Garcom": ("floor.", "orders."),
    "Cozinha": ("kitchen.",),
    "Estoque": ("products.", "inventory."),
    "Entregador": ("orders.", "pages.delivery"),
}

LICENSE_EXEMPT_ENDPOINTS = {
    "static",
    "index",
    "auth.login",
    "auth.register",
    "auth.accept_invite",
    "auth.forgot_password",
    "auth.reset_password",
    "auth.logout",
    "pages.subscription",
    "pages.maintenance",
    "pages.onboarding",
    "pages.finish_onboarding",
}


@bp.before_app_request
def load_logged_in_user():
    endpoint = request.endpoint or ""
    g.platform_admin = None
    platform_admin_id = session.get("platform_admin_id")
    if platform_admin_id:
        g.platform_admin = query_one("SELECT * FROM platform_admins WHERE id=? AND active=1", (platform_admin_id,))
        if g.platform_admin is None:
            session.pop("platform_admin_id", None)

    if setting("maintenance_mode", "0") == "1" and not endpoint.startswith(("apex_admin.", "auth.")) and endpoint != "static":
        if not g.platform_admin:
            return render_template("maintenance.html", message=setting("maintenance_message")), 503

    user_id = session.get("user_id")
    if user_id is None:
        g.user = None
        return

    g.user = query_one(
        """
        SELECT users.*, companies.trade_name AS company_name, companies.status AS company_status,
               companies.onboarding_completed
        FROM users
        JOIN companies ON companies.id = users.company_id
        WHERE users.id = ?
        """,
        (user_id,),
    )
    if g.user is None or not g.user["active"] or (g.user["company_status"] == "blocked" and not session.get("impersonated_by")):
        session.clear()
        flash("Seu acesso esta indisponivel. Fale com o suporte.", "error")
        return redirect(url_for("auth.login"))

    g.license_context = license_context(g.user["company_id"])
    if g.user is not None and not _can_access(request.endpoint or ""):
        abort(403)
    if endpoint not in LICENSE_EXEMPT_ENDPOINTS and not endpoint.startswith(("auth.", "apex_admin.")):
        if not g.license_context["allowed"] and not session.get("impersonated_by"):
            return redirect(url_for("pages.subscription"))


def _can_access(endpoint):
    if endpoint == "static" or endpoint.startswith("auth."):
        return True
    if g.user is None or g.user["role"] == "Administrador":
        return True
    return any(endpoint.startswith(prefix) for prefix in ROLE_ENDPOINTS.get(g.user["role"], ()))


def login_required(view):
    @wraps(view)
    def wrapped_view(**kwargs):
        if g.user is None:
            return redirect(url_for("auth.login"))
        return view(**kwargs)

    return wrapped_view


company_user_required = login_required


def active_license_required(view):
    @wraps(view)
    def wrapped_view(**kwargs):
        context = getattr(g, "license_context", None)
        if context and not context["allowed"] and not session.get("impersonated_by"):
            return redirect(url_for("pages.subscription"))
        return view(**kwargs)

    return wrapped_view


def platform_admin_required(view):
    @wraps(view)
    def wrapped_view(**kwargs):
        if g.platform_admin is None:
            return redirect(url_for("apex_admin.login"))
        return view(**kwargs)

    return wrapped_view


def company_id():
    return session.get("company_id")


@bp.route("/login", methods=("GET", "POST"))
def login():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        attempts = [item for item in session.get("login_attempts", []) if datetime.utcnow().timestamp() - item < 600]
        if len(attempts) >= 6:
            flash("Muitas tentativas. Aguarde alguns minutos e tente novamente.", "error")
            session["login_attempts"] = attempts
            return render_template("auth/login.html", email=email)
        user = query_one(
            """
            SELECT users.*, companies.trade_name AS company_name, companies.onboarding_completed,
                   companies.status AS company_status
            FROM users
            JOIN companies ON companies.id = users.company_id
            WHERE lower(users.email) = ?
            """,
            (email,),
        )

        if user is None or not check_password_hash(user["password_hash"], password):
            attempts.append(datetime.utcnow().timestamp())
            session["login_attempts"] = attempts
            current_app.logger.warning("Tentativa de login invalida para %s", email)
            flash("E-mail ou senha incorretos.", "error")
        elif not user["active"]:
            flash("Este acesso esta desativado ou ainda nao foi ativado.", "error")
        elif user["company_status"] == "blocked":
            flash("A licenca da empresa esta indisponivel.", "error")
        else:
            session.clear()
            session["user_id"] = user["id"]
            session["company_id"] = user["company_id"]
            session["user_name"] = user["name"]
            session["company_name"] = user["company_name"]
            session["role"] = user["role"]
            session.permanent = bool(request.form.get("remember"))
            db = get_db()
            db.execute("UPDATE users SET last_login_at=CURRENT_TIMESTAMP WHERE id=?", (user["id"],))
            db.execute("UPDATE companies SET last_access_at=CURRENT_TIMESTAMP WHERE id=?", (user["company_id"],))
            db.commit()
            flash("Bem-vindo ao Apex Food.", "success")
            if user["role"] == "Administrador" and not user["onboarding_completed"]:
                return redirect(url_for("pages.onboarding"))
            return redirect(url_for(ROLE_HOME.get(user["role"], "dashboard.index")))

    return render_template("auth/login.html", email=request.form.get("email", ""))


@bp.route("/register", methods=("GET", "POST"))
def register():
    abort(404)


@bp.route("/invite/<token>", methods=("GET", "POST"))
def accept_invite(token):
    db = get_db()
    invite = db.execute(
        """
        SELECT client_invites.*, users.name, users.email, companies.trade_name
        FROM client_invites
        JOIN users ON users.id=client_invites.user_id
        JOIN companies ON companies.id=client_invites.company_id
        WHERE token_hash=? AND used_at IS NULL AND revoked_at IS NULL
        """,
        (token_hash(token),),
    ).fetchone()
    valid = invite and datetime.fromisoformat(invite["expires_at"]) >= datetime.utcnow()
    if not valid:
        flash("Convite expirado ou invalido. Solicite um novo acesso.", "error")
        return redirect(url_for("auth.login"))
    if request.method == "POST":
        password = request.form.get("password", "")
        confirm = request.form.get("password_confirm", "")
        if len(password) < 6 or password != confirm:
            flash("Informe uma senha valida e confirme corretamente.", "error")
            return render_template("auth/invite.html", invite=invite)
        db.execute("UPDATE users SET password_hash=?, active=1 WHERE id=?", (generate_password_hash(password), invite["user_id"]))
        db.execute("UPDATE client_invites SET used_at=CURRENT_TIMESTAMP WHERE id=?", (invite["id"],))
        db.commit()
        flash("Senha definida. Acesse o Apex Food.", "success")
        return redirect(url_for("auth.login"))
    return render_template("auth/invite.html", invite=invite)


@bp.route("/forgot-password", methods=("GET", "POST"))
def forgot_password():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        db = get_db()
        user = db.execute("SELECT id FROM users WHERE lower(email)=? AND active=1", (email,)).fetchone()
        user_type = "company"
        if not user:
            user = db.execute("SELECT id FROM platform_admins WHERE lower(email)=? AND active=1", (email,)).fetchone()
            user_type = "platform"
        if user:
            token = secrets.token_urlsafe(32)
            expires = (datetime.utcnow() + timedelta(hours=1)).isoformat(timespec="seconds")
            db.execute(
                "INSERT INTO password_reset_tokens (user_type, user_id, token_hash, expires_at) VALUES (?, ?, ?, ?)",
                (user_type, user["id"], token_hash(token), expires),
            )
            db.commit()
            if current_app.debug:
                current_app.logger.warning("Link de recuperacao Apex Food: %s", url_for("auth.reset_password", token=token, _external=True))
        flash("Se encontrarmos uma conta com este e-mail, enviaremos as instrucoes.", "success")
        return redirect(url_for("auth.login"))
    return render_template("auth/forgot_password.html")


@bp.route("/reset-password/<token>", methods=("GET", "POST"))
def reset_password(token):
    db = get_db()
    reset = db.execute(
        "SELECT * FROM password_reset_tokens WHERE token_hash=? AND used_at IS NULL",
        (token_hash(token),),
    ).fetchone()
    valid = reset and datetime.fromisoformat(reset["expires_at"]) >= datetime.utcnow()
    if not valid:
        flash("Link expirado ou invalido.", "error")
        return redirect(url_for("auth.forgot_password"))
    if request.method == "POST":
        password = request.form.get("password", "")
        confirm = request.form.get("password_confirm", "")
        if len(password) < 6 or password != confirm:
            flash("Informe uma senha valida e confirme corretamente.", "error")
            return render_template("auth/reset_password.html")
        table = "platform_admins" if reset["user_type"] == "platform" else "users"
        db.execute(f"UPDATE {table} SET password_hash=? WHERE id=?", (generate_password_hash(password), reset["user_id"]))
        db.execute("UPDATE password_reset_tokens SET used_at=CURRENT_TIMESTAMP WHERE id=?", (reset["id"],))
        db.commit()
        session.clear()
        flash("Senha atualizada. Entre novamente.", "success")
        return redirect(url_for("auth.login"))
    return render_template("auth/reset_password.html")


@bp.get("/logout")
def logout():
    session.clear()
    flash("Sessao encerrada.", "success")
    return redirect(url_for("auth.login"))
