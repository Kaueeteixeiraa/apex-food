from flask import Blueprint, flash, redirect, render_template, request, url_for

from ..database import get_db, query_all, query_one
from ..models import PAYMENT_METHODS
from .auth import company_id, login_required

bp = Blueprint("pos", __name__, url_prefix="/pos")


@bp.get("/")
@login_required
def index():
    cid = company_id()
    register = query_one(
        "SELECT * FROM cash_registers WHERE company_id = ? ORDER BY id DESC LIMIT 1",
        (cid,),
    )
    orders = query_all(
        """
        SELECT id, customer_name, fulfillment_type, status, total
        FROM orders
        WHERE company_id = ? AND status NOT IN ('Entregue', 'Cancelado')
        ORDER BY created_at DESC
        """,
        (cid,),
    )
    products = query_all(
        "SELECT id, name, price FROM products WHERE company_id = ? AND available = 1 ORDER BY name",
        (cid,),
    )
    sales = query_all(
        """
        SELECT sales.*, orders.customer_name
        FROM sales
        LEFT JOIN orders ON orders.id = sales.order_id
        WHERE sales.company_id = ?
        ORDER BY sales.created_at DESC
        LIMIT 8
        """,
        (cid,),
    )
    return render_template(
        "pos.html",
        register=register,
        orders=orders,
        products=products,
        sales=sales,
        payment_methods=PAYMENT_METHODS,
    )


@bp.post("/open")
@login_required
def open_register():
    cid = company_id()
    db = get_db()
    db.execute(
        """
        INSERT INTO cash_registers (company_id, status, opening_amount, opened_at)
        VALUES (?, 'Aberto', ?, datetime('now'))
        """,
        (cid, float(request.form.get("opening_amount") or 0)),
    )
    db.commit()
    flash("Caixa aberto.", "success")
    return redirect(url_for("pos.index"))


@bp.post("/close")
@login_required
def close_register():
    cid = company_id()
    db = get_db()
    db.execute(
        """
        UPDATE cash_registers
        SET status = 'Fechado', closed_at = datetime('now')
        WHERE id = (
            SELECT id FROM cash_registers WHERE company_id = ? ORDER BY id DESC LIMIT 1
        )
        """,
        (cid,),
    )
    db.commit()
    flash("Caixa fechado.", "success")
    return redirect(url_for("pos.index"))


@bp.post("/sale")
@login_required
def finish_sale():
    cid = company_id()
    register = query_one(
        "SELECT * FROM cash_registers WHERE company_id = ? ORDER BY id DESC LIMIT 1",
        (cid,),
    )
    if not register or register["status"] != "Aberto":
        flash("Abra o caixa antes de finalizar vendas.", "error")
        return redirect(url_for("pos.index"))

    form = request.form
    order_id = form.get("order_id") or None
    subtotal = 0.0
    db = get_db()

    if order_id:
        order = db.execute("SELECT total FROM orders WHERE id = ? AND company_id = ?", (order_id, cid)).fetchone()
        if not order:
            flash("Pedido não encontrado.", "error")
            return redirect(url_for("pos.index"))
        subtotal = float(order["total"])
    else:
        product = db.execute(
            "SELECT id, name, price FROM products WHERE id = ? AND company_id = ?",
            (form.get("product_id"), cid),
        ).fetchone()
        if not product:
            flash("Escolha um pedido ou produto.", "error")
            return redirect(url_for("pos.index"))
        quantity = max(int(form.get("quantity") or 1), 1)
        subtotal = round(float(product["price"]) * quantity, 2)
        order_cursor = db.execute(
            """
            INSERT INTO orders (company_id, customer_name, fulfillment_type, status, total)
            VALUES (?, ?, 'Balcao', 'Entregue', ?)
            """,
            (cid, "Venda rápida", subtotal),
        )
        order_id = order_cursor.lastrowid
        db.execute(
            """
            INSERT INTO order_items (order_id, product_id, product_name, quantity, unit_price)
            VALUES (?, ?, ?, ?, ?)
            """,
            (order_id, product["id"], product["name"], quantity, product["price"]),
        )

    discount = float(form.get("discount") or 0)
    service_fee = float(form.get("service_fee") or 0)
    total = max(round(subtotal - discount + service_fee, 2), 0)
    db.execute(
        """
        INSERT INTO sales (company_id, order_id, subtotal, discount, service_fee, total, payment_method, status)
        VALUES (?, ?, ?, ?, ?, ?, ?, 'Finalizada')
        """,
        (cid, order_id, subtotal, discount, service_fee, total, form.get("payment_method", "Pix")),
    )
    db.execute("UPDATE orders SET status = 'Entregue', total = ? WHERE id = ? AND company_id = ?", (total, order_id, cid))
    db.commit()
    flash("Venda finalizada.", "success")
    return redirect(url_for("pos.index"))
