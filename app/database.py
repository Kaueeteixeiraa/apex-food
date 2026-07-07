import sqlite3
from pathlib import Path

from flask import current_app, g
from werkzeug.security import generate_password_hash


def get_database_path():
    configured = current_app.config.get("DATABASE")
    if configured:
        return configured
    return str(Path(current_app.instance_path) / "apex_food.sqlite")


def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(get_database_path())
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db


def close_db(error=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db():
    db = get_db()
    schema_path = Path(current_app.root_path) / "schema.sql"
    db.executescript(schema_path.read_text(encoding="utf-8"))
    ensure_product_columns(db)
    ensure_cash_columns(db)
    ensure_cash_movements(db)
    normalize_order_statuses(db)
    ensure_demo_role_users(db)
    db.commit()


def ensure_product_columns(db):
    existing = {row["name"] for row in db.execute("PRAGMA table_info(products)").fetchall()}
    columns = {
        "product_class": "TEXT NOT NULL DEFAULT 'Produto'",
        "product_group": "TEXT",
        "unit_value": "REAL NOT NULL DEFAULT 0",
        "cost_price": "REAL NOT NULL DEFAULT 0",
        "stock_quantity": "REAL NOT NULL DEFAULT 0",
        "min_stock": "REAL NOT NULL DEFAULT 0",
        "unit": "TEXT NOT NULL DEFAULT 'un'",
        "sku": "TEXT",
        "barcode": "TEXT",
        "addons": "TEXT",
        "combo_items": "TEXT",
    }
    for name, definition in columns.items():
        if name not in existing:
            db.execute(f"ALTER TABLE products ADD COLUMN {name} {definition}")


def ensure_cash_columns(db):
    existing = {row["name"] for row in db.execute("PRAGMA table_info(cash_registers)").fetchall()}
    columns = {
        "closing_amount": "REAL NOT NULL DEFAULT 0",
        "expected_amount": "REAL NOT NULL DEFAULT 0",
        "difference_amount": "REAL NOT NULL DEFAULT 0",
        "closed_by": "TEXT",
    }
    for name, definition in columns.items():
        if name not in existing:
            db.execute(f"ALTER TABLE cash_registers ADD COLUMN {name} {definition}")


def ensure_cash_movements(db):
    db.execute(
        """
        CREATE TABLE IF NOT EXISTS cash_movements (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            company_id INTEGER NOT NULL,
            register_id INTEGER NOT NULL,
            type TEXT NOT NULL,
            amount REAL NOT NULL DEFAULT 0,
            note TEXT,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (company_id) REFERENCES companies (id) ON DELETE CASCADE,
            FOREIGN KEY (register_id) REFERENCES cash_registers (id) ON DELETE CASCADE
        )
        """
    )


def normalize_order_statuses(db):
    db.execute("UPDATE orders SET status = 'Recebido' WHERE status = 'Novo'")
    db.execute("UPDATE orders SET status = 'Preparando' WHERE status = 'Em preparo'")


def ensure_demo_role_users(db):
    company = db.execute("SELECT id FROM companies WHERE email = ?", ("demo@apexfood.local",)).fetchone()
    if not company:
        return
    users = [
        ("Caixa Demo", "caixa@apexfood.local", "Caixa"),
        ("Cozinha Demo", "cozinha@apexfood.local", "Cozinha"),
        ("Entregador Demo", "entregador@apexfood.local", "Entregador"),
    ]
    for name, email, role in users:
        exists = db.execute("SELECT id FROM users WHERE lower(email)=?", (email,)).fetchone()
        if not exists:
            db.execute(
                "INSERT INTO users (company_id, name, email, password_hash, role) VALUES (?, ?, ?, ?, ?)",
                (company["id"], name, email, generate_password_hash("123456"), role),
            )


def query_one(sql, params=()):
    return get_db().execute(sql, params).fetchone()


def query_all(sql, params=()):
    return get_db().execute(sql, params).fetchall()


def execute(sql, params=()):
    db = get_db()
    cursor = db.execute(sql, params)
    db.commit()
    return cursor


def seed_demo_data():
    db = get_db()
    company = db.execute("SELECT id FROM companies WHERE email = ?", ("demo@apexfood.local",)).fetchone()
    if company:
        return

    cursor = db.execute(
        """
        INSERT INTO companies
        (legal_name, trade_name, cnpj, email, phone, segment, address, city, state, cep)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            "Apex Food Restaurante Demo Ltda",
            "Apex Food Demo",
            "00.000.000/0001-00",
            "demo@apexfood.local",
            "(11) 4002-8922",
            "Restaurante",
            "Av. Neon, 1200",
            "Sao Paulo",
            "SP",
            "01000-000",
        ),
    )
    company_id = cursor.lastrowid

    db.execute(
        """
        INSERT INTO users (company_id, name, email, password_hash, role)
        VALUES (?, ?, ?, ?, ?)
        """,
        (
            company_id,
            "Administrador Demo",
            "admin@apexfood.local",
            generate_password_hash("123456"),
            "Administrador",
        ),
    )

    products = [
        ("Pizza Apex Pepperoni", "Pizzas", "Venda", "Pizzas premium", "Massa fina, pepperoni, mozzarella e molho especial.", 59.9, 59.9, 24.0, 18, 5, "un", "PIZ-001", "", "Borda recheada; queijo extra", "", 1, 25),
        ("Burger Neon Smash", "Hamburgueres", "Venda", "Smash", "Blend 160g, cheddar, cebola crispy e molho da casa.", 34.9, 34.9, 13.5, 24, 8, "un", "BUR-001", "", "Bacon; cheddar extra", "", 1, 15),
        ("Combo Fast Lunch", "Combos", "Venda", "Combos", "Burger, fritas e bebida.", 49.9, 49.9, 21.0, 15, 4, "un", "COM-001", "", "", "Burger Neon Smash + fritas + bebida", 1, 18),
        ("Suco Tropical", "Bebidas", "Venda", "Bebidas naturais", "Suco natural gelado.", 12.0, 12.0, 4.0, 30, 10, "un", "BEB-001", "", "Sem acucar; gelo extra", "", 1, 5),
        ("Brownie Vulcano", "Sobremesas", "Venda", "Doces", "Brownie quente com calda.", 18.5, 18.5, 6.5, 20, 6, "un", "SOB-001", "", "Sorvete; calda extra", "", 1, 8),
    ]
    db.executemany(
        """
        INSERT INTO products
        (company_id, name, category, product_class, product_group, description, price, unit_value, cost_price, stock_quantity, min_stock, unit, sku, barcode, addons, combo_items, available, prep_time)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        [(company_id, *product) for product in products],
    )

    customers = [
        ("Marina Costa", "(11) 99999-0001", "marina@example.com", "Rua das Flores, 45"),
        ("Rafael Lima", "(11) 99999-0002", "rafael@example.com", "Av. Central, 88"),
    ]
    db.executemany(
        "INSERT INTO customers (company_id, name, phone, email, address) VALUES (?, ?, ?, ?, ?)",
        [(company_id, *customer) for customer in customers],
    )

    areas = ["Salao Principal", "Area Externa", "VIP"]
    area_ids = []
    for area in areas:
        area_ids.append(db.execute("INSERT INTO areas (company_id, name) VALUES (?, ?)", (company_id, area)).lastrowid)

    tables = [
        (area_ids[0], "Mesa 01", "round", 4, "Livre", 80, 80, 104, 104, "", 0),
        (area_ids[0], "Mesa 02", "square", 2, "Ocupada", 260, 100, 104, 104, "Marina Costa", 86.4),
        (area_ids[0], "Mesa 03", "rect", 6, "Pedido em preparo", 460, 90, 150, 94, "Rafael Lima", 59.9),
        (area_ids[1], "Deck 01", "round", 4, "Reservada", 120, 150, 110, 110, "", 0),
        (area_ids[2], "VIP 01", "rect", 8, "Conta solicitada", 180, 120, 180, 100, "Evento Apex", 240.0),
    ]
    db.executemany(
        """
        INSERT INTO tables
        (company_id, area_id, name, shape, seats, status, x, y, width, height, customer_name, total)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        [(company_id, *table) for table in tables],
    )

    db.executemany(
        """
        INSERT INTO employees (company_id, name, role, email, phone, permission)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        [
            (company_id, "Lucas Barros", "Gerente", "lucas@apexfood.local", "(11) 98888-0001", "Gerente"),
            (company_id, "Bianca Souza", "Caixa", "bianca@apexfood.local", "(11) 98888-0002", "Caixa"),
            (company_id, "Diego Ramos", "Cozinha", "diego@apexfood.local", "(11) 98888-0003", "Cozinha"),
        ],
    )

    db.executemany(
        """
        INSERT INTO inventory_items (company_id, name, quantity, unit, min_stock)
        VALUES (?, ?, ?, ?, ?)
        """,
        [
            (company_id, "Mussarela", 8, "kg", 5),
            (company_id, "Carne blend", 3, "kg", 4),
            (company_id, "Caixas de pizza", 40, "un", 20),
            (company_id, "Refrigerante lata", 72, "un", 30),
        ],
    )

    first_product = db.execute("SELECT id, name, price FROM products WHERE company_id = ? LIMIT 1", (company_id,)).fetchone()
    second_product = db.execute("SELECT id, name, price FROM products WHERE company_id = ? LIMIT 1 OFFSET 1", (company_id,)).fetchone()

    order_cursor = db.execute(
        """
        INSERT INTO orders
        (company_id, customer_name, fulfillment_type, table_id, status, total)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (company_id, "Marina Costa", "Mesa", 2, "Preparando", 86.4),
    )
    order_id = order_cursor.lastrowid
    db.executemany(
        """
        INSERT INTO order_items (order_id, product_id, product_name, quantity, unit_price)
        VALUES (?, ?, ?, ?, ?)
        """,
        [
            (order_id, first_product["id"], first_product["name"], 1, first_product["price"]),
            (order_id, second_product["id"], second_product["name"], 1, second_product["price"]),
        ],
    )

    db.execute(
        """
        INSERT INTO orders
        (company_id, customer_name, fulfillment_type, status, total)
        VALUES (?, ?, ?, ?, ?)
        """,
        (company_id, "Entrega rapida", "Entrega", "Recebido", 49.9),
    )

    db.execute(
        """
        INSERT INTO cash_registers (company_id, status, opening_amount, opened_at)
        VALUES (?, ?, ?, datetime('now'))
        """,
        (company_id, "Aberto", 200.0),
    )

    db.execute(
        """
        INSERT INTO sales (company_id, order_id, subtotal, discount, service_fee, total, payment_method, status)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (company_id, order_id, 86.4, 0, 8.64, 95.04, "Pix", "Finalizada"),
    )

    ensure_demo_role_users(db)
    db.commit()
