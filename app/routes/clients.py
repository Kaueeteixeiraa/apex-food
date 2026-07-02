from flask import Blueprint, flash, redirect, render_template, request, url_for

from ..database import execute, query_all
from .auth import company_id, login_required

bp = Blueprint("clients", __name__, url_prefix="/clients")


@bp.route("/", methods=("GET", "POST"))
@login_required
def index():
    cid = company_id()
    if request.method == "POST":
        execute(
            """
            INSERT INTO customers (company_id, name, phone, email, address)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                cid,
                request.form.get("name", "").strip(),
                request.form.get("phone", "").strip(),
                request.form.get("email", "").strip(),
                request.form.get("address", "").strip(),
            ),
        )
        flash("Cliente cadastrado.", "success")
        return redirect(url_for("clients.index"))

    clients = query_all(
        """
        SELECT
            customers.*,
            COUNT(orders.id) AS order_count,
            COALESCE(SUM(orders.total), 0) AS total_spent
        FROM customers
        LEFT JOIN orders ON orders.customer_id = customers.id
        WHERE customers.company_id = ?
        GROUP BY customers.id
        ORDER BY customers.name
        """,
        (cid,),
    )
    return render_template("clients.html", clients=clients)
