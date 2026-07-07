from flask import Blueprint, flash, g, redirect, render_template, request, url_for

from ..database import get_db, query_all, query_one
from ..models import ORDER_STATUSES
from .auth import company_id, login_required

bp = Blueprint("orders", __name__, url_prefix="/orders")


def _form_options(cid):
    return {
        "products": query_all(
            "SELECT id, name, price FROM products WHERE company_id = ? AND available = 1 ORDER BY name",
            (cid,),
        ),
        "tables": query_all("SELECT id, name, status FROM tables WHERE company_id = ? ORDER BY name", (cid,)),
    }


def _create_order(cid, form):
    product = query_one(
        "SELECT id, name, price FROM products WHERE id = ? AND company_id = ?",
        (form.get("product_id"), cid),
    )
    if not product:
        return False

    quantity = max(int(form.get("quantity") or 1), 1)
    total = round(float(product["price"]) * quantity, 2)
    table_id = form.get("table_id") or None
    db = get_db()
    order_cursor = db.execute(
        """
        INSERT INTO orders
        (company_id, customer_name, fulfillment_type, table_id, status, total)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            cid,
            form.get("customer_name", "").strip() or "Cliente balcao",
            form.get("fulfillment_type", "Mesa"),
            table_id,
            "Recebido",
            total,
        ),
    )
    order_id = order_cursor.lastrowid
    db.execute(
        """
        INSERT INTO order_items (order_id, product_id, product_name, quantity, unit_price, notes)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (order_id, product["id"], product["name"], quantity, product["price"], form.get("notes", "").strip()),
    )
    if table_id:
        db.execute(
            """
            UPDATE tables
            SET status = 'Pedido em preparo',
                customer_name = ?,
                total = COALESCE(total, 0) + ?
            WHERE id = ? AND company_id = ?
            """,
            (form.get("customer_name", "").strip(), total, table_id, cid),
        )
    db.commit()
    return True


@bp.route("/", methods=("GET", "POST"))
@login_required
def index():
    cid = company_id()

    if request.method == "POST":
        if not _create_order(cid, request.form):
            flash("Selecione um produto valido.", "error")
            return redirect(url_for("orders.index"))
        flash("Pedido criado.", "success")
        return redirect(url_for("orders.index"))

    selected_status = request.args.get("status", "")
    params = [cid]
    status_clause = ""
    if selected_status in ORDER_STATUSES:
        status_clause = "AND orders.status = ?"
        params.append(selected_status)
    if g.user["role"] == "Entregador":
        status_clause += " AND orders.fulfillment_type = 'Entrega'"

    orders = query_all(
        f"""
        SELECT
            orders.*,
            tables.name AS table_name,
            strftime('%H:%M', orders.created_at) AS order_time,
            COALESCE(MAX(sales.payment_method), 'Pendente') AS payment_method,
            GROUP_CONCAT(order_items.quantity || 'x ' || order_items.product_name, ', ') AS items_summary
        FROM orders
        LEFT JOIN tables ON tables.id = orders.table_id
        LEFT JOIN order_items ON order_items.order_id = orders.id
        LEFT JOIN sales ON sales.order_id = orders.id
        WHERE orders.company_id = ? {status_clause}
        GROUP BY orders.id
        ORDER BY orders.created_at DESC
        """,
        tuple(params),
    )
    options = _form_options(cid)
    orders_by_status = {status: [] for status in ORDER_STATUSES}
    for order in orders:
        orders_by_status.setdefault(order["status"], []).append(order)

    return render_template(
        "orders.html",
        mode="list",
        orders=orders,
        orders_by_status=orders_by_status,
        products=options["products"],
        tables=options["tables"],
        statuses=ORDER_STATUSES,
        selected_status=selected_status,
        is_delivery=g.user["role"] == "Entregador",
    )


@bp.route("/new", methods=("GET", "POST"))
@login_required
def new():
    cid = company_id()
    if request.method == "POST":
        if not _create_order(cid, request.form):
            flash("Selecione um produto valido.", "error")
            return redirect(url_for("orders.new"))
        flash("Pedido criado.", "success")
        return redirect(url_for("orders.index"))
    options = _form_options(cid)
    return render_template(
        "orders.html",
        mode="form",
        products=options["products"],
        tables=options["tables"],
        statuses=ORDER_STATUSES,
        is_delivery=g.user["role"] == "Entregador",
    )


@bp.post("/<int:order_id>/status")
@login_required
def update_status(order_id):
    cid = company_id()
    new_status = request.form.get("status")
    if new_status not in ORDER_STATUSES:
        flash("Status invalido.", "error")
        return redirect(url_for("orders.index"))

    db = get_db()
    db.execute("UPDATE orders SET status = ? WHERE id = ? AND company_id = ?", (new_status, order_id, cid))
    if new_status in ("Entregue", "Cancelado"):
        order = db.execute("SELECT table_id FROM orders WHERE id = ? AND company_id = ?", (order_id, cid)).fetchone()
        if order and order["table_id"]:
            db.execute(
                "UPDATE tables SET status = 'Livre', customer_name = '', total = 0 WHERE id = ? AND company_id = ?",
                (order["table_id"], cid),
            )
    db.commit()
    flash("Status do pedido atualizado.", "success")
    return redirect(url_for("orders.index"))
