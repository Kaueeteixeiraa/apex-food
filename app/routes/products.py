from flask import Blueprint, flash, redirect, render_template, request, url_for

from ..database import execute, query_all, query_one
from ..models import PRODUCT_CATEGORIES, products_with_demo_images
from .auth import company_id, login_required

bp = Blueprint("products", __name__, url_prefix="/products")


@bp.route("/", methods=("GET", "POST"))
@login_required
def index():
    cid = company_id()
    if request.method == "POST":
        form = request.form
        execute(
            """
            INSERT INTO products
            (company_id, name, category, product_class, product_group, description, price, unit_value, cost_price, stock_quantity, min_stock, unit, sku, barcode, available, image_url, prep_time)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                cid,
                form.get("name", "").strip(),
                form.get("category", "Outros"),
                form.get("product_class", "").strip() or "Produto",
                form.get("product_group", "").strip(),
                form.get("description", "").strip(),
                float(form.get("price") or 0),
                float(form.get("unit_value") or form.get("price") or 0),
                float(form.get("cost_price") or 0),
                float(form.get("stock_quantity") or 0),
                float(form.get("min_stock") or 0),
                form.get("unit", "un").strip() or "un",
                form.get("sku", "").strip(),
                form.get("barcode", "").strip(),
                1 if form.get("available") else 0,
                form.get("image_url", "").strip(),
                int(form.get("prep_time") or 10),
            ),
        )
        flash("Produto cadastrado.", "success")
        return redirect(url_for("products.index"))

    selected_category = request.args.get("category", "Todos")
    selected_status = request.args.get("status", "Todos")
    search = request.args.get("q", "").strip()
    clauses = ["company_id = ?"]
    params = [cid]
    if selected_category in PRODUCT_CATEGORIES:
        clauses.append("category = ?")
        params.append(selected_category)
    if selected_status in ("Ativos", "Pausados"):
        clauses.append("available = ?")
        params.append(1 if selected_status == "Ativos" else 0)
    if search:
        clauses.append("(name LIKE ? OR description LIKE ? OR product_group LIKE ? OR sku LIKE ? OR barcode LIKE ?)")
        params.extend([f"%{search}%", f"%{search}%", f"%{search}%", f"%{search}%", f"%{search}%"])

    products = products_with_demo_images(
        query_all(
            f"SELECT * FROM products WHERE {' AND '.join(clauses)} ORDER BY available DESC, category, name",
            tuple(params),
        )
    )
    metrics = {
        "total": query_one("SELECT COUNT(*) value FROM products WHERE company_id=?", (cid,))["value"],
        "active": query_one("SELECT COUNT(*) value FROM products WHERE company_id=? AND available=1", (cid,))["value"],
        "avg": query_one("SELECT COALESCE(AVG(price),0) value FROM products WHERE company_id=?", (cid,))["value"],
        "stock": query_one("SELECT COALESCE(SUM(stock_quantity),0) value FROM products WHERE company_id=?", (cid,))["value"],
    }
    return render_template(
        "products.html",
        products=products,
        categories=PRODUCT_CATEGORIES,
        selected_category=selected_category,
        selected_status=selected_status,
        search=search,
        metrics=metrics,
    )


@bp.post("/<int:product_id>/toggle")
@login_required
def toggle(product_id):
    cid = company_id()
    product = query_one("SELECT available FROM products WHERE id = ? AND company_id = ?", (product_id, cid))
    if product:
        execute(
            "UPDATE products SET available = ? WHERE id = ? AND company_id = ?",
            (0 if product["available"] else 1, product_id, cid),
        )
        flash("Disponibilidade atualizada.", "success")
    return redirect(url_for("products.index"))
