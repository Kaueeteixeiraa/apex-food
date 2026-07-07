from flask import Blueprint, flash, redirect, render_template, request, url_for

from ..database import execute, query_all, query_one
from .auth import company_id, login_required

bp = Blueprint("clients", __name__, url_prefix="/clients")


def _payload(form):
    return (
        form.get("name", "").strip(),
        form.get("phone", "").strip(),
        form.get("email", "").strip(),
        form.get("address", "").strip(),
    )


def _insert(cid, form):
    execute(
        """
        INSERT INTO customers (company_id, name, phone, email, address)
        VALUES (?, ?, ?, ?, ?)
        """,
        (cid, *_payload(form)),
    )


def _update(client_id, cid, form):
    execute(
        """
        UPDATE customers
        SET name=?, phone=?, email=?, address=?
        WHERE id=? AND company_id=?
        """,
        (*_payload(form), client_id, cid),
    )


@bp.route("/", methods=("GET", "POST"))
@login_required
def index():
    cid = company_id()
    if request.method == "POST":
        _insert(cid, request.form)
        flash("Cliente cadastrado.", "success")
        return redirect(url_for("clients.index"))

    search = request.args.get("q", "").strip()
    params = [cid]
    where = "customers.company_id = ?"
    if search:
        where += " AND (customers.name LIKE ? OR customers.phone LIKE ? OR customers.email LIKE ? OR customers.address LIKE ?)"
        params.extend([f"%{search}%"] * 4)

    clients = query_all(
        f"""
        SELECT
            customers.*,
            COUNT(orders.id) AS order_count,
            COALESCE(SUM(orders.total), 0) AS total_spent
        FROM customers
        LEFT JOIN orders ON orders.customer_id = customers.id
        WHERE {where}
        GROUP BY customers.id
        ORDER BY customers.name
        """,
        tuple(params),
    )
    return render_template("clients.html", mode="list", clients=clients, search=search)


@bp.route("/new", methods=("GET", "POST"))
@login_required
def new():
    if request.method == "POST":
        _insert(company_id(), request.form)
        flash("Cliente cadastrado.", "success")
        return redirect(url_for("clients.index"))
    return render_template("clients.html", mode="form", client=None, form_action=url_for("clients.new"))


@bp.route("/<int:client_id>/edit", methods=("GET", "POST"))
@login_required
def edit(client_id):
    cid = company_id()
    client = query_one("SELECT * FROM customers WHERE id=? AND company_id=?", (client_id, cid))
    if not client:
        flash("Cliente nao encontrado.", "error")
        return redirect(url_for("clients.index"))
    if request.method == "POST":
        _update(client_id, cid, request.form)
        flash("Cliente atualizado.", "success")
        return redirect(url_for("clients.index"))
    return render_template("clients.html", mode="form", client=client, form_action=url_for("clients.edit", client_id=client_id))


@bp.post("/<int:client_id>/update")
@login_required
def update(client_id):
    _update(client_id, company_id(), request.form)
    flash("Cliente atualizado.", "success")
    return redirect(url_for("clients.index"))


@bp.post("/<int:client_id>/delete")
@login_required
def delete(client_id):
    execute("DELETE FROM customers WHERE id=? AND company_id=?", (client_id, company_id()))
    flash("Cliente excluido.", "success")
    return redirect(url_for("clients.index"))
