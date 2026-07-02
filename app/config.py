import os


class Config:
    SECRET_KEY = os.environ.get("APEX_FOOD_SECRET_KEY", "dev-apex-food-change-me")
    DATABASE = os.environ.get("APEX_FOOD_DATABASE")
