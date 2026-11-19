from datetime import date
from pathlib import Path

from flask import current_app, url_for

TIPOS = {"Fut 5": "Fútbol 5", "Fut 11": "Fútbol 11", "Futsal": "Futsal"}
PISOS = {"sintetico": "Césped sintético", "natural": "Césped natural", "madera": "Madera"}
FOTOS = {
    "Fut 5": "Fut 5, pasto sintético, con techo.jpg",
    "Fut 11": "Fut 11, pasto natural, sin techo.jpg",
    "Futsal": "Futsal, piso de madera, con techo.jpg",
}
OPTIMIZADAS = dict(zip(FOTOS.values(), ("futbol-5.webp", "futbol-11.webp", "futsal.webp")))
NOMBRES_ORIGINALES = {
    "Fut 5 - Sintec. - Con techo": "Fútbol 5",
    "Fut 11 - Natural - s/techo": "Fútbol 11",
    "Futsal - Madera - Con techo": "Futsal",
}
DIAS = ("lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo")
MESES = (
    "enero",
    "febrero",
    "marzo",
    "abril",
    "mayo",
    "junio",
    "julio",
    "agosto",
    "septiembre",
    "octubre",
    "noviembre",
    "diciembre",
)


def moneda(valor):
    if valor is None:
        return "Sin importe"
    return "$ " + f"{valor:,.2f}".removesuffix(".00").translate(str.maketrans(",.", ".,"))


def fecha_texto(valor):
    dia = date.fromisoformat(valor)
    return f"{DIAS[dia.weekday()]} {dia.day} de {MESES[dia.month - 1]} de {dia.year}"


def imagen_cancha(cancha):
    directorio = Path(current_app.static_folder) / "img"
    foto = cancha["foto"] or ""
    if Path(foto).name != foto or not (directorio / foto).is_file():
        foto = FOTOS.get(cancha["tipo"], FOTOS["Fut 5"])
    optimizada = OPTIMIZADAS.get(foto)
    if optimizada and (directorio / optimizada).is_file():
        foto = optimizada
    return url_for("static", filename="img/" + foto)
