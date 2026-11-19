import os
import secrets

from dotenv import load_dotenv
from flask import Flask, g, render_template

from database.db import crear_tablas
from logica.horarios import ahora, fin_turno, ya_inicio
from routes.admin import admin_bp
from routes.cliente import cliente_bp
from utils.auth import cargar_usuario, csrf_token, validar_csrf
from utils.presentacion import NOMBRES_ORIGINALES, PISOS, TIPOS, fecha_texto, imagen_cancha, moneda

load_dotenv()
app = Flask(__name__)
app.config.update(
    SECRET_KEY=os.environ.get("SECRET_KEY") or secrets.token_hex(32),
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
)
app.before_request(cargar_usuario)
app.before_request(validar_csrf)
app.jinja_env.filters.update(
    moneda=moneda, fecha_texto=fecha_texto, nombre_cancha=lambda n: NOMBRES_ORIGINALES.get(n, n)
)
app.jinja_env.globals.update(
    csrf_token=csrf_token,
    imagen_cancha=imagen_cancha,
    tipos=TIPOS,
    pisos=PISOS,
    fin_turno=fin_turno,
    ya_inicio=ya_inicio,
)


@app.context_processor
def contexto():
    return {"usuario_sesion": g.usuario, "hoy": ahora().date().isoformat()}


crear_tablas()
app.register_blueprint(cliente_bp)
app.register_blueprint(admin_bp)


@app.errorhandler(400)
@app.errorhandler(403)
@app.errorhandler(404)
def pagina_error(error):
    return render_template("404.html", codigo=error.code, detalle=error.description), error.code


if __name__ == "__main__":
    app.run()
