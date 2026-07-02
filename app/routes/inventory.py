from flask import Blueprint, flash, redirect, render_template, request, url_for

from ..database import execute, query_all
from .auth import company_id, login_required

bp = Blueprint("inventory", __name__, url_prefix="/inventory")


@bp.route("/", methods=("GET", "POST"))
@login_required
def index():
    cid = company_id()
    if request.method == "POST":
        execute(
            """
            INSERT INTO inventory_items (company_id, name, quantity, unit, min_stock)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                cid,
                request.form.get("name", "").strip(),
                float(request.form.get("quantity") or 0),
                request.form.get("unit", "un").strip(),
                float(request.form.get("min_stock") or 0),
            ),
        )
        flash("Item de estoque cadastrado.", "success")
        return redirect(url_for("inventory.index"))

    items = query_all(
        "SELECT * FROM inventory_items WHERE company_id = ? ORDER BY name",
        (cid,),
    )
    return render_template("inventory.html", items=items)
