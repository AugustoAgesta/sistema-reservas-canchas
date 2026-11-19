import os
import sqlite3
from contextlib import closing
from pathlib import Path

DB_PATH = Path(__file__).resolve().parents[1] / "canchas.db"


def get_connection():
    conn = sqlite3.connect(os.environ.get("CANCHAS_DB") or DB_PATH, timeout=12)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def crear_tablas():
    with closing(get_connection()) as conn, conn:
        conn.execute("BEGIN IMMEDIATE")
        nueva = not conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='cancha'"
        ).fetchone()
        conn.execute("""CREATE TABLE IF NOT EXISTS cancha (
            id INTEGER PRIMARY KEY AUTOINCREMENT, nombre TEXT NOT NULL, tipo TEXT NOT NULL,
            piso TEXT NOT NULL, techo INTEGER NOT NULL, precio REAL NOT NULL, foto TEXT,
            activa INTEGER NOT NULL DEFAULT 1)""")
        conn.execute("""CREATE TABLE IF NOT EXISTS usuario (
            id INTEGER PRIMARY KEY AUTOINCREMENT, nombre TEXT NOT NULL, email TEXT NOT NULL UNIQUE,
            contrasena TEXT NOT NULL, telefono TEXT, email_confirmado INTEGER NOT NULL DEFAULT 0,
            activo INTEGER NOT NULL DEFAULT 1, es_admin INTEGER NOT NULL DEFAULT 0)""")
        conn.execute("""CREATE TABLE IF NOT EXISTS reserva (
            id INTEGER PRIMARY KEY AUTOINCREMENT, id_cancha INTEGER NOT NULL REFERENCES cancha(id),
            id_usuario INTEGER NOT NULL REFERENCES usuario(id), fecha TEXT NOT NULL, hora_inicio TEXT NOT NULL,
            cedula TEXT, telefono TEXT, estado TEXT NOT NULL DEFAULT 'pendiente',
            pago_web INTEGER NOT NULL DEFAULT 0, descuento REAL NOT NULL DEFAULT 0,
            precio_final REAL, fecha_creacion TEXT NOT NULL)""")
        conn.execute("""CREATE TABLE IF NOT EXISTS bloqueo (
            id INTEGER PRIMARY KEY AUTOINCREMENT, id_cancha INTEGER NOT NULL REFERENCES cancha(id),
            fecha TEXT NOT NULL, hora_inicio TEXT NOT NULL, hora_fin TEXT NOT NULL,
            motivo TEXT, fecha_creacion TEXT NOT NULL)""")
        if "es_admin" not in {r["name"] for r in conn.execute("PRAGMA table_info(usuario)")}:
            conn.execute("ALTER TABLE usuario ADD COLUMN es_admin INTEGER NOT NULL DEFAULT 0")
        if "telefono" not in {r["name"] for r in conn.execute("PRAGMA table_info(reserva)")}:
            conn.execute("ALTER TABLE reserva ADD COLUMN telefono TEXT")
        conn.execute("CREATE INDEX IF NOT EXISTS reserva_turno ON reserva(fecha,id_cancha,hora_inicio)")
        conn.execute("CREATE INDEX IF NOT EXISTS bloqueo_turno ON bloqueo(fecha,id_cancha)")
        if nueva:
            conn.executemany(
                "INSERT INTO cancha(nombre,tipo,piso,techo,precio,foto) VALUES(?,?,?,?,?,?)",
                [
                    ("Fútbol 5", "Fut 5", "sintetico", 1, 1200, "Fut 5, pasto sintético, con techo.jpg"),
                    ("Fútbol 11", "Fut 11", "natural", 0, 1000, "Fut 11, pasto natural, sin techo.jpg"),
                    ("Futsal", "Futsal", "madera", 1, 1500, "Futsal, piso de madera, con techo.jpg"),
                ],
            )
