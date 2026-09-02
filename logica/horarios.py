from database.db import get_connection
from datetime import datetime 

HORARIOS_POSIBLES = ["09:00", "10:00", "11:00", "17:00", 
                     "18:00", "19:00", "20:00", "21:00", 
                    "22:00"]

def obtener_horarios(id_cancha, fecha):
    conn = get_connection()
    
    reservas = conn.execute(
        'SELECT hora_inicio FROM reserva WHERE id_cancha = ? AND fecha = ? AND estado != "cancelada"',
        (id_cancha, fecha)
    ).fetchall()
    
    bloqueos = conn.execute(
        'SELECT hora_inicio, hora_fin FROM bloqueo WHERE id_cancha = ?  AND fecha = ?',
        (id_cancha, fecha)
    ).fetchall() 
    
    horas_ocupadas = []
    for r in reservas:
        horas_ocupadas.append(r['hora_inicio'])
        
    for b in bloqueos:
        for hora in HORARIOS_POSIBLES:
            if hora >= b['hora_inicio'] and hora < b['hora_fin']:
                horas_ocupadas.append(hora)    
    
    hoy = datetime.today().isoformat()[:10]
    horaActual = datetime.now().strftime("%H:%M")

    resultado = []
    for h in HORARIOS_POSIBLES:
        if h in horas_ocupadas:
            resultado.append((h, "ocupado")) 
        elif fecha == hoy and h < horaActual:
            resultado.append((h, "pasado"))
        else:  
            resultado.append((h, "disponible")) 
    
    conn.close()
    return resultado

#test
if __name__ == '__main__':
    print(obtener_horarios(1, "2026-07-25"))