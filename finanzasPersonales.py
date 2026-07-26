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
    # 1. Si existe variable de entorno en Render
    json_env = os.environ.get('GOOGLE_CREDS_JSON')
    
    if json_env:
        info_creds = json.loads(json_env)
        cliente = gspread.service_account_from_dict(info_creds)
    else:
        # 2. Si existe el Secret File en Render o local
        ruta_creds = '/etc/secrets/credenciales.json' if os.path.exists('/etc/secrets/credenciales.json') else 'credenciales.json'
        cliente = gspread.service_account(filename=ruta_creds)

    # ID real de tu planilla extraído de tu URL
    SPREADSHEET_ID = "1OZy55rSg_6Z0nu-MpCXfTofIfa_ekcDWdywDVj1wlfA"
    
    spreadsheet = cliente.open_by_key(SPREADSHEET_ID)
    return spreadsheet
    
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
        
    return "Varios", "Pasivo"

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/registrar_gasto', methods=['POST'])
def registrar_gasto():
    datos = request.get_json()
    concepto = datos.get('concepto', '').strip()
    monto = float(datos.get('monto', 0))

    ahora = datetime.now()
    fecha_hoy = ahora.strftime("%d/%m/%Y")
    hora_actual = ahora.strftime("%H:%M")
    nombre_mes = MESES[ahora.month]

    try:
        doc = conectar_google_sheets()
        hoja_transacciones = doc.worksheet("Transacciones")
        hoja_categorias = doc.worksheet("Categorias")
        hoja_resumen = doc.worksheet("Resumen")

        # 1. Categorización automática
        categoria, tipo = detectar_categoria(hoja_categorias, concepto)

        # 2. Guardar en Transacciones
        hoja_transacciones.append_row([fecha_hoy, hora_actual, concepto, monto, categoria, nombre_mes])

        # 3. Actualizar Resumen (si el concepto coincide)
        try:
            conceptos_resumen = hoja_resumen.col_values(2) # Columna B
            encabezados = hoja_resumen.row_values(1)       # Fila 1

            if concepto.upper() in [c.upper() for c in conceptos_resumen] and nombre_mes in encabezados:
                fila_idx = [c.upper() for c in conceptos_resumen].index(concepto.upper()) + 1
                col_idx = encabezados.index(nombre_mes) + 1

                val_actual = hoja_resumen.cell(fila_idx, col_idx).value or "$0"
                num_actual = float(str(val_actual).replace('$', '').replace('.', '').replace(',', '.').strip() or 0)
                nuevo_monto = num_actual + monto

                hoja_resumen.update_cell(fila_idx, col_idx, f"${nuevo_monto:,.0f}")
        except Exception as err_resumen:
            print(f"Aviso en Resumen: {err_resumen}")

        return jsonify({
            "status": "success",
            "message": "Gasto registrado correctamente",
            "categoria": categoria,
            "tipo": tipo
        })

    except Exception as e:
        print(f"❌ ERROR DETALLADO:")
        traceback.print_exc()
        return jsonify({"status": "error", "message": str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True)