import sqlite3
from functools import wraps

from flask import Blueprint, flash, g, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash

from ..database import get_db, query_one
from ..models import SEGMENTS

bp = Blueprint("auth", __name__, url_prefix="/auth")


@bp.before_app_request
def load_logged_in_user():
    user_id = session.get("user_id")
    if user_id is None:
        g.user = None
        return

    g.user = query_one(
        """
        SELECT users.*, companies.trade_name AS company_name
        FROM users
        JOIN companies ON companies.id = users.company_id
        WHERE users.id = ?
        """,
        (user_id,),
    )


def login_required(view):
    @wraps(view)
    def wrapped_view(**kwargs):
        if g.user is None:
            return redirect(url_for("auth.login"))
        return view(**kwargs)

    return wrapped_view


def company_id():
    return session.get("company_id")


@bp.route("/login", methods=("GET", "POST"))
def login():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        user = query_one(
            """
            SELECT users.*, companies.trade_name AS company_name
            FROM users
            JOIN companies ON companies.id = users.company_id
            WHERE lower(users.email) = ?
            """,
            (email,),
        )

        if user is None or not check_password_hash(user["password_hash"], password):
            flash("E-mail ou senha invalidos.", "error")
        else:
            session.clear()
            session["user_id"] = user["id"]
            session["company_id"] = user["company_id"]
            session["user_name"] = user["name"]
            session["company_name"] = user["company_name"]
            flash("Bem-vindo ao Apex Food.", "success")
            return redirect(url_for("dashboard.index"))

    return render_template("auth/login.html")


@bp.route("/register", methods=("GET", "POST"))
def register():
    if request.method == "POST":
        form = request.form
        required = [
            "legal_name",
            "trade_name",
            "cnpj",
            "email",
            "phone",
            "segment",
            "address",
            "city",
            "state",
            "cep",
            "admin_name",
            "admin_email",
            "password",
        ]

        missing = [field for field in required if not form.get(field, "").strip()]
        if missing:
            flash("Preencha todos os campos obrigatorios.", "error")
            return render_template("auth/register.html", segments=SEGMENTS)

        db = get_db()
        try:
            company_cursor = db.execute(
                """
                INSERT INTO companies
                (legal_name, trade_name, cnpj, email, phone, segment, address, city, state, cep)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    form["legal_name"].strip(),
                    form["trade_name"].strip(),
                    form["cnpj"].strip(),
                    form["email"].strip().lower(),
                    form["phone"].strip(),
                    form["segment"].strip(),
                    form["address"].strip(),
                    form["city"].strip(),
                    form["state"].strip().upper(),
                    form["cep"].strip(),
                ),
            )
            new_company_id = company_cursor.lastrowid
            db.execute(
                """
                INSERT INTO users (company_id, name, email, password_hash, role)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    new_company_id,
                    form["admin_name"].strip(),
                    form["admin_email"].strip().lower(),
                    generate_password_hash(form["password"]),
                    "Administrador",
                ),
            )
            db.commit()
        except sqlite3.IntegrityError:
            db.rollback()
            flash("Ja existe uma empresa ou usuario com esse e-mail.", "error")
            return render_template("auth/register.html", segments=SEGMENTS)

        flash("Empresa cadastrada. Entre com o e-mail do administrador.", "success")
        return redirect(url_for("auth.login"))

    return render_template("auth/register.html", segments=SEGMENTS)


@bp.get("/logout")
def logout():
    session.clear()
    flash("Sessao encerrada.", "success")
    return redirect(url_for("auth.login"))
