from flask import Blueprint, flash, redirect, render_template, request, url_for

from ..database import execute, query_all, query_one
from ..models import PERMISSIONS
from .auth import company_id, login_required

bp = Blueprint("employees", __name__, url_prefix="/employees")


def _payload(form):
    return (
        form.get("name", "").strip(),
        form.get("role", "").strip(),
        form.get("email", "").strip(),
        form.get("phone", "").strip(),
        form.get("permission", "Caixa"),
    )


def _insert(cid, form):
    execute(
        """
        INSERT INTO employees (company_id, name, role, email, phone, permission)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (cid, *_payload(form)),
    )


def _update(employee_id, cid, form):
    execute(
        """
        UPDATE employees
        SET name=?, role=?, email=?, phone=?, permission=?
        WHERE id=? AND company_id=?
        """,
        (*_payload(form), employee_id, cid),
    )


@bp.route("/", methods=("GET", "POST"))
@login_required
def index():
    cid = company_id()
    if request.method == "POST":
        _insert(cid, request.form)
        flash("Funcionario cadastrado.", "success")
        return redirect(url_for("employees.index"))

    search = request.args.get("q", "").strip()
    params = [cid]
    where = "company_id = ?"
    if search:
        where += " AND (name LIKE ? OR role LIKE ? OR email LIKE ? OR phone LIKE ? OR permission LIKE ?)"
        params.extend([f"%{search}%"] * 5)

    employees = query_all(f"SELECT * FROM employees WHERE {where} ORDER BY name", tuple(params))
    return render_template("employees.html", mode="list", employees=employees, permissions=PERMISSIONS, search=search)


@bp.route("/new", methods=("GET", "POST"))
@login_required
def new():
    if request.method == "POST":
        _insert(company_id(), request.form)
        flash("Funcionario cadastrado.", "success")
        return redirect(url_for("employees.index"))
    return render_template("employees.html", mode="form", employee=None, permissions=PERMISSIONS, form_action=url_for("employees.new"))


@bp.route("/<int:employee_id>/edit", methods=("GET", "POST"))
@login_required
def edit(employee_id):
    cid = company_id()
    employee = query_one("SELECT * FROM employees WHERE id=? AND company_id=?", (employee_id, cid))
    if not employee:
        flash("Funcionario nao encontrado.", "error")
        return redirect(url_for("employees.index"))
    if request.method == "POST":
        _update(employee_id, cid, request.form)
        flash("Funcionario atualizado.", "success")
        return redirect(url_for("employees.index"))
    return render_template("employees.html", mode="form", employee=employee, permissions=PERMISSIONS, form_action=url_for("employees.edit", employee_id=employee_id))


@bp.post("/<int:employee_id>/update")
@login_required
def update(employee_id):
    _update(employee_id, company_id(), request.form)
    flash("Funcionario atualizado.", "success")
    return redirect(url_for("employees.index"))


@bp.post("/<int:employee_id>/delete")
@login_required
def delete(employee_id):
    execute("DELETE FROM employees WHERE id=? AND company_id=?", (employee_id, company_id()))
    flash("Funcionario excluido.", "success")
    return redirect(url_for("employees.index"))
