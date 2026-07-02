from flask import Blueprint, flash, redirect, render_template, request, url_for

from ..database import execute, query_all, query_one
from ..models import PRODUCT_CATEGORIES
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
            (company_id, name, category, description, price, available, image_url, prep_time)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                cid,
                form.get("name", "").strip(),
                form.get("category", "Outros"),
                form.get("description", "").strip(),
                float(form.get("price") or 0),
                1 if form.get("available") else 0,
                form.get("image_url", "").strip(),
                int(form.get("prep_time") or 10),
            ),
        )
        flash("Produto cadastrado.", "success")
        return redirect(url_for("products.index"))

    products = query_all(
        "SELECT * FROM products WHERE company_id = ? ORDER BY category, name",
        (cid,),
    )
    return render_template("products.html", products=products, categories=PRODUCT_CATEGORIES)


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
