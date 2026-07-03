from pathlib import Path

from flask import Flask, redirect, session, url_for

from .config import Config
from .database import close_db, init_db, seed_demo_data


def create_app(test_config=None):
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_object(Config)

    if test_config:
        app.config.update(test_config)

    Path(app.instance_path).mkdir(parents=True, exist_ok=True)

    app.teardown_appcontext(close_db)

    from .routes.auth import bp as auth_bp
    from .routes.dashboard import bp as dashboard_bp
    from .routes.products import bp as products_bp
    from .routes.orders import bp as orders_bp
    from .routes.pos import bp as pos_bp
    from .routes.floor import bp as floor_bp
    from .routes.clients import bp as clients_bp
    from .routes.inventory import bp as inventory_bp
    from .routes.employees import bp as employees_bp
    from .routes.kitchen import bp as kitchen_bp
    from .routes.pages import bp as pages_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(products_bp)
    app.register_blueprint(orders_bp)
    app.register_blueprint(pos_bp)
    app.register_blueprint(floor_bp)
    app.register_blueprint(clients_bp)
    app.register_blueprint(inventory_bp)
    app.register_blueprint(employees_bp)
    app.register_blueprint(kitchen_bp)
    app.register_blueprint(pages_bp)

    @app.route("/")
    def index():
        if session.get("user_id"):
            return redirect(url_for("dashboard.index"))
        return redirect(url_for("auth.login"))

    with app.app_context():
        init_db()
        seed_demo_data()

    return app
