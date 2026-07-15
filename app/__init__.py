from pathlib import Path

from flask import Flask, redirect, render_template, session, url_for

from .config import config_class
from .database import close_db, init_db, seed_demo_data
from .errors import register_error_handlers
from .extensions import db, migrate
from .security import csrf_token, protect_csrf


def create_app(test_config=None):
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_object(config_class())

    if test_config:
        app.config.update(test_config)

    Path(app.instance_path).mkdir(parents=True, exist_ok=True)

    db.init_app(app)
    migrate.init_app(app, db)
    app.teardown_appcontext(close_db)
    app.before_request(protect_csrf)
    app.context_processor(lambda: {"csrf_token": csrf_token})
    register_error_handlers(app)

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
    from .routes.apex_admin import bp as apex_admin_bp

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
    app.register_blueprint(apex_admin_bp)

    @app.route("/")
    def index():
        if session.get("user_id"):
            return redirect(url_for("dashboard.index"))
        if session.get("platform_admin_id"):
            return redirect(url_for("apex_admin.dashboard"))
        return redirect(url_for("auth.login"))

    with app.app_context():
        init_db()
        if app.config.get("SEED_DEMO_DATA"):
            seed_demo_data()

    return app
