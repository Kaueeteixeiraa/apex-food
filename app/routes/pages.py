from datetime import datetime, timedelta

from flask import Blueprint, render_template, request

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


def _period_context():
    today = datetime.now().date()
    period = request.args.get("period", "7")
    start_raw = request.args.get("start") or ""
    end_raw = request.args.get("end") or ""
    labels = {"today": "Hoje", "7": "7 dias", "30": "30 dias", "90": "90 dias"}

    if period == "custom" and start_raw and end_raw:
        try:
            start = datetime.strptime(start_raw, "%Y-%m-%d").date()
            end = datetime.strptime(end_raw, "%Y-%m-%d").date()
            if start > end:
                start, end = end, start
            return {"key": period, "label": "Personalizado", "start": start.isoformat(), "end": end.isoformat()}
        except ValueError:
            period = "7"

    days = {"today": 1, "7": 7, "30": 30, "90": 90}.get(period, 7)
    start = today - timedelta(days=days - 1)
    return {"key": period, "label": labels.get(period, "7 dias"), "start": start.isoformat(), "end": today.isoformat()}


def _period_where(column, period):
    return f"date({column}) BETWEEN date(?) AND date(?)", (period["start"], period["end"])


def _sales_chart(cid, period=None):
    period = period or _period_context()
    where, dates = _period_where("created_at", period)
    rows = query_all(
        f"""
        SELECT date(created_at) day, COALESCE(SUM(total),0) total
        FROM sales
        WHERE company_id=? AND {where}
        GROUP BY date(created_at)
        """,
        (cid, *dates),
    )
    by_day = {row["day"]: float(row["total"]) for row in rows}
    start = datetime.strptime(period["start"], "%Y-%m-%d").date()
    end = datetime.strptime(period["end"], "%Y-%m-%d").date()
    total_days = max(1, (end - start).days + 1)
    step = max(1, (total_days + 9) // 10)
    data = []
    max_total = max(by_day.values(), default=1)
    for offset in range(0, total_days, step):
        day = start + timedelta(days=offset)
        chunk = [day + timedelta(days=i) for i in range(step) if day + timedelta(days=i) <= end]
        total = sum(by_day.get(item.isoformat(), 0) for item in chunk)
        data.append({"label": day.strftime("%d/%m"), "total": total, "height": max(8, int(total / max_total * 100)) if max_total else 8})
    return data


def _report_summary(cid, period):
    where, dates = _period_where("created_at", period)
    sales = query_one(
        f"SELECT COALESCE(SUM(total),0) revenue, COUNT(*) sales, COALESCE(AVG(total),0) ticket FROM sales WHERE company_id=? AND {where}",
        (cid, *dates),
    )
    orders = query_one(f"SELECT COUNT(*) orders FROM orders WHERE company_id=? AND {where}", (cid, *dates))
    customers = query_one(
        f"SELECT COUNT(DISTINCT COALESCE(NULLIF(customer_name,''), 'Cliente ' || id)) customers FROM orders WHERE company_id=? AND {where}",
        (cid, *dates),
    )
    return {"revenue": sales["revenue"], "sales": sales["sales"], "ticket": sales["ticket"], "orders": orders["orders"], "customers": customers["customers"]}


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


def _top_products_period(cid, period, limit=6):
    where, dates = _period_where("o.created_at", period)
    rows = query_all(
        f"""
        SELECT oi.product_name name, COALESCE(p.category,'Vendas') category,
               COALESCE(SUM(oi.quantity),0) sold, COALESCE(SUM(oi.quantity * oi.unit_price),0) total
        FROM order_items oi
        JOIN orders o ON o.id=oi.order_id
        LEFT JOIN products p ON p.id=oi.product_id
        WHERE o.company_id=? AND {where}
        GROUP BY oi.product_name, p.category
        ORDER BY sold DESC, total DESC
        LIMIT ?
        """,
        (cid, *dates, limit),
    )
    return rows or _top_products(cid, limit)


def _report_customers(cid, period):
    where, dates = _period_where("created_at", period)
    return query_all(
        f"""
        SELECT COALESCE(NULLIF(customer_name,''),'Cliente balcão') name, COUNT(*) orders, COALESCE(SUM(total),0) total
        FROM orders
        WHERE company_id=? AND {where}
        GROUP BY COALESCE(NULLIF(customer_name,''),'Cliente balcão')
        ORDER BY total DESC, orders DESC
        LIMIT 5
        """,
        (cid, *dates),
    )


def _report_channels(cid, period):
    where, dates = _period_where("created_at", period)
    return query_all(
        f"""
        SELECT fulfillment_type name, COUNT(*) orders, COALESCE(SUM(total),0) total
        FROM orders
        WHERE company_id=? AND {where}
        GROUP BY fulfillment_type
        ORDER BY orders DESC
        """,
        (cid, *dates),
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


@bp.get("/reports")
@login_required
def reports():
    cid = company_id()
    period = _period_context()
    return render_template(
        "workspace.html",
        screen="reports",
        title="Relatorios",
        period=period,
        summary=_report_summary(cid, period),
        chart=_sales_chart(cid, period),
        top_products=_top_products_period(cid, period),
        clients=_report_customers(cid, period),
        channels=_report_channels(cid, period),
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
