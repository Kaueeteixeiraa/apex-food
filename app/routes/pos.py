import json

from flask import Blueprint, flash, g, redirect, render_template, request, url_for

from ..database import get_db, query_all, query_one
from ..models import PAYMENT_METHODS, products_with_demo_images
from .auth import company_id, login_required

bp = Blueprint("pos", __name__, url_prefix="/pos")


def _money(value):
    try:
        return max(float(value or 0), 0)
    except (TypeError, ValueError):
        return 0


def _quantity(value):
    try:
        return max(int(value or 1), 1)
    except (TypeError, ValueError):
        return 1


def _decrement_stock(db, cid, product_id, quantity):
    db.execute(
        """
        UPDATE products
        SET stock_quantity = CASE WHEN stock_quantity >= ? THEN stock_quantity - ? ELSE 0 END
        WHERE id = ? AND company_id = ?
        """,
        (quantity, quantity, product_id, cid),
    )


def _cash_context(cid, register):
    if not register:
        return {"sales": 0, "supply": 0, "withdraw": 0, "expected": 0}, []

    opened_at = register["opened_at"] or register["created_at"]
    closed_at = register["closed_at"]
    close_clause = "AND datetime(created_at) <= datetime(?)" if closed_at else ""
    params = (cid, opened_at, closed_at) if closed_at else (cid, opened_at)
    sales_total = query_one(
        f"""
        SELECT COALESCE(SUM(total),0) value
        FROM sales
        WHERE company_id=? AND datetime(created_at) >= datetime(?) {close_clause}
        """,
        params,
    )["value"]
    movements = query_all(
        """
        SELECT * FROM cash_movements
        WHERE company_id=? AND register_id=?
        ORDER BY created_at DESC
        LIMIT 6
        """,
        (cid, register["id"]),
    )
    movement_totals = query_all(
        """
        SELECT type, COALESCE(SUM(amount),0) total
        FROM cash_movements
        WHERE company_id=? AND register_id=?
        GROUP BY type
        """,
        (cid, register["id"]),
    )
    totals_by_type = {row["type"]: float(row["total"] or 0) for row in movement_totals}
    supply = totals_by_type.get("Suprimento", 0)
    withdraw = totals_by_type.get("Sangria", 0)
    expected = float(register["opening_amount"] or 0) + float(sales_total or 0) + supply - withdraw
    if register["status"] == "Fechado" and float(register["expected_amount"] or 0):
        expected = float(register["expected_amount"] or 0)
    return {"sales": sales_total, "supply": supply, "withdraw": withdraw, "expected": expected}, movements


@bp.get("/")
@login_required
def index():
    cid = company_id()
    register = query_one(
        "SELECT * FROM cash_registers WHERE company_id = ? ORDER BY id DESC LIMIT 1",
        (cid,),
    )
    cash_totals, cash_movements = _cash_context(cid, register)
    orders = query_all(
        """
        SELECT id, customer_name, fulfillment_type, status, total
        FROM orders
        WHERE company_id = ? AND status NOT IN ('Entregue', 'Cancelado')
        ORDER BY created_at DESC
        """,
        (cid,),
    )
    products = products_with_demo_images(
        query_all(
            """
            SELECT id, name, category, description, price, available, image_url, prep_time
            FROM products
            WHERE company_id = ?
            ORDER BY available DESC, category, name
            """,
            (cid,),
        )
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
            "SELECT COUNT(*) AS value FROM orders WHERE company_id = ? AND status IN ('Recebido', 'Preparando')",
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
        cash_totals=cash_totals,
        cash_movements=cash_movements,
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
        (cid, _money(request.form.get("opening_amount"))),
    )
    db.commit()
    flash("Caixa aberto.", "success")
    return redirect(url_for("pos.index"))


@bp.post("/movement")
@login_required
def movement():
    cid = company_id()
    db = get_db()
    register = db.execute(
        "SELECT * FROM cash_registers WHERE company_id=? AND status='Aberto' ORDER BY id DESC LIMIT 1",
        (cid,),
    ).fetchone()
    if not register:
        flash("Abra o caixa antes de lançar movimentações.", "error")
        return redirect(url_for("pos.index"))

    movement_type = request.form.get("type", "Suprimento")
    if movement_type not in ("Suprimento", "Sangria"):
        movement_type = "Suprimento"
    amount = _money(request.form.get("amount"))
    if amount <= 0:
        flash("Informe um valor válido.", "error")
        return redirect(url_for("pos.index"))

    db.execute(
        "INSERT INTO cash_movements (company_id, register_id, type, amount, note) VALUES (?, ?, ?, ?, ?)",
        (cid, register["id"], movement_type, amount, request.form.get("note", "").strip()),
    )
    db.commit()
    flash("Movimento de caixa registrado.", "success")
    return redirect(url_for("pos.index"))


@bp.post("/close")
@login_required
def close_register():
    cid = company_id()
    db = get_db()
    register = db.execute(
        "SELECT * FROM cash_registers WHERE company_id=? AND status='Aberto' ORDER BY id DESC LIMIT 1",
        (cid,),
    ).fetchone()
    if not register:
        flash("Nenhum caixa aberto para fechar.", "error")
        return redirect(url_for("pos.index"))

    cash_totals, _ = _cash_context(cid, register)
    closing_amount = _money(request.form.get("closing_amount"))
    expected_amount = round(float(cash_totals["expected"] or 0), 2)
    difference_amount = round(closing_amount - expected_amount, 2)
    db.execute(
        """
        UPDATE cash_registers
        SET status = 'Fechado',
            closing_amount = ?,
            expected_amount = ?,
            difference_amount = ?,
            closed_by = ?,
            closed_at = datetime('now')
        WHERE id = ? AND company_id = ?
        """,
        (closing_amount, expected_amount, difference_amount, g.user["name"], register["id"], cid),
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
            quantity = _quantity(item.get("quantity"))
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
            _decrement_stock(db, cid, product["id"], quantity)

        if subtotal <= 0:
            db.rollback()
            flash("Adicione produtos ao carrinho antes de finalizar.", "error")
            return redirect(url_for("pos.index"))

    elif order_id:
        order = db.execute("SELECT total, status FROM orders WHERE id = ? AND company_id = ?", (order_id, cid)).fetchone()
        if not order:
            flash("Pedido não encontrado.", "error")
            return redirect(url_for("pos.index"))
        subtotal = float(order["total"])
        if order["status"] != "Entregue":
            items = db.execute("SELECT product_id, quantity FROM order_items WHERE order_id = ?", (order_id,)).fetchall()
            for item in items:
                if item["product_id"]:
                    _decrement_stock(db, cid, item["product_id"], _quantity(item["quantity"]))
    else:
        product = db.execute(
            "SELECT id, name, price FROM products WHERE id = ? AND company_id = ?",
            (form.get("product_id"), cid),
        ).fetchone()
        if not product:
            flash("Escolha um pedido ou produto.", "error")
            return redirect(url_for("pos.index"))
        quantity = _quantity(form.get("quantity"))
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
        _decrement_stock(db, cid, product["id"], quantity)

    discount = _money(form.get("discount"))
    service_fee = _money(form.get("service_fee"))
    delivery_fee = _money(form.get("delivery_fee"))
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
