import json

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
        """
        SELECT id, name, category, description, price, available, image_url, prep_time
        FROM products
        WHERE company_id = ?
        ORDER BY available DESC, category, name
        """,
        (cid,),
    )
    categories = ["Todos"]
    for product in products:
        if product["category"] not in categories:
            categories.append(product["category"])
    for extra in ["Massas", "Bebidas alcoolicas"]:
        if extra not in categories:
            categories.append(extra)

    best_sellers = query_all(
        """
        SELECT products.id, COALESCE(SUM(order_items.quantity), 0) AS sold
        FROM products
        LEFT JOIN order_items ON order_items.product_id = products.id
        WHERE products.company_id = ?
        GROUP BY products.id
        ORDER BY sold DESC, products.name ASC
        LIMIT 4
        """,
        (cid,),
    )
    best_seller_ids = {row["id"] for row in best_sellers if row["sold"] > 0}
    favorite_ids = {product["id"] for product in products[:4]}

    tables = query_all(
        """
        SELECT id, name, seats, status
        FROM tables
        WHERE company_id = ?
        ORDER BY name
        """,
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
    stats = {
        "open_orders": query_one(
            "SELECT COUNT(*) AS value FROM orders WHERE company_id = ? AND status NOT IN ('Entregue', 'Cancelado')",
            (cid,),
        )["value"],
        "occupied_tables": query_one(
            "SELECT COUNT(*) AS value FROM tables WHERE company_id = ? AND status IN ('Ocupada', 'Pedido em preparo', 'Conta solicitada')",
            (cid,),
        )["value"],
        "kitchen_orders": query_one(
            "SELECT COUNT(*) AS value FROM orders WHERE company_id = ? AND status IN ('Novo', 'Em preparo')",
            (cid,),
        )["value"],
    }
    return render_template(
        "pos.html",
        register=register,
        orders=orders,
        products=products,
        categories=categories,
        favorite_ids=favorite_ids,
        best_seller_ids=best_seller_ids,
        tables=tables,
        sales=sales,
        payment_methods=PAYMENT_METHODS,
        stats=stats,
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
    cart_items = []
    if form.get("cart_items"):
        try:
            cart_items = json.loads(form.get("cart_items") or "[]")
        except json.JSONDecodeError:
            flash("Carrinho inválido.", "error")
            return redirect(url_for("pos.index"))

    subtotal = 0.0
    db = get_db()

    if cart_items:
        order_cursor = db.execute(
            """
            INSERT INTO orders (company_id, customer_name, fulfillment_type, table_id, status, total)
            VALUES (?, ?, ?, ?, 'Entregue', 0)
            """,
            (
                cid,
                form.get("customer_name", "").strip() or "Venda PDV",
                form.get("fulfillment_type", "Balcao"),
                form.get("table_id") or None,
            ),
        )
        order_id = order_cursor.lastrowid

        for item in cart_items:
            product = db.execute(
                "SELECT id, name, price FROM products WHERE id = ? AND company_id = ?",
                (item.get("id"), cid),
            ).fetchone()
            if not product:
                continue
            quantity = max(int(item.get("quantity") or 1), 1)
            line_total = round(float(product["price"]) * quantity, 2)
            subtotal += line_total
            db.execute(
                """
                INSERT INTO order_items (order_id, product_id, product_name, quantity, unit_price, notes)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    order_id,
                    product["id"],
                    product["name"],
                    quantity,
                    product["price"],
                    item.get("note", ""),
                ),
            )

        if subtotal <= 0:
            db.rollback()
            flash("Adicione produtos ao carrinho antes de finalizar.", "error")
            return redirect(url_for("pos.index"))

    elif order_id:
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
    delivery_fee = float(form.get("delivery_fee") or 0)
    total = max(round(subtotal - discount + service_fee + delivery_fee, 2), 0)
    db.execute(
        """
        INSERT INTO sales (company_id, order_id, subtotal, discount, service_fee, total, payment_method, status)
        VALUES (?, ?, ?, ?, ?, ?, ?, 'Finalizada')
        """,
        (cid, order_id, subtotal, discount, service_fee, total, form.get("payment_method", "Pix")),
    )
    db.execute("UPDATE orders SET status = 'Entregue', total = ? WHERE id = ? AND company_id = ?", (total, order_id, cid))
    if form.get("table_id"):
        db.execute(
            "UPDATE tables SET status = 'Livre', customer_name = '', total = 0 WHERE id = ? AND company_id = ?",
            (form.get("table_id"), cid),
        )
    db.commit()
    flash("Venda finalizada.", "success")
    return redirect(url_for("pos.index"))
