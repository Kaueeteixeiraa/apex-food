from datetime import datetime, timedelta

from flask import Blueprint, render_template

from ..database import query_all, query_one
from ..models import PRODUCT_CATEGORIES, products_with_demo_images
from .auth import company_id, login_required

bp = Blueprint("pages", __name__)


def _value(sql, params):
    row = query_one(sql, params)
    return row["value"] if row else 0


def _summary(cid):
    return {
        "today": _value("SELECT COALESCE(SUM(total),0) value FROM sales WHERE company_id=? AND date(created_at)=date('now')", (cid,)),
        "month": _value("SELECT COALESCE(SUM(total),0) value FROM sales WHERE company_id=? AND date(created_at)>=date('now','start of month')", (cid,)),
        "orders": _value("SELECT COUNT(*) value FROM orders WHERE company_id=? AND status NOT IN ('Entregue','Cancelado')", (cid,)),
        "ticket": _value("SELECT COALESCE(AVG(total),0) value FROM sales WHERE company_id=?", (cid,)),
    }


def _sales_chart(cid):
    rows = query_all(
        """
        SELECT date(created_at) day, COALESCE(SUM(total),0) total
        FROM sales
        WHERE company_id=? AND date(created_at)>=date('now','-6 day')
        GROUP BY date(created_at)
        """,
        (cid,),
    )
    by_day = {row["day"]: float(row["total"]) for row in rows}
    today = datetime.now().date()
    data = []
    max_total = max(by_day.values(), default=1)
    for offset in range(6, -1, -1):
        day = today - timedelta(days=offset)
        total = by_day.get(day.isoformat(), 0)
        data.append({"label": day.strftime("%d/%m"), "total": total, "height": max(8, int(total / max_total * 100)) if max_total else 8})
    return data


def _top_products(cid, limit=6):
    return query_all(
        """
        SELECT p.name, p.category, p.price, COALESCE(SUM(oi.quantity),0) sold,
               COALESCE(SUM(oi.quantity * oi.unit_price),0) total
        FROM products p
        LEFT JOIN order_items oi ON oi.product_id = p.id
        WHERE p.company_id=?
        GROUP BY p.id
        ORDER BY sold DESC, p.name
        LIMIT ?
        """,
        (cid, limit),
    )


@bp.get("/menu")
@login_required
def menu():
    cid = company_id()
    products = products_with_demo_images(query_all("SELECT * FROM products WHERE company_id=? ORDER BY category,name", (cid,)))
    return render_template("workspace.html", screen="menu", title="Cardapio", products=products)


@bp.get("/categories")
@login_required
def categories():
    cid = company_id()
    rows = query_all(
        "SELECT category, COUNT(*) products, SUM(available) available, COALESCE(AVG(price),0) avg_price FROM products WHERE company_id=? GROUP BY category",
        (cid,),
    )
    indexed = {row["category"]: row for row in rows}
    categories = []
    for name in PRODUCT_CATEGORIES:
        row = indexed.get(name)
        categories.append({
            "name": name,
            "products": row["products"] if row else 0,
            "available": row["available"] if row else 0,
            "avg_price": row["avg_price"] if row else 0,
        })
    return render_template("workspace.html", screen="categories", title="Categorias", categories=categories)


@bp.get("/delivery")
@login_required
def delivery():
    cid = company_id()
    orders = query_all(
        """
        SELECT id, customer_name, status, total, created_at
        FROM orders
        WHERE company_id=? AND fulfillment_type='Entrega'
        ORDER BY created_at DESC
        LIMIT 8
        """,
        (cid,),
    )
    metrics = {
        "active": _value("SELECT COUNT(*) value FROM orders WHERE company_id=? AND fulfillment_type='Entrega' AND status NOT IN ('Entregue','Cancelado')", (cid,)),
        "done": _value("SELECT COUNT(*) value FROM orders WHERE company_id=? AND fulfillment_type='Entrega' AND status='Entregue'", (cid,)),
        "revenue": _value("SELECT COALESCE(SUM(total),0) value FROM orders WHERE company_id=? AND fulfillment_type='Entrega'", (cid,)),
        "time": 32,
    }
    return render_template("workspace.html", screen="delivery", title="Delivery", orders=orders, metrics=metrics)


@bp.get("/finance")
@login_required
def finance():
    cid = company_id()
    payments = query_all(
        "SELECT payment_method, COALESCE(SUM(total),0) total, COUNT(*) count FROM sales WHERE company_id=? GROUP BY payment_method ORDER BY total DESC",
        (cid,),
    )
    sales = query_all("SELECT id, total, payment_method, status, created_at FROM sales WHERE company_id=? ORDER BY created_at DESC LIMIT 8", (cid,))
    return render_template(
        "workspace.html",
        screen="finance",
        title="Financeiro",
        summary=_summary(cid),
        payments=payments,
        sales=sales,
        chart=_sales_chart(cid),
    )


@bp.get("/reports")
@login_required
def reports():
    cid = company_id()
    low_stock = query_all("SELECT name, quantity, unit, min_stock FROM inventory_items WHERE company_id=? AND quantity<=min_stock ORDER BY quantity LIMIT 5", (cid,))
    clients = query_all(
        """
        SELECT c.name, COUNT(o.id) orders, COALESCE(SUM(o.total),0) total
        FROM customers c
        LEFT JOIN orders o ON o.customer_id=c.id
        WHERE c.company_id=?
        GROUP BY c.id
        ORDER BY total DESC
        LIMIT 5
        """,
        (cid,),
    )
    return render_template(
        "workspace.html",
        screen="reports",
        title="Relatorios",
        summary=_summary(cid),
        chart=_sales_chart(cid),
        top_products=_top_products(cid),
        low_stock=low_stock,
        clients=clients,
    )


@bp.get("/settings")
@login_required
def settings():
    cid = company_id()
    company = query_one("SELECT * FROM companies WHERE id=?", (cid,))
    groups = [
        ("Empresa", "Dados fiscais, marca e unidades."),
        ("Pagamentos", "Pix, cartoes, taxas e recebiveis."),
        ("Usuarios", "Permissoes e perfis de acesso."),
        ("Integracoes", "Delivery, fiscal, impressoras e webhooks."),
        ("Backup", "Rotina de seguranca e exportacoes."),
        ("Operacao", "Mesas, cozinha, estoque e PDV."),
    ]
    return render_template("workspace.html", screen="settings", title="Configuracoes", company=company, groups=groups)
