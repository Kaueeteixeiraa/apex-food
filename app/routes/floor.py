from flask import Blueprint, flash, jsonify, redirect, render_template, request, url_for

from ..database import execute, get_db, query_all, query_one
from ..models import TABLE_STATUSES
from .auth import company_id, login_required

bp = Blueprint("floor", __name__, url_prefix="/floor")


@bp.get("/")
@login_required
def index():
    cid = company_id()
    areas = query_all("SELECT * FROM areas WHERE company_id = ? ORDER BY id", (cid,))
    tables = query_all("SELECT * FROM tables WHERE company_id = ? ORDER BY id", (cid,))
    open_orders = query_all(
        """
        SELECT orders.id, orders.customer_name, orders.total, orders.table_id,
               GROUP_CONCAT(order_items.quantity || 'x ' || order_items.product_name, ', ') AS items_summary
        FROM orders
        LEFT JOIN order_items ON order_items.order_id = orders.id
        WHERE orders.company_id = ? AND orders.status NOT IN ('Entregue', 'Cancelado')
        GROUP BY orders.id
        """,
        (cid,),
    )
    return render_template(
        "floor.html",
        areas=[dict(row) for row in areas],
        tables=[dict(row) for row in tables],
        open_orders=[dict(row) for row in open_orders],
        statuses=TABLE_STATUSES,
    )


@bp.post("/areas")
@login_required
def create_area():
    name = request.form.get("name", "").strip()
    if not name:
        flash("Informe o nome da área.", "error")
        return redirect(url_for("floor.index"))
    execute("INSERT INTO areas (company_id, name) VALUES (?, ?)", (company_id(), name))
    flash("Área criada.", "success")
    return redirect(url_for("floor.index"))


@bp.post("/tables")
@login_required
def create_table():
    cid = company_id()
    form = request.form
    area = query_one("SELECT id FROM areas WHERE id = ? AND company_id = ?", (form.get("area_id"), cid))
    if not area:
        flash("Área inválida.", "error")
        return redirect(url_for("floor.index"))

    execute(
        """
        INSERT INTO tables
        (company_id, area_id, name, shape, seats, status, x, y, width, height)
        VALUES (?, ?, ?, ?, ?, 'Livre', ?, ?, ?, ?)
        """,
        (
            cid,
            area["id"],
            form.get("name", "Nova mesa").strip() or "Nova mesa",
            form.get("shape", "round"),
            int(form.get("seats") or 4),
            float(form.get("x") or 80),
            float(form.get("y") or 80),
            float(form.get("width") or 110),
            float(form.get("height") or 110),
        ),
    )
    flash("Mesa criada.", "success")
    return redirect(url_for("floor.index"))


@bp.patch("/tables/<int:table_id>")
@login_required
def update_table(table_id):
    cid = company_id()
    payload = request.get_json(silent=True) or {}
    allowed = {
        "area_id",
        "name",
        "shape",
        "seats",
        "status",
        "x",
        "y",
        "width",
        "height",
        "customer_name",
        "total",
    }
    fields = {key: payload[key] for key in allowed if key in payload}

    if "status" in fields and fields["status"] not in TABLE_STATUSES:
        return jsonify({"ok": False, "error": "Status inválido"}), 400

    if "area_id" in fields:
        area = query_one("SELECT id FROM areas WHERE id = ? AND company_id = ?", (fields["area_id"], cid))
        if not area:
            return jsonify({"ok": False, "error": "Área inválida"}), 400

    numeric_fields = {"x", "y", "width", "height", "total"}
    integer_fields = {"area_id", "seats"}
    for key in list(fields):
        if key in numeric_fields:
            fields[key] = float(fields[key] or 0)
        if key in integer_fields:
            fields[key] = int(fields[key] or 0)

    if not fields:
        return jsonify({"ok": True})

    set_clause = ", ".join([f"{field} = ?" for field in fields])
    values = list(fields.values()) + [table_id, cid]
    db = get_db()
    db.execute(f"UPDATE tables SET {set_clause} WHERE id = ? AND company_id = ?", values)
    db.commit()
    table = query_one("SELECT * FROM tables WHERE id = ? AND company_id = ?", (table_id, cid))
    return jsonify({"ok": True, "table": dict(table)})
