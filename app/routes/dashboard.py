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
        SELECT orders.*, tables.name AS table_name
        FROM orders
        LEFT JOIN tables ON tables.id = orders.table_id
        WHERE orders.company_id = ?
        ORDER BY orders.created_at DESC
        LIMIT 6
        """,
        (cid,),
    )

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

    return render_template(
        "dashboard.html",
        summary=summary,
        low_stock=low_stock,
        recent_orders=recent_orders,
        chart_json=json.dumps(chart),
    )
