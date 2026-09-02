from functools import wraps
from flask import session, redirect, url_for

def admin_requerido(f):
    @wraps(f)
    def funcion_envuelta(*args, **kwargs):
        if not session.get('es_admin'):
            return redirect(url_for('cliente.login'))
        return f(*args, **kwargs)
    return funcion_envuelta

#Control de seguridad

def login_requerido(f):
    @wraps(f)
    def funcion_envuelta(*args, **kwargs):
        if not session.get('id_usuario'):
            return redirect(url_for('cliente.login'))
        return f(*args, **kwargs)
    return funcion_envuelta