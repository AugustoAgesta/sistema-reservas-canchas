from contextlib import closing
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from database.db import get_connection

try:
    ZONA = ZoneInfo("America/Montevideo")
except ZoneInfoNotFoundError:
    ZONA = timezone(timedelta(hours=-3))

HORARIOS_POSIBLES = ("09:00", "10:00", "11:00", "17:00", "18:00", "19:00", "20:00", "21:00", "22:00")


def ahora():
    return datetime.now(ZONA)


def fecha_valida(valor):
    try:
        return date.fromisoformat(valor).isoformat() == valor
    except (TypeError, ValueError):
        return False


def fin_turno(hora):
    return f"{int(hora[:2]) + 1:02d}:00"


def ya_inicio(fecha, hora, momento=None):
    momento = momento or ahora()
    return (fecha, hora) <= (momento.date().isoformat(), momento.strftime("%H:%M"))


def agenda_del_dia(conn, fecha):
    reservas = conn.execute(
        "SELECT id_cancha, hora_inicio FROM reserva WHERE fecha=? AND estado!='cancelada'", (fecha,)
    )
    ocupados = {(r["id_cancha"], r["hora_inicio"]): "ocupado" for r in reservas}
    bloqueos = conn.execute(
        "SELECT id_cancha, hora_inicio, hora_fin FROM bloqueo WHERE fecha=?", (fecha,)
    )
    for b in bloqueos:
        for hora in HORARIOS_POSIBLES:
            if hora < b["hora_fin"] and b["hora_inicio"] < fin_turno(hora):
                ocupados.setdefault((b["id_cancha"], hora), "bloqueado")
    return ocupados


def horarios_cancha(id_cancha, fecha, agenda, momento):
    return [
        (
            hora,
            agenda.get((id_cancha, hora), "pasado" if ya_inicio(fecha, hora, momento) else "disponible"),
        )
        for hora in HORARIOS_POSIBLES
    ]


def obtener_horarios(id_cancha, fecha, conn=None):
    if conn is None:
        with closing(get_connection()) as conexion:
            return obtener_horarios(id_cancha, fecha, conexion)
    return horarios_cancha(id_cancha, fecha, agenda_del_dia(conn, fecha), ahora())
