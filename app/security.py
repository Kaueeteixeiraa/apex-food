import secrets

from flask import abort, current_app, request, session


SAFE_METHODS = {"GET", "HEAD", "OPTIONS", "TRACE"}


def csrf_token():
    token = session.get("_csrf_token")
    if not token:
        token = secrets.token_urlsafe(32)
        session["_csrf_token"] = token
    return token


def protect_csrf():
    if current_app.config.get("TESTING") or not current_app.config.get("WTF_CSRF_ENABLED", True):
        return
    if request.method in SAFE_METHODS or request.endpoint == "static":
        return
    sent = request.form.get("_csrf_token") or request.headers.get("X-CSRF-Token")
    if not sent or sent != session.get("_csrf_token"):
        abort(403)
