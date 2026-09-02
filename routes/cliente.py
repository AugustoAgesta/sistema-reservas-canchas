from flask import Blueprint, render_template, request, redirect, url_for, session, flash
from database.db import get_connection
from logica.horarios import obtener_horarios, HORARIOS_POSIBLES
from datetime import date
from werkzeug.security import generate_password_hash, check_password_hash
from utils.auth import login_requerido
import re
import sqlite3

#Blueprint: forma de organizar rutas en archivos separados
cliente_bp = Blueprint('cliente', __name__)

@cliente_bp.route('/')
def index():
    conn = get_connection()
    canchas = conn.execute('SELECT * FROM cancha WHERE activa = 1').fetchall()
    #trae todas las canchas activas
    conn.close()
    return render_template('index.html', canchas=canchas)
    #renderiza el html en index.html y le pasa canchas.

@cliente_bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        contrasena = request.form['contrasena']

        conn = get_connection()
        usuario = conn.execute('SELECT * FROM usuario WHERE email = ?', (email,)).fetchone()
        conn.close()

        if usuario and check_password_hash(usuario['contrasena'], contrasena):
            session['id_usuario'] = usuario['id']
            session['es_admin'] = usuario['es_admin']
            
            if usuario['es_admin']:
                return redirect(url_for('admin.panel'))
            else:
                return redirect(url_for('cliente.index'))
            
        else:
            return render_template('login.html', error='Email o contraseña incorrectos')

    return render_template('login.html')

@cliente_bp.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('cliente.index'))

@cliente_bp.route('/cancha/<int:id>') #int id pasa el numero de URL para tomarlo como numero de cancha.
def detalle_cancha(id):
    conn = get_connection()
    cancha = conn.execute('SELECT * FROM cancha WHERE id = ?', (id,)).fetchone()
    conn.close()
    
    fecha = request.args.get('fecha')
    
    #print("FECHA RECIBIDA DE LA URL:", fecha) 
    
    if fecha is None:
        fecha = date.today().isoformat()
        
    hoy = date.today().isoformat()

    horarios = obtener_horarios(id, fecha)
    
    return render_template('cancha.html', cancha=cancha, fecha=fecha, horarios=horarios, hoy=hoy)

@cliente_bp.route('/reserva', methods=['GET', 'POST'])
def confirmar_reserva():
    if request.method == 'POST':
        
        if session.get('id_usuario') is None:
            return redirect(url_for('cliente.login'))
        
        id_cancha = request.form['id_cancha']
        fecha = request.form['fecha']
        hora = request.form['hora']
        
        if hora not in HORARIOS_POSIBLES:
            flash('Horario inválido.', 'error')
            return redirect(url_for('cliente.index'))

        cedula = request.form['cedula']
        telefono = request.form['telefono']
        pago_web = 1 if request.form.get('pago_web') == 'on' else 0
        idUsuario = session.get('id_usuario')
        
        conn = get_connection()
        cancha = conn.execute('SELECT * FROM cancha WHERE id = ?', (id_cancha,)).fetchone()

        descuento = 0.05 if pago_web else 0
        precio_final = cancha['precio'] * (1 - descuento)

        conn.execute(
        'INSERT INTO reserva (id_cancha, id_usuario, fecha, hora_inicio, cedula, estado, pago_web, descuento, precio_final, fecha_creacion) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)',
        (id_cancha, idUsuario, fecha, hora, cedula, 'confirmada', pago_web, descuento, precio_final, date.today().isoformat())
        )
        conn.commit()
        conn.close() 
        
        flash('¡Reserva confirmada con éxito!', 'exito')
        return redirect(url_for('cliente.index'))

    id = request.args.get('id')
    fecha = request.args.get('fecha')
    hora = request.args.get('hora')
    
    conn = get_connection()
    cancha = conn.execute('SELECT * FROM cancha WHERE id = ?', (id,)).fetchone()
    conn.close()
    
    return render_template('reserva.html', cancha=cancha, fecha=fecha, hora=hora)

@cliente_bp.route('/registro', methods=['GET', 'POST'])
def registro():
    if request.method == 'POST':
        nombre = request.form['nombre']
        email = request.form['email']
        contraseña = request.form['contraseña']
        telefono = request.form['telefono']
        
        patron_email = r'^[\w\.-]+@[\w\.-]+\.\w+$'

        if not re.match(patron_email, email):
            flash('El email ingresado no es válido.', 'error')
            return render_template('registro.html')
            
        if len(contraseña) < 8:
            flash('La contraseña debe tener al menos 8 caracteres.', 'error')
            return render_template('registro.html')

        hashpsw = generate_password_hash(contraseña)
        
        conn = get_connection()
        try:
            cursor = conn.execute(
                'INSERT INTO usuario (nombre, email, contrasena, telefono, email_confirmado, activo) VALUES(?,?,?,?,?,?)',
                (nombre, email, hashpsw, telefono, 0, 1)
            )
            
            conn.commit()
            conn.close() 
            
            session['id_usuario'] = cursor.lastrowid
            session['es_admin'] = 0

            flash('¡Cuenta creada con éxito!', 'exito')
            
            return redirect(url_for('cliente.index'))
        
        except sqlite3.IntegrityError:
            conn.close()
            flash('Ese email ya está registrado.', 'error')
            return render_template('registro.html')
    
    return render_template('registro.html')

@cliente_bp.route('/perfil')
@login_requerido
def perfil():
    id_usuario = session.get('id_usuario')
    
    conn = get_connection()
    reservas = conn.execute(
        '''
        SELECT reserva.*, cancha.nombre AS nombre_cancha
        FROM reserva
        JOIN cancha ON reserva.id_cancha = cancha.id
        WHERE reserva.id_usuario = ? 
        ORDER BY reserva.fecha DESC
        ''',(id_usuario,)).fetchall()
    
    conn.close()
    
    hoy = date.today().isoformat()
    return render_template('perfil.html', reservas=reservas, hoy=hoy)
