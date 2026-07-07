from flask import Blueprint, flash, redirect, render_template, url_for

from ..database import execute, query_all
from .auth import company_id, login_required

bp = Blueprint("kitchen", __name__, url_prefix="/kitchen")


@bp.get("/")
@login_required
def index():
    cid = company_id()
    orders = query_all(
        """
        SELECT
            orders.*,
            tables.name AS table_name,
            strftime('%H:%M', orders.created_at) AS order_time,
            GROUP_CONCAT(order_items.quantity || 'x ' || order_items.product_name, ', ') AS items_summary,
            GROUP_CONCAT(NULLIF(order_items.notes, ''), ' | ') AS notes_summary
        FROM orders
        LEFT JOIN tables ON tables.id = orders.table_id
        LEFT JOIN order_items ON order_items.order_id = orders.id
        WHERE orders.company_id = ? AND orders.status IN ('Recebido', 'Preparando')
        GROUP BY orders.id
        ORDER BY orders.created_at ASC
        """,
        (cid,),
    )
    return render_template("kitchen.html", orders=orders)


@bp.post("/orders/<int:order_id>/start")
@login_required
def start_prepare(order_id):
    execute("UPDATE orders SET status = 'Preparando' WHERE id = ? AND company_id = ?", (order_id, company_id()))
    flash("Preparo iniciado.", "success")
    return redirect(url_for("kitchen.index"))


@bp.post("/orders/<int:order_id>/ready")
@login_required
def mark_ready(order_id):
    execute("UPDATE orders SET status = 'Pronto' WHERE id = ? AND company_id = ?", (order_id, company_id()))
    flash("Pedido marcado como pronto.", "success")
    return redirect(url_for("kitchen.index"))
