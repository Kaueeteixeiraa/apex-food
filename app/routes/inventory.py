from flask import Blueprint, flash, redirect, render_template, request, url_for

from ..database import execute, query_all, query_one
from .auth import company_id, login_required

bp = Blueprint("inventory", __name__, url_prefix="/inventory")


def _payload(form):
    return (
        form.get("name", "").strip(),
        float(form.get("quantity") or 0),
        form.get("unit", "un").strip() or "un",
        float(form.get("min_stock") or 0),
    )


def _insert(cid, form):
    execute(
        """
        INSERT INTO inventory_items (company_id, name, quantity, unit, min_stock)
        VALUES (?, ?, ?, ?, ?)
        """,
        (cid, *_payload(form)),
    )


def _update(item_id, cid, form):
    execute(
        """
        UPDATE inventory_items
        SET name=?, quantity=?, unit=?, min_stock=?
        WHERE id=? AND company_id=?
        """,
        (*_payload(form), item_id, cid),
    )


@bp.route("/", methods=("GET", "POST"))
@login_required
def index():
    cid = company_id()
    if request.method == "POST":
        _insert(cid, request.form)
        flash("Item de estoque cadastrado.", "success")
        return redirect(url_for("inventory.index"))

    search = request.args.get("q", "").strip()
    params = [cid]
    where = "company_id = ?"
    if search:
        where += " AND (name LIKE ? OR unit LIKE ?)"
        params.extend([f"%{search}%"] * 2)

    items = query_all(
        f"SELECT * FROM inventory_items WHERE {where} ORDER BY name",
        tuple(params),
    )
    return render_template("inventory.html", mode="list", items=items, search=search)


@bp.route("/new", methods=("GET", "POST"))
@login_required
def new():
    if request.method == "POST":
        _insert(company_id(), request.form)
        flash("Item de estoque cadastrado.", "success")
        return redirect(url_for("inventory.index"))
    return render_template("inventory.html", mode="form", item=None, form_action=url_for("inventory.new"))


@bp.route("/<int:item_id>/edit", methods=("GET", "POST"))
@login_required
def edit(item_id):
    cid = company_id()
    item = query_one("SELECT * FROM inventory_items WHERE id=? AND company_id=?", (item_id, cid))
    if not item:
        flash("Item nao encontrado.", "error")
        return redirect(url_for("inventory.index"))
    if request.method == "POST":
        _update(item_id, cid, request.form)
        flash("Item atualizado.", "success")
        return redirect(url_for("inventory.index"))
    return render_template("inventory.html", mode="form", item=item, form_action=url_for("inventory.edit", item_id=item_id))


@bp.post("/<int:item_id>/update")
@login_required
def update(item_id):
    _update(item_id, company_id(), request.form)
    flash("Item atualizado.", "success")
    return redirect(url_for("inventory.index"))


@bp.post("/<int:item_id>/delete")
@login_required
def delete(item_id):
    execute("DELETE FROM inventory_items WHERE id=? AND company_id=?", (item_id, company_id()))
    flash("Item excluido.", "success")
    return redirect(url_for("inventory.index"))
