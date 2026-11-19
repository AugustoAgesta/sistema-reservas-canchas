import math
import re
from contextlib import closing
from datetime import date, timedelta
from pathlib import Path

from flask import Blueprint, abort, current_app, flash, redirect, render_template, request, url_for

from database.db import get_connection
from logica.horarios import (
    HORARIOS_POSIBLES,
    agenda_del_dia,
    ahora,
    fecha_valida,
    fin_turno,
    horarios_cancha,
    ya_inicio,
)
from utils.auth import admin_requerido
from utils.presentacion import OPTIMIZADAS, PISOS, TIPOS

admin_bp = Blueprint("admin", __name__, url_prefix="/admin")


def fotos_disponibles():
    return sorted(
        p.name
        for p in (Path(current_app.static_folder) / "img").iterdir()
        if p.suffix.lower() in {".jpg", ".jpeg", ".png", ".webp"}
        and p.name not in {*OPTIMIZADAS.values(), "portada.webp", "404.png"}
    )


def formulario_cancha(id=None):
    fotos = fotos_disponibles()
    with closing(get_connection()) as conn, conn:
        cancha = (
            None if id is None else conn.execute("SELECT * FROM cancha WHERE id=?", (id,)).fetchone()
        )
        if id is not None and cancha is None:
            abort(404)
        if request.method == "POST":
            f = request.form
            nombre, tipo, piso = (f.get(campo, "").strip() for campo in ("nombre", "tipo", "piso"))
            foto = f.get("foto", "").strip()
            precio = f.get("precio", type=float)
            if not nombre or len(nombre) > 100 or tipo not in TIPOS or piso not in PISOS:
                flash("Revisá el nombre, el formato y el piso de la cancha.", "error")
            elif precio is None or not math.isfinite(precio) or not 0 < precio <= 99999999:
                flash("Ingresá un precio por hora mayor que cero, de hasta 99.999.999 pesos.", "error")
            elif foto and foto not in fotos and (not cancha or foto != cancha["foto"]):
                flash("Elegí una de las fotos del complejo.", "error")
            else:
                datos = nombre, tipo, piso, int("techo" in f), round(precio, 2), foto
                if cancha:
                    conn.execute(
                        "UPDATE cancha SET nombre=?,tipo=?,piso=?,techo=?,precio=?,foto=?,activa=? WHERE id=?",
                        (*datos, int("activa" in f), id),
                    )
                else:
                    conn.execute(
                        "INSERT INTO cancha(nombre,tipo,piso,techo,precio,foto) VALUES(?,?,?,?,?,?)",
                        datos,
                    )
                flash("Los datos de la cancha quedaron guardados.", "exito")
                return redirect(url_for("admin.listar_canchas"))
    valores = request.form if request.method == "POST" else (dict(cancha) if cancha else {})
    if cancha and cancha["foto"] and cancha["foto"] not in fotos:
        fotos.append(cancha["foto"])
    return render_template(
        "admin/editar_cancha.html" if cancha else "admin/canchas.html",
        cancha=cancha,
        valores=valores,
        fotos=fotos,
    )


@admin_bp.route("/canchas/nueva", methods=["GET", "POST"])
@admin_requerido
def nueva_cancha():
    return formulario_cancha()


@admin_bp.route("/canchas/<int:id>/editar", methods=["GET", "POST"])
@admin_requerido
def editar_cancha(id):
    return formulario_cancha(id)


@admin_bp.get("/canchas/listar")
@admin_requerido
def listar_canchas():
    with closing(get_connection()) as conn:
        canchas = conn.execute("SELECT * FROM cancha ORDER BY activa DESC, id").fetchall()
    return render_template("admin/canchas_lista.html", canchas=canchas)


@admin_bp.get("/panel")
@admin_requerido
def panel():
    fecha = request.args.get("fecha", "")
    momento = ahora()
    if not fecha_valida(fecha):
        fecha = momento.date().isoformat()
    with closing(get_connection()) as conn:
        reservas = conn.execute(
            """SELECT r.*, c.nombre AS nombre_cancha, u.nombre AS nombre_usuario,
            COALESCE(NULLIF(r.telefono,''),u.telefono) AS contacto FROM reserva r JOIN cancha c ON c.id=r.id_cancha
            JOIN usuario u ON u.id=r.id_usuario WHERE r.fecha=? ORDER BY r.hora_inicio, c.id""",
            (fecha,),
        ).fetchall()
        bloqueos = conn.execute(
            """SELECT b.*, c.nombre AS nombre_cancha FROM bloqueo b JOIN cancha c ON c.id=b.id_cancha
            WHERE b.fecha=? ORDER BY b.hora_inicio, c.id""",
            (fecha,),
        ).fetchall()
        canchas = conn.execute("SELECT * FROM cancha WHERE activa=1 ORDER BY id").fetchall()
        agenda = agenda_del_dia(conn, fecha)
    return vista_agenda(fecha, canchas, reservas, bloqueos, agenda)


@admin_bp.get("/demo")
def demo():
    # La vista de portfolio usa datos en memoria, independientes de las cuentas del complejo.
    fecha = request.args.get("fecha", "")
    if not fecha_valida(fecha):
        fecha = (ahora().date() + timedelta(days=1)).isoformat()
    canchas = [
        {"id": 1, "nombre": "Fútbol 5"},
        {"id": 2, "nombre": "Fútbol 11"},
        {"id": 3, "nombre": "Futsal"},
    ]
    partidos = [
        (1, "10:00", "Equipo Sur"),
        (2, "17:00", "Los del jueves"),
        (3, "18:00", "Futsal del Parque"),
        (1, "19:00", "Equipo Norte"),
        (2, "20:00", "Unión del Barrio"),
    ]
    reservas = [
        {
            "hora_inicio": h,
            "nombre_cancha": canchas[i - 1]["nombre"],
            "nombre_usuario": n,
            "estado": "confirmada",
        }
        for i, h, n in partidos
    ]
    bloqueos = [
        {
            "hora_inicio": "09:00",
            "hora_fin": "11:00",
            "nombre_cancha": "Futsal",
            "motivo": "Acondicionamiento del piso",
        }
    ]
    agenda = {(i, h): "ocupado" for i, h, _ in partidos}
    agenda.update({(3, "09:00"): "bloqueado", (3, "10:00"): "bloqueado"})
    return vista_agenda(fecha, canchas, reservas, bloqueos, agenda, demo=True)


def vista_agenda(fecha, canchas, reservas, bloqueos, agenda, demo=False):
    momento = ahora()
    turnos = {c["id"]: dict(horarios_cancha(c["id"], fecha, agenda, momento)) for c in canchas}
    libres = sum(list(estados.values()).count("disponible") for estados in turnos.values())
    dia = date.fromisoformat(fecha)
    return render_template(
        "admin/panel.html",
        reservas=reservas,
        bloqueos=bloqueos,
        canchas=canchas,
        fecha=fecha,
        turnos=turnos,
        horas=HORARIOS_POSIBLES,
        libres=libres,
        demo=demo,
        activas=sum(r["estado"] != "cancelada" for r in reservas),
        anterior=(dia - timedelta(days=1)).isoformat() if dia > date.min else None,
        siguiente=(dia + timedelta(days=1)).isoformat() if dia < date.max else None,
    )


@admin_bp.post("/reserva/<int:id>/cancelar")
@admin_requerido
def cancelar_reserva(id):
    with closing(get_connection()) as conn, conn:
        conn.execute("BEGIN IMMEDIATE")
        reserva = conn.execute("SELECT * FROM reserva WHERE id=?", (id,)).fetchone()
        if not reserva:
            abort(404)
        if reserva["estado"] != "cancelada" and not ya_inicio(reserva["fecha"], reserva["hora_inicio"]):
            conn.execute("UPDATE reserva SET estado='cancelada' WHERE id=?", (id,))
            flash("Reserva cancelada.", "exito")
        else:
            flash("Esta reserva ya no admite cancelaciones.", "error")
    return redirect(url_for("admin.panel", fecha=reserva["fecha"]))


@admin_bp.route("/bloqueo/nueva", methods=["GET", "POST"])
@admin_requerido
def nuevo_bloqueo():
    valores = request.form if request.method == "POST" else request.args
    with closing(get_connection()) as conn, conn:
        if request.method == "POST":
            conn.execute("BEGIN IMMEDIATE")
        canchas = conn.execute("SELECT * FROM cancha WHERE activa=1 ORDER BY id").fetchall()
        if request.method == "POST":
            ident = valores.get("id_cancha", type=int)
            fecha, ini, fin = (valores.get(k, "") for k in ("fecha", "hora_ini", "hora_fin"))
            motivo = valores.get("motivo", "").strip()
            patron = r"(?:[01][0-9]|2[0-3]):[0-5][0-9]"
            if ident not in {c["id"] for c in canchas}:
                flash("Elegí una cancha activa.", "error")
            elif (
                not fecha_valida(fecha)
                or not all(re.fullmatch(patron, h) for h in (ini, fin))
                or ini >= fin
            ):
                flash("Revisá la fecha y el intervalo. El fin debe ser posterior al inicio.", "error")
            elif ya_inicio(fecha, fin) or len(motivo) > 200:
                flash("Elegí un intervalo vigente y un motivo de hasta 200 caracteres.", "error")
            elif not any(h < fin and ini < fin_turno(h) for h in HORARIOS_POSIBLES):
                flash("El intervalo debe incluir al menos parte de un turno de juego.", "error")
            else:
                solapado = conn.execute(
                    """SELECT 1 FROM bloqueo WHERE id_cancha=? AND fecha=?
                    AND hora_inicio<? AND hora_fin>?""",
                    (ident, fecha, fin, ini),
                ).fetchone()
                reserva = conn.execute(
                    """SELECT 1 FROM reserva WHERE id_cancha=? AND fecha=? AND estado!='cancelada'
                    AND hora_inicio<? AND substr(time(hora_inicio,'+1 hour'),1,5)>?""",
                    (ident, fecha, fin, ini),
                ).fetchone()
                if solapado or reserva:
                    flash(
                        "Ese intervalo coincide con una reserva o un bloqueo. Revisá la agenda.", "error"
                    )
                else:
                    conn.execute(
                        """INSERT INTO bloqueo(id_cancha,fecha,hora_inicio,hora_fin,motivo,fecha_creacion)
                                    VALUES(?,?,?,?,?,?)""",
                        (ident, fecha, ini, fin, motivo, ahora().date().isoformat()),
                    )
                    flash("Bloqueo guardado en la agenda.", "exito")
                    return redirect(url_for("admin.panel", fecha=fecha))
    return render_template("admin/bloqueo.html", canchas=canchas, valores=valores)


@admin_bp.post("/bloqueo/<int:id>/eliminar")
@admin_requerido
def eliminar_bloqueo(id):
    with closing(get_connection()) as conn, conn:
        conn.execute("BEGIN IMMEDIATE")
        bloqueo = conn.execute("SELECT fecha FROM bloqueo WHERE id=?", (id,)).fetchone()
        if not bloqueo:
            abort(404)
        conn.execute("DELETE FROM bloqueo WHERE id=?", (id,))
    flash("Bloqueo retirado de la agenda.", "exito")
    return redirect(url_for("admin.panel", fecha=bloqueo["fecha"]))


@admin_bp.get("/estadisticas")
@admin_requerido
def estadisticas():
    with closing(get_connection()) as conn:
        ranking = conn.execute("""SELECT c.nombre, COUNT(r.id) AS cantidad, COALESCE(SUM(r.precio_final),0) AS importe
             FROM cancha c LEFT JOIN reserva r ON r.id_cancha=c.id AND r.estado='confirmada'
             GROUP BY c.id ORDER BY cantidad DESC, c.id""").fetchall()
    return render_template(
        "admin/estadisticas.html",
        ranking=ranking,
        total=sum(r["cantidad"] for r in ranking),
        importe=sum(r["importe"] for r in ranking),
    )
