import re
from contextlib import closing
from datetime import timedelta

from flask import Blueprint, abort, flash, g, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash

from database.db import get_connection
from logica.horarios import (
    HORARIOS_POSIBLES,
    agenda_del_dia,
    ahora,
    fecha_valida,
    horarios_cancha,
    obtener_horarios,
    ya_inicio,
)
from utils.auth import login_requerido
from utils.presentacion import DIAS, TIPOS

cliente_bp = Blueprint("cliente", __name__)


def dia_consulta():
    valor = request.args.get("fecha")
    hoy = ahora().date().isoformat()
    if valor and (not fecha_valida(valor) or valor < hoy):
        flash("Elegí una fecha de hoy en adelante.", "error")
        return hoy
    return valor or hoy


def cancha_activa(conn, identificador):
    cancha = conn.execute("SELECT * FROM cancha WHERE id=? AND activa=1", (identificador,)).fetchone()
    if cancha is None:
        abort(404)
    return cancha


@cliente_bp.get("/")
def index():
    fecha = dia_consulta()
    tipo = request.args.get("tipo", "")
    if tipo not in TIPOS:
        tipo = ""
    with closing(get_connection()) as conn:
        todas = conn.execute("SELECT * FROM cancha WHERE activa=1 ORDER BY id").fetchall()
        agenda = agenda_del_dia(conn, fecha)
    momento = ahora()
    canchas = [c for c in todas if not tipo or c["tipo"] == tipo]
    libres = {
        c["id"]: sum(
            estado == "disponible" for _, estado in horarios_cancha(c["id"], fecha, agenda, momento)
        )
        for c in canchas
    }
    return render_template(
        "index.html",
        canchas=canchas,
        fecha=fecha,
        tipo=tipo,
        libres=libres,
        formatos=[t for t in TIPOS if any(c["tipo"] == t for c in todas)],
    )


def contexto_acceso():
    siguiente = request.args.get("siguiente")
    if siguiente == "reserva":
        return {
            "siguiente": siguiente,
            "id": request.args.get("id", type=int),
            "fecha": request.args.get("fecha", ""),
            "hora": request.args.get("hora", ""),
        }
    return {"siguiente": siguiente} if siguiente in ("perfil", "admin") else {}


def entrar(usuario_id, es_admin):
    session.clear()
    session["id_usuario"] = usuario_id
    destino = contexto_acceso()
    siguiente = destino.pop("siguiente", None)
    if siguiente == "reserva":
        return redirect(url_for("cliente.confirmar_reserva", **destino))
    if siguiente == "perfil":
        return redirect(url_for("cliente.perfil"))
    if siguiente == "admin" and not es_admin:
        flash(
            "Esta cuenta tiene acceso de jugador. Administración requiere una cuenta del complejo.",
            "error",
        )
    return redirect(url_for("admin.panel" if es_admin else "cliente.index"))


@cliente_bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email", "").strip()
        with closing(get_connection()) as conn:
            usuario = conn.execute(
                "SELECT * FROM usuario WHERE email=? COLLATE NOCASE AND activo=1 ORDER BY email=? DESC LIMIT 1",
                (email, email),
            ).fetchone()
        if usuario and check_password_hash(usuario["contrasena"], request.form.get("contrasena", "")):
            return entrar(usuario["id"], usuario["es_admin"])
        flash("Revisá tu correo y contraseña e intentá de nuevo.", "error")
    return render_template("login.html", destino=contexto_acceso())


@cliente_bp.route("/registro", methods=["GET", "POST"])
def registro():
    if request.method == "POST":
        nombre = request.form.get("nombre", "").strip()
        email = request.form.get("email", "").strip().lower()
        telefono = request.form.get("telefono", "").strip()
        clave = request.form.get("contraseña", "")
        if not nombre or len(nombre) > 100:
            flash("Ingresá un nombre de hasta 100 caracteres.", "error")
        elif len(email) > 254 or not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", email):
            flash("Ingresá un correo electrónico válido.", "error")
        elif not re.fullmatch(r"[0-9]{7,12}", telefono):
            flash("El teléfono debe tener entre 7 y 12 dígitos.", "error")
        elif not 8 <= len(clave) <= 256:
            flash("Usá una contraseña de entre 8 y 256 caracteres.", "error")
        else:
            clave_hash = generate_password_hash(clave)
            with closing(get_connection()) as conn, conn:
                conn.execute("BEGIN IMMEDIATE")
                if conn.execute(
                    "SELECT id FROM usuario WHERE email=? COLLATE NOCASE", (email,)
                ).fetchone():
                    flash("Ese correo ya está registrado. Podés ingresar con tu cuenta.", "error")
                else:
                    fila = conn.execute(
                        "INSERT INTO usuario(nombre,email,telefono,contrasena) VALUES(?,?,?,?)",
                        (nombre, email, telefono, clave_hash),
                    )
                    return entrar(fila.lastrowid, False)
    return render_template("registro.html", destino=contexto_acceso())


@cliente_bp.route("/logout", methods=["GET", "POST"])
def logout():
    if request.method == "GET" and g.usuario:
        return render_template("salir.html")
    if request.method == "POST":
        session.clear()
    return redirect(url_for("cliente.index"))


@cliente_bp.get("/cancha/<int:id>")
def detalle_cancha(id):
    fecha = dia_consulta()
    with closing(get_connection()) as conn:
        cancha = cancha_activa(conn, id)
        horarios = obtener_horarios(id, fecha, conn)
    inicio = ahora().date()
    dias = [inicio + timedelta(days=i) for i in range(7)]
    return render_template(
        "cancha.html", cancha=cancha, fecha=fecha, horarios=horarios, dias=dias, nombres_dias=DIAS
    )


@cliente_bp.route("/reserva", methods=["GET", "POST"])
def confirmar_reserva():
    enviando = request.method == "POST"
    datos = request.form if enviando else request.args
    ident = datos.get("id_cancha" if enviando else "id", type=int)
    fecha, hora = datos.get("fecha", ""), datos.get("hora", "")
    if not ident or not fecha_valida(fecha) or hora not in HORARIOS_POSIBLES:
        flash("Elegí una cancha, una fecha y un horario para reservar.", "error")
        return redirect(url_for("cliente.index"))
    with closing(get_connection()) as conn, conn:
        if enviando:
            conn.execute("BEGIN IMMEDIATE")
        cancha = cancha_activa(conn, ident)
        if dict(obtener_horarios(ident, fecha, conn)).get(hora) != "disponible":
            flash("Ese turno ya no está disponible. Elegí otro horario.", "error")
            return redirect(url_for("cliente.detalle_cancha", id=ident, fecha=fecha))
        if not g.usuario:
            return redirect(
                url_for("cliente.login", siguiente="reserva", id=ident, fecha=fecha, hora=hora)
            )
        if enviando:
            cedula, telefono = datos.get("cedula", "").strip(), datos.get("telefono", "").strip()
            if not re.fullmatch(r"[0-9]{6,9}", cedula) or not re.fullmatch(r"[0-9]{7,12}", telefono):
                flash("Revisá la cédula (6 a 9 dígitos) y el teléfono (7 a 12 dígitos).", "error")
            else:
                web = datos.get("pago_web") == "on"
                descuento = 0.05 if web else 0
                conn.execute(
                    """INSERT INTO reserva(id_cancha,id_usuario,fecha,hora_inicio,cedula,telefono,estado,
                            pago_web,descuento,precio_final,fecha_creacion) VALUES(?,?,?,?,?,?,'confirmada',?,?,?,?)""",
                    (
                        ident,
                        g.usuario["id"],
                        fecha,
                        hora,
                        cedula,
                        telefono,
                        web,
                        descuento,
                        round(cancha["precio"] * (1 - descuento), 2),
                        ahora().date().isoformat(),
                    ),
                )
                flash("Tu reserva quedó confirmada.", "exito")
                return redirect(url_for("cliente.perfil"))
    return render_template("reserva.html", cancha=cancha, fecha=fecha, hora=hora)


@cliente_bp.get("/perfil")
@login_requerido
def perfil():
    with closing(get_connection()) as conn:
        reservas = conn.execute(
            """SELECT r.*, c.nombre AS nombre_cancha, c.tipo, c.foto FROM reserva r
              JOIN cancha c ON c.id=r.id_cancha WHERE r.id_usuario=? ORDER BY r.fecha, r.hora_inicio, r.id""",
            (g.usuario["id"],),
        ).fetchall()
    proximas, historial = [], []
    momento = ahora()
    for r in reservas:
        grupo = (
            historial
            if r["estado"] == "cancelada" or ya_inicio(r["fecha"], r["hora_inicio"], momento)
            else proximas
        )
        grupo.append(r)
    return render_template("perfil.html", proximas=proximas, historial=historial[::-1])


@cliente_bp.post("/perfil/reserva/<int:id>/cancelar")
@login_requerido
def cancelar_reserva(id):
    with closing(get_connection()) as conn, conn:
        conn.execute("BEGIN IMMEDIATE")
        r = conn.execute(
            "SELECT * FROM reserva WHERE id=? AND id_usuario=?", (id, g.usuario["id"])
        ).fetchone()
        if not r:
            abort(404)
        if r["estado"] == "cancelada" or ya_inicio(r["fecha"], r["hora_inicio"]):
            flash("Solo podés cancelar una reserva vigente antes del inicio.", "error")
        else:
            conn.execute("UPDATE reserva SET estado='cancelada' WHERE id=?", (id,))
            flash("Reserva cancelada. El turno volvió a estar disponible.", "exito")
    return redirect(url_for("cliente.perfil"))
