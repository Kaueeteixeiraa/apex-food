from flask import Blueprint, flash, redirect, render_template, request, url_for

from ..database import execute, query_all
from ..models import PERMISSIONS
from .auth import company_id, login_required

bp = Blueprint("employees", __name__, url_prefix="/employees")


@bp.route("/", methods=("GET", "POST"))
@login_required
def index():
    cid = company_id()
    if request.method == "POST":
        execute(
            """
            INSERT INTO employees (company_id, name, role, email, phone, permission)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                cid,
                request.form.get("name", "").strip(),
                request.form.get("role", "").strip(),
                request.form.get("email", "").strip(),
                request.form.get("phone", "").strip(),
                request.form.get("permission", "Garcom"),
            ),
        )
        flash("Funcionário cadastrado.", "success")
        return redirect(url_for("employees.index"))

    employees = query_all(
        "SELECT * FROM employees WHERE company_id = ? ORDER BY name",
        (cid,),
    )
    return render_template("employees.html", employees=employees, permissions=PERMISSIONS)
