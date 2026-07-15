import os
from datetime import timedelta
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent.parent


def _database_url(default_sqlite=True):
    url = os.environ.get("DATABASE_URL") or os.environ.get("APEX_FOOD_DATABASE_URL")
    if url:
        return url.replace("postgres://", "postgresql+psycopg://", 1)
    if default_sqlite:
        return f"sqlite:///{BASE_DIR / 'instance' / 'apex_food.sqlite'}"
    return None


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY") or os.environ.get("APEX_FOOD_SECRET_KEY") or "dev-apex-food-change-me"
    DATABASE = os.environ.get("APEX_FOOD_DATABASE")
    SQLALCHEMY_DATABASE_URI = _database_url()
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    UPLOAD_FOLDER = os.environ.get("APEX_FOOD_UPLOAD_FOLDER", str(BASE_DIR / "instance" / "uploads"))
    MAX_CONTENT_LENGTH = int(os.environ.get("APEX_FOOD_MAX_UPLOAD_MB", "4")) * 1024 * 1024
    DEBUG = os.environ.get("APEX_FOOD_DEBUG", "0") == "1"
    TESTING = False
    WTF_CSRF_ENABLED = os.environ.get("APEX_FOOD_CSRF", "1") == "1"
    SEED_DEMO_DATA = os.environ.get("APEX_FOOD_SEED_DEMO", "0") == "1"
    PLATFORM_ADMIN_EMAIL = os.environ.get("APEX_PLATFORM_ADMIN_EMAIL", "admin@apexfood.local")
    PLATFORM_ADMIN_PASSWORD = os.environ.get("APEX_PLATFORM_ADMIN_PASSWORD")
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SECURE = False
    PERMANENT_SESSION_LIFETIME = timedelta(hours=int(os.environ.get("APEX_SESSION_HOURS", "12")))


class DevelopmentConfig(Config):
    DEBUG = os.environ.get("APEX_FOOD_DEBUG", "1") == "1"
    PLATFORM_ADMIN_PASSWORD = os.environ.get("APEX_PLATFORM_ADMIN_PASSWORD", "123456")


class TestingConfig(Config):
    TESTING = True
    WTF_CSRF_ENABLED = False
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"


class ProductionConfig(Config):
    SECRET_KEY = os.environ.get("SECRET_KEY") or os.environ.get("APEX_FOOD_SECRET_KEY")
    DEBUG = False
    SESSION_COOKIE_SECURE = True
    PLATFORM_ADMIN_PASSWORD = os.environ.get("APEX_PLATFORM_ADMIN_PASSWORD")


CONFIGS = {
    "development": DevelopmentConfig,
    "testing": TestingConfig,
    "production": ProductionConfig,
}


def config_class():
    env = os.environ.get("APEX_FOOD_ENV", "development")
    if env == "production" and not ProductionConfig.SECRET_KEY:
        raise RuntimeError("SECRET_KEY e obrigatoria em producao.")
    return CONFIGS.get(env, DevelopmentConfig)
