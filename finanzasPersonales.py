from flask import Flask, render_template, request, jsonify
from datetime import datetime

app = Flask(__name__)

@app.route('/')
def home():
    return render_template('index.html')

# Esta es la nueva ruta que recibe la información del JS
@app.route('/registrar_gasto', methods=['POST'])
def registrar_gasto():
    datos = request.get_json()
    concepto = datos.get('concepto')
    monto = datos.get('monto')
    fecha_actual = datetime.now().strftime("%d/%m/%Y %H:%M")

    # POR AHORA: Solo lo imprimimos. Esto se verá en los Logs de Render.
    # EN EL PRÓXIMO PASO: Aquí enviaremos los datos a Google Sheets.
    print(f"💰 NUEVO GASTO | Fecha: {fecha_actual} | Concepto: {concepto} | Monto: ${monto}")

    return jsonify({"status": "success", "message": "Gasto registrado"})

if __name__ == '__main__':
    app.run(debug=True)