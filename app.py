#Probamos que el server funcione
from flask import Flask, session, render_template
from dotenv import load_dotenv
import os
from database.db import crear_tablas, get_connection
from routes.cliente import cliente_bp
from routes.admin import admin_bp

load_dotenv()

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY')

@app.context_processor
def usuario_actual():
    id_usuario = session.get('id_usuario')
    usuario = None

    if id_usuario:
        conn = get_connection()
        usuario = conn.execute('SELECT * FROM usuario WHERE id = ?', (id_usuario,)).fetchone()
        conn.close()

    return dict(usuario_sesion=usuario)

with app.app_context():
    crear_tablas()

app.register_blueprint(cliente_bp) #conecta rutas de cliente con app
app.register_blueprint(admin_bp) #admin

@app.errorhandler(404)
def pagina_no_encontrada(error):
    return render_template('404.html'), 404

if __name__ == '__main__':
    app.run(debug=True)

