from ..database import get_db, query_one
from .audit import log_audit


def create_order(company_id, form):
    product = query_one(
        "SELECT id, name, price FROM products WHERE id = ? AND company_id = ?",
        (form.get("product_id"), company_id),
    )
    if not product:
        return None

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
            company_id,
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
            (form.get("customer_name", "").strip(), total, table_id, company_id),
        )
    log_audit(company_id, "order.create", "orders", order_id, {"total": total})
    db.commit()
    return order_id
