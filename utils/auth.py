import secrets
from contextlib import closing
from functools import wraps

from flask import abort, g, redirect, request, session, url_for

from database.db import get_connection


def cargar_usuario():
    g.usuario = None
    if session.get("id_usuario"):
        with closing(get_connection()) as conn:
            g.usuario = conn.execute(
                "SELECT id, nombre, email, telefono, es_admin FROM usuario WHERE id=? AND activo=1",
                (session["id_usuario"],),
            ).fetchone()
        if not g.usuario:
            session.clear()


def csrf_token():
    if "csrf" not in session:
        session["csrf"] = secrets.token_urlsafe(32)
    return session["csrf"]


def validar_csrf():
    if request.method != "POST":
        return
    esperado = session.get("csrf", "")
    recibido = request.form.get("csrf", "")
    if not esperado or not secrets.compare_digest(esperado.encode(), recibido.encode()):
        abort(400, description="El formulario venció. Volvé a abrir la página y probá otra vez.")


def login_requerido(f):
    @wraps(f)
    def envuelta(*args, **kwargs):
        if g.usuario is None:
            return redirect(url_for("cliente.login", siguiente="perfil"))
        return f(*args, **kwargs)

    return envuelta


def admin_requerido(f):
    @wraps(f)
    def envuelta(*args, **kwargs):
        if g.usuario is None:
            return redirect(url_for("cliente.login", siguiente="admin"))
        if not g.usuario["es_admin"]:
            abort(403)
        return f(*args, **kwargs)

    return envuelta
