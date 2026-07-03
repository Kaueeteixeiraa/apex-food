import json
from datetime import datetime, timedelta

from flask import Blueprint, render_template

from ..database import query_all, query_one
from .auth import company_id, login_required

bp = Blueprint("dashboard", __name__, url_prefix="/dashboard")


@bp.get("/")
@login_required
def index():
    cid = company_id()
    company = query_one("SELECT trade_name FROM companies WHERE id = ?", (cid,))
    total_tables = query_one("SELECT COUNT(*) AS value FROM tables WHERE company_id = ?", (cid,))["value"]
    summary = {
        "sales_today": query_one(
            """
            SELECT COALESCE(SUM(total), 0) AS value
            FROM sales
            WHERE company_id = ? AND date(created_at) = date('now')
            """,
            (cid,),
        )["value"],
        "orders_today": query_one(
            """
            SELECT COUNT(*) AS value
            FROM orders
            WHERE company_id = ? AND date(created_at) = date('now')
            """,
            (cid,),
        )["value"],
        "avg_ticket": query_one(
            """
            SELECT COALESCE(AVG(total), 0) AS value
            FROM sales
            WHERE company_id = ? AND date(created_at) = date('now')
            """,
            (cid,),
        )["value"],
        "occupied_tables": query_one(
            """
            SELECT COUNT(*) AS value
            FROM tables
            WHERE company_id = ? AND status IN ('Ocupada', 'Pedido em preparo', 'Conta solicitada')
            """,
            (cid,),
        )["value"],
        "total_tables": total_tables,
        "preparing_orders": query_one(
            "SELECT COUNT(*) AS value FROM orders WHERE company_id = ? AND status = 'Em preparo'",
            (cid,),
        )["value"],
    }

    low_stock = query_all(
        """
        SELECT name, quantity, unit, min_stock
        FROM inventory_items
        WHERE company_id = ? AND quantity <= min_stock
        ORDER BY quantity ASC
        LIMIT 5
        """,
        (cid,),
    )

    recent_orders = query_all(
        """
        SELECT
            orders.*,
            tables.name AS table_name,
            strftime('%H:%M', orders.created_at) AS order_time,
            GROUP_CONCAT(order_items.quantity || 'x ' || order_items.product_name, ', ') AS items_summary
        FROM orders
        LEFT JOIN tables ON tables.id = orders.table_id
        LEFT JOIN order_items ON order_items.order_id = orders.id
        WHERE orders.company_id = ?
        GROUP BY orders.id
        ORDER BY orders.created_at DESC
        LIMIT 5
        """,
        (cid,),
    )

    reserved_tables = query_one(
        "SELECT COUNT(*) AS value FROM tables WHERE company_id = ? AND status = 'Reservada'",
        (cid,),
    )["value"]
    delayed_orders = query_one(
        """
        SELECT COUNT(*) AS value
        FROM orders
        WHERE company_id = ?
          AND status IN ('Novo', 'Em preparo')
          AND datetime(created_at) <= datetime('now', '-25 minutes')
        """,
        (cid,),
    )["value"]

    dashboard_alerts = [
        {
            "kind": "danger",
            "icon": "!",
            "title": "Estoque baixo",
            "description": f"{len(low_stock)} item(ns) abaixo do minimo operacional.",
        },
        {
            "kind": "warning",
            "icon": "T",
            "title": "Pedidos atrasados",
            "description": f"{delayed_orders} pedido(s) precisam de atencao da cozinha.",
        },
        {
            "kind": "info",
            "icon": "R",
            "title": "Mesas reservadas",
            "description": f"{reserved_tables} reserva(s) ativas para acompanhar.",
        },
    ]

    raw_sales = query_all(
        """
        SELECT date(created_at) AS day, COALESCE(SUM(total), 0) AS total
        FROM sales
        WHERE company_id = ? AND date(created_at) >= date('now', '-6 day')
        GROUP BY date(created_at)
        """,
        (cid,),
    )
    totals_by_day = {row["day"]: row["total"] for row in raw_sales}
    today = datetime.now().date()
    chart = []
    for offset in range(6, -1, -1):
        day = today - timedelta(days=offset)
        key = day.isoformat()
        chart.append({"label": day.strftime("%d/%m"), "total": float(totals_by_day.get(key, 0))})

    status_rows = query_all(
        """
        SELECT status, COUNT(*) AS count
        FROM orders
        WHERE company_id = ?
        GROUP BY status
        """,
        (cid,),
    )
    status_map = {row["status"]: row["count"] for row in status_rows}
    status_chart = [
        {"label": "Novo", "value": int(status_map.get("Novo", 0)), "color": "#3B82F6"},
        {"label": "Em preparo", "value": int(status_map.get("Em preparo", 0)), "color": "#22D3EE"},
        {"label": "Pronto", "value": int(status_map.get("Pronto", 0)), "color": "#22C55E"},
        {"label": "Entregue", "value": int(status_map.get("Entregue", 0)), "color": "#38BDF8"},
        {"label": "Cancelado", "value": int(status_map.get("Cancelado", 0)), "color": "#EF4444"},
    ]

    payment_rows = query_all(
        """
        SELECT payment_method, COALESCE(SUM(total), 0) AS total
        FROM sales
        WHERE company_id = ? AND date(created_at) = date('now')
        GROUP BY payment_method
        """,
        (cid,),
    )
    payment_map = {row["payment_method"]: float(row["total"]) for row in payment_rows}
    payment_chart = [
        {"label": "Dinheiro", "value": payment_map.get("Dinheiro", 0), "color": "#22C55E"},
        {"label": "Cartao", "value": payment_map.get("Cartao", 0), "color": "#3B82F6"},
        {"label": "Pix", "value": payment_map.get("Pix", 0), "color": "#0EA5FF"},
        {"label": "Outros", "value": payment_map.get("Outros", 0), "color": "#67E8F9"},
    ]
    payment_total = sum(item["value"] for item in payment_chart)

    return render_template(
        "dashboard.html",
        summary=summary,
        low_stock=low_stock,
        recent_orders=recent_orders,
        chart_json=json.dumps(chart),
        status_chart_json=json.dumps(status_chart),
        payment_chart_json=json.dumps(payment_chart),
        payment_total=payment_total,
        dashboard_alerts=dashboard_alerts,
        company=company,
        current_date=datetime.now().strftime("%d/%m/%Y"),
        dashboard_name="João Admin",
        dashboard_role="Administrador",
    )
