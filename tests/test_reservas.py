"""Pruebas con bases temporales y datos ficticios."""

import os
import sqlite3
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
from datetime import timedelta
from pathlib import Path
from threading import Barrier
from unittest.mock import patch


class FlujosReservas(unittest.TestCase):
    def setUp(self):
        self.carpeta = tempfile.TemporaryDirectory()
        self.addCleanup(self.carpeta.cleanup)
        entorno = patch.dict(os.environ, CANCHAS_DB=str(Path(self.carpeta.name) / "prueba.db"))
        entorno.start()
        self.addCleanup(entorno.stop)
        from app import app
        from database.db import crear_tablas, get_connection
        from logica.horarios import ahora

        crear_tablas()
        self.app, self.conexion = app, get_connection
        self.app.testing = True
        self.cliente = app.test_client()
        self.fecha = (ahora().date() + timedelta(days=3)).isoformat()
        self.turno = {
            "id_cancha": 1,
            "fecha": self.fecha,
            "hora": "17:00",
            "cedula": "12345678",
            "telefono": "098000000",
        }
        self.reserva_url = f"/reserva?id=1&hora=17:00&fecha={self.fecha}"

    def registrar(self, cliente, email, destino=""):
        ruta = "/registro" + destino
        cliente.get(ruta)
        return self.post(
            cliente,
            ruta,
            {
                "nombre": "Jugador de prueba",
                "email": email,
                "telefono": "099000000",
                "contraseña": "clave de ejemplo",
            },
        )

    def post(self, cliente, ruta, datos):
        cliente.get("/login")
        with cliente.session_transaction() as ses:
            token = ses["csrf"]
        return cliente.post(ruta, data={**datos, "csrf": token})

    def administrador(self):
        self.registrar(self.cliente, "admin@example.test")
        with closing(self.conexion()) as conn, conn:
            conn.execute("UPDATE usuario SET es_admin=1 WHERE email='admin@example.test'")
        return self.cliente

    def test_registro_conserva_turno_y_descuento(self):
        acceso = self.cliente.get(self.reserva_url)
        self.assertIn("/login?", acceso.location)
        creado = self.registrar(
            self.cliente, "equipo@example.test", "?" + acceso.location.split("?", 1)[1]
        )
        self.assertIn("/reserva?", creado.location)
        self.assertEqual(self.cliente.get(creado.location).status_code, 200)
        self.assertTrue(
            self.post(self.cliente, "/reserva", {**self.turno, "pago_web": "on"}).location.endswith(
                "/perfil"
            )
        )
        with closing(self.conexion()) as conn:
            r = conn.execute("SELECT telefono,precio_final FROM reserva").fetchone()
        self.assertEqual(tuple(r), ("098000000", 1140))
        self.assertIn("Próximos partidos", self.cliente.get("/perfil").get_data(as_text=True))

    def test_dos_jugadores_un_turno(self):
        jugadores = [self.app.test_client() for _ in range(2)]
        for i, jugador in enumerate(jugadores):
            self.registrar(jugador, f"jugador{i}@example.test")
        barrera = Barrier(2)

        def confirmar(jugador):
            barrera.wait(timeout=10)
            return self.post(jugador, "/reserva", self.turno).location.split("?")[0]

        with ThreadPoolExecutor(max_workers=2) as pool:
            destinos = list(pool.map(confirmar, jugadores))
        self.assertCountEqual(destinos, ["/perfil", "/cancha/1"])
        with closing(self.conexion()) as conn:
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM reserva").fetchone()[0], 1)

    def test_cancelacion_y_bloqueo_parcial(self):
        admin = self.administrador()
        jugador = self.app.test_client()
        self.registrar(jugador, "jugador@example.test")
        self.post(jugador, "/reserva", self.turno)
        bloqueo = {
            "id_cancha": 1,
            "fecha": self.fecha,
            "hora_ini": "17:30",
            "hora_fin": "18:15",
            "motivo": "Mantenimiento",
        }
        self.assertEqual(self.post(admin, "/admin/bloqueo/nueva", bloqueo).status_code, 200)
        with closing(self.conexion()) as conn:
            ident = conn.execute("SELECT id FROM reserva").fetchone()[0]
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM bloqueo").fetchone()[0], 0)
        self.post(jugador, f"/perfil/reserva/{ident}/cancelar", {})
        guardado = self.post(admin, "/admin/bloqueo/nueva", bloqueo)
        self.assertIn(self.fecha, guardado.location)
        from logica.horarios import obtener_horarios

        estados = dict(obtener_horarios(1, self.fecha))
        self.assertEqual(
            [estados[h] for h in ("17:00", "18:00", "19:00")], ["bloqueado", "bloqueado", "disponible"]
        )
        with closing(self.conexion()) as conn:
            ident = conn.execute("SELECT id FROM bloqueo").fetchone()[0]
        self.post(admin, f"/admin/bloqueo/{ident}/eliminar", {})
        self.assertEqual(dict(obtener_horarios(1, self.fecha))["17:00"], "disponible")

    def test_administracion_y_demo(self):
        antes = self.cliente.get("/admin/demo").get_data(as_text=True)
        self.assertIn("Equipo Sur", antes)
        self.assertNotIn("Confirmar cancelación", antes)
        admin = self.administrador()
        for ruta in (
            "/admin/panel",
            "/admin/canchas/listar",
            "/admin/estadisticas",
            "/admin/canchas/1/editar",
            "/admin/bloqueo/nueva",
        ):
            self.assertEqual(admin.get(ruta).status_code, 200)
        datos = {
            "nombre": "Cancha auxiliar",
            "tipo": "Fut 5",
            "piso": "natural",
            "precio": "950.50",
            "foto": "",
        }
        self.post(admin, "/admin/canchas/nueva", datos)
        with closing(self.conexion()) as conn:
            ident = conn.execute("SELECT id FROM cancha WHERE nombre=?", (datos["nombre"],)).fetchone()[
                0
            ]
        self.post(admin, f"/admin/canchas/{ident}/editar", datos)
        self.assertEqual(admin.get(f"/cancha/{ident}").status_code, 404)
        jugador = self.app.test_client()
        self.registrar(jugador, "otra@example.test")
        self.assertEqual(jugador.get("/admin/panel").status_code, 403)

    def test_cancelar_desde_agenda_conserva_el_dia(self):
        admin = self.administrador()
        jugador = self.app.test_client()
        self.registrar(jugador, "delantero@example.test")
        self.post(jugador, "/reserva", self.turno)
        with closing(self.conexion()) as conn:
            ident = conn.execute("SELECT id FROM reserva").fetchone()[0]
        panel = admin.get("/admin/panel", query_string={"fecha": self.fecha}).get_data(as_text=True)
        self.assertIn(self.turno["telefono"], panel)
        self.assertIn(self.fecha, self.post(admin, f"/admin/reserva/{ident}/cancelar", {}).location)
        self.assertIn("Cancelada", jugador.get("/perfil").get_data(as_text=True))

    def test_fechas_y_contacto_invalidos(self):
        self.registrar(self.cliente, "portero@example.test")
        for datos in (
            {"fecha": "2000-01-01"},
            {"fecha": "mañana"},
            {"hora": "03:37"},
            {"telefono": "x"},
        ):
            self.post(self.cliente, "/reserva", {**self.turno, **datos})
        with closing(self.conexion()) as conn:
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM reserva").fetchone()[0], 0)

    def test_migracion_idempotente(self):
        from database.db import crear_tablas

        ruta = Path(self.carpeta.name) / "anterior.db"
        with closing(sqlite3.connect(ruta)) as conn, conn:
            conn.executescript("""CREATE TABLE cancha (id INTEGER PRIMARY KEY, nombre TEXT);
                INSERT INTO cancha VALUES(7,'Cancha anterior');
                CREATE TABLE usuario (id INTEGER PRIMARY KEY);
                CREATE TABLE reserva(id INTEGER PRIMARY KEY,fecha TEXT,id_cancha INTEGER,hora_inicio TEXT);
                INSERT INTO reserva VALUES(3,'2025-04-18',7,'19:00');""")
        with patch.dict(os.environ, CANCHAS_DB=str(ruta)):
            crear_tablas()
            crear_tablas()
            with closing(self.conexion()) as conn:
                self.assertEqual(
                    tuple(conn.execute("SELECT id,telefono FROM reserva").fetchone()), (3, None)
                )
                self.assertEqual(conn.execute("SELECT COUNT(*) FROM cancha").fetchone()[0], 1)


if __name__ == "__main__":
    unittest.main()
