from flask import Flask, render_template, request, jsonify
from datetime import datetime
import os
import json
import traceback
import gspread

app = Flask(__name__)

MESES = {
    1: "ENERO", 2: "FEBRERO", 3: "MARZO", 4: "ABRIL",
    5: "MAYO", 6: "JUNIO", 7: "JULIO", 8: "AGOSTO",
    9: "SEPTIEMBRE", 10: "OCTUBRE", 11: "NOVIEMBRE", 12: "DICIEMBRE"
}

def conectar_google_sheets():
    json_env = os.environ.get('GOOGLE_CREDS_JSON')
    if json_env:
        info_creds = json.loads(json_env)
        cliente = gspread.service_account_from_dict(info_creds)
    else:
        ruta_creds = '/etc/secrets/credenciales.json' if os.path.exists('/etc/secrets/credenciales.json') else 'credenciales.json'
        cliente = gspread.service_account(filename=ruta_creds)

    SPREADSHEET_ID = "1OZy55rSg_6Z0nu-MpCXfTofIfa_ekcDWdywDVj1wlfA"
    return cliente.open_by_key(SPREADSHEET_ID)

def detectar_categoria(hoja_cat, concepto_ingresado):
    try:
        registros = hoja_cat.get_all_records()
        concepto_lower = concepto_ingresado.lower().strip()
        
        for fila in registros:
            palabra_clave = str(fila.get('Palabra Clave', '')).lower().strip()
            if palabra_clave and palabra_clave in concepto_lower:
                return fila.get('Categoria', 'Varios'), fila.get('Tipo', 'Pasivo')
    except Exception as e:
        print(f"Aviso detectando categoría: {e}")
        
    return None, None

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/registrar_gasto', methods=['POST'])
def registrar_gasto():
    datos = request.get_json()
    concepto = datos.get('concepto', '').strip()
    monto = float(datos.get('monto', 0))
    tipo_ingresado = datos.get('tipo', 'Pasivo') # 'Activo' (Ingreso) o 'Pasivo' (Gasto)
    nueva_categoria = datos.get('nueva_categoria')

    ahora = datetime.now()
    fecha_hoy = me = ahora.strftime("%d/%m/%Y")
    hora_actual = me = me = ahora.strftime("%H:%M")
    nombre_mes = MESES[ahora.month]

    try:
        doc = conectar_google_sheets()
        hoja_transacciones = doc.worksheet("Transacciones")
        hoja_categorias = doc.worksheet("Categorias")

        if nueva_categoria:
            categoria = nueva_categoria
            tipo = tipo_ingresado
            # Guardar la regla para futuras consultas
            hoja_categorias.append_row([concepto.lower(), categoria, tipo])
        else:
            categoria, tipo = detectar_categoria(hoja_categorias, concepto)
            if not tipo: 
                tipo = tipo_ingresado

            if not categoria:
                cat_records = hoja_categorias.col_values(2)[1:]
                categorias_unicas = sorted(list(set([c for c in cat_records if c.strip()])))
                
                # Opciones por defecto si la hoja está vacía
                if not categorias_unicas:
                    categorias_unicas = ["Sueldo", "Alimentación", "Servicios", "Transporte", "Venta", "Varios"]
                
                return jsonify({
                    "status": "needs_category",
                    "categorias": categorias_unicas
                })

        # Guardar en Transacciones (7 columnas)
        hoja_transacciones.append_row([fecha_hoy, hora_actual, concepto, monto, categoria, nombre_mes, tipo])

        return jsonify({
            "status": "success",
            "message": "Movimiento registrado correctamente",
            "categoria": categoria,
            "tipo": tipo
        })

    except Exception as e:
        traceback.print_exc()
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/obtener_metricas', methods=['GET'])
def obtener_metricas():
    try:
        doc = conectar_google_sheets()
        hoja_transacciones = doc.worksheet("Transacciones")
        registros = hoja_transacciones.get_all_records()

        total_ingresos = 0.0
        total_gastos = 0.0

        for r in registros:
            monto = float(r.get('Monto', 0) or 0)
            tipo = str(r.get('Tipo', '')).strip().capitalize()

            if tipo == 'Activo':
                total_ingresos += monto
            else:
                total_gastos += monto

        balance_real = total_ingresos - total_gastos

        return jsonify({
            "status": "success",
            "ingresos": f"${total_ingresos:,.0f}",
            "gastos": f"${total_gastos:,.0f}",
            "balance": f"${balance_real:,.0f}"
        })
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True)