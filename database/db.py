import sqlite3
import os

#Para la direccion (se bugeaba)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, '..', 'canchas.db')

#para obtener conexion
def get_connection():
    conn = sqlite3.connect('canchas.db')
    conn.row_factory = sqlite3.Row
    return conn

#creamos tablas
def crear_tablas():
    conn = get_connection()
    cursor = conn.cursor()

    cursor.executescript('''
        CREATE TABLE IF NOT EXISTS cancha (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre TEXT NOT NULL,
            tipo TEXT NOT NULL,
            piso TEXT NOT NULL,
            techo INTEGER NOT NULL,
            precio REAL NOT NULL,
            foto TEXT,
            activa INTEGER NOT NULL DEFAULT 1
        );

        CREATE TABLE IF NOT EXISTS usuario (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre TEXT NOT NULL,
            email TEXT NOT NULL UNIQUE,
            contrasena TEXT NOT NULL,
            telefono TEXT,
            email_confirmado INTEGER NOT NULL DEFAULT 0,
            activo INTEGER NOT NULL DEFAULT 1
        );

        CREATE TABLE IF NOT EXISTS reserva (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            id_cancha INTEGER NOT NULL,
            id_usuario INTEGER NOT NULL,
            fecha TEXT NOT NULL,
            hora_inicio TEXT NOT NULL,
            cedula TEXT,
            estado TEXT NOT NULL DEFAULT 'pendiente',
            pago_web INTEGER NOT NULL DEFAULT 0,
            descuento REAL NOT NULL DEFAULT 0,
            precio_final REAL,
            fecha_creacion TEXT NOT NULL,
            FOREIGN KEY (id_cancha) REFERENCES cancha(id),
            FOREIGN KEY (id_usuario) REFERENCES usuario(id)
        );

        CREATE TABLE IF NOT EXISTS bloqueo (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            id_cancha INTEGER NOT NULL,
            fecha TEXT NOT NULL,
            hora_inicio TEXT NOT NULL,
            hora_fin TEXT NOT NULL,
            motivo TEXT,
            fecha_creacion TEXT NOT NULL,
            FOREIGN KEY (id_cancha) REFERENCES cancha(id)
        );
    ''')
    
    try:
        cursor.execute('ALTER TABLE usuario ADD COLUMN es_admin INTEGER NOT NULL DEFAULT 0')
    except sqlite3.OperationalError:
        pass

    conn.commit()
    conn.close()