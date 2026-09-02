from flask import Blueprint, render_template, request, redirect, url_for
from database.db import get_connection
from datetime import date
from utils.auth import admin_requerido

admin_bp = Blueprint('admin', __name__, url_prefix='/admin')

@admin_bp.route('/canchas/nueva', methods=['GET', 'POST'])
@admin_requerido
#GET es para ver, POST para agregar
def nueva_cancha():
    if request.method == 'POST': #Si se enviaron datos, se procesa el formulario
        nombre = request.form['nombre'] #lee lo que se escribio en el campo nombre
        tipo = request.form['tipo']
        piso = request.form['piso']
        techo = 1 if request.form.get('techo') == 'on' else 0 #los checkbox en HTML mandan on
        precio = request.form['precio']
        foto = request.form.get('foto', '')
        
        conn = get_connection()
        conn.execute(
            'INSERT INTO cancha (nombre, tipo, piso, techo, precio, foto) VALUES (?, ?, ?, ?, ?, ?)',
            (nombre, tipo, piso, techo, precio, foto)
        )
        conn.commit()
        conn.close()

        return redirect(url_for('cliente.index')) #guarda y nos manda a la pagina principal.

    return render_template('admin/canchas.html')

@admin_bp.route('/canchas/<int:id>/editar', methods=['GET', 'POST'])
@admin_requerido
def editar_cancha(id):
    conn = get_connection()
    cancha = conn.execute('SELECT * FROM cancha WHERE id = ?', (id,)).fetchone()
    
    if request.method == 'POST':
        nombre = request.form['nombre']
        tipo = request.form['tipo']
        piso = request.form['piso']
        techo = 1 if request.form.get('techo') == 'on' else 0
        precio = request.form['precio']
        activa = 1 if request.form.get('activa') == 'on' else 0
        foto = request.form.get('foto', '')
        
        conn.execute(
            'UPDATE cancha SET nombre = ?, tipo = ?, piso = ?, techo = ?, precio = ?, activa = ?, foto = ? WHERE id = ?',
            (nombre, tipo, piso, techo, precio, activa, foto, id)
        )
        conn.commit()
        conn.close()
        return redirect(url_for('admin.listar_canchas'))
    
    conn.close()
    return render_template('admin/editar_cancha.html', cancha=cancha)

@admin_bp.route('/canchas/listar', methods=['GET'])
@admin_requerido
def listar_canchas():
    conn = get_connection()
    canchas = conn.execute('SELECT * FROM cancha').fetchall()
    conn.close()
    return render_template('admin/canchas_lista.html', canchas=canchas)
  
    
@admin_bp.route('/panel')
@admin_requerido
def panel():
    fecha = request.args.get('fecha')
    if fecha is None:
        fecha = date.today().isoformat()
    
    conn = get_connection()
    reservas = conn.execute(
        '''
        SELECT reserva.*, cancha.nombre AS nombre_cancha, usuario.nombre AS nombre_usuario
        FROM reserva
        JOIN cancha ON reserva.id_cancha = cancha.id
        JOIN usuario ON reserva.id_usuario = usuario.id
        WHERE reserva.fecha = ?
        ORDER BY reserva.hora_inicio
        ''',(fecha,)).fetchall()
    
    bloqueos = conn.execute('''
        SELECT bloqueo.*, cancha.nombre AS nombre_cancha
        FROM bloqueo
        JOIN cancha ON bloqueo.id_cancha = cancha.id
        WHERE bloqueo.fecha = ?
        ORDER BY bloqueo.hora_inicio
        ''', (fecha,)).fetchall()
    
    fechas_reservas = conn.execute('''
        SELECT fecha FROM reserva
        UNION
        SELECT fecha FROM bloqueo
        ORDER BY fecha
        ''').fetchall()
    conn.close()
    
    hoy = date.today().isoformat()
    
    return render_template('admin/panel.html', reservas=reservas, fecha=fecha, fechas_reservas=fechas_reservas, hoy=hoy, bloqueos=bloqueos)

@admin_bp.route('/reserva/<int:id>/cancelar', methods=['POST'])
@admin_requerido
def cancelar_reserva(id):
    conn = get_connection()
    conn.execute('UPDATE reserva SET estado = ? WHERE id = ?', ('cancelada', id))
    conn.commit()
    conn.close()
    return redirect(url_for('admin.panel'))

@admin_bp.route('/bloqueo/nueva', methods=['GET', 'POST'])
@admin_requerido
def nuevo_bloqueo():
    if request.method == 'POST': #Si se enviaron datos, se procesa el formulario
            id_cancha = request.form['id_cancha'] #lee lo que se escribio en el campo nombre
            fecha = request.form['fecha']
            hora_ini = request.form['hora_ini']
            hora_fin = request.form['hora_fin']
            motivo = request.form['motivo']
    
            conn = get_connection()
            conn.execute(
                'INSERT INTO bloqueo (id_cancha, fecha, hora_inicio, hora_fin, motivo, fecha_creacion) VALUES (?, ?, ?, ?, ?, ?)',
                (id_cancha, fecha, hora_ini, hora_fin, motivo, date.today().isoformat())
            )
            conn.commit()
            conn.close()
    
            return redirect(url_for('cliente.index')) #guarda y nos manda a la pagina principal.
    
    conn = get_connection()
    canchas = conn.execute('SELECT * FROM cancha WHERE activa = 1').fetchall()
    conn.close()
    return render_template('admin/bloqueo.html', canchas=canchas)

@admin_bp.route('/estadisticas')
@admin_requerido
def estadisticas():
    conn = get_connection()
    
    total_reservas = conn.execute('SELECT COUNT(*) AS total FROM reserva WHERE estado = ?', ('confirmada',)).fetchone()
    
    mas_reservada = conn.execute('''SELECT cancha.nombre, COUNT(*) AS total 
                                 FROM reserva 
                                 JOIN cancha ON reserva.id_cancha = cancha.id 
                                 WHERE reserva.estado = 'confirmada' 
                                 GROUP BY cancha.nombre 
                                 ORDER BY total DESC 
                                 LIMIT 1''').fetchone()
    
    ingresos_totales = conn.execute('''SELECT SUM(precio_final) AS total FROM reserva WHERE estado = 'confirmada' ''').fetchone()
    conn.close()
    
    total_reservas = total_reservas['total']
    ingresos_totales = ingresos_totales['total']
    
    if ingresos_totales is None:
        ingresos_totales = 0
    
    return render_template('admin/estadisticas.html', total_reservas=total_reservas, mas_reservada=mas_reservada, ingresos_totales=ingresos_totales)
    

@admin_bp.route('/bloqueo/<int:id>/eliminar', methods=['POST'])
@admin_requerido
def eliminar_bloqueo(id):
    conn = get_connection()
    conn.execute('DELETE FROM bloqueo WHERE id = ?', (id,))
    conn.commit()
    conn.close()
    return redirect(url_for('admin.panel'))
