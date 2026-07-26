from flask import Flask, render_template, request, jsonify
from datetime import datetime
import gspread
from oauth2client.service_account import ServiceAccountCredentials

app = Flask(__name__)

MESES = {
    1: "ENERO", 2: "FEBRERO", 3: "MARZO", 4: "ABRIL",
    5: "MAYO", 6: "JUNIO", 7: "JULIO", 8: "AGOSTO",
    9: "SEPTIEMBRE", 10: "OCTUBRE", 11: "NOVIEMBRE", 12: "DICIEMBRE"
}

def conectar_google_sheets():
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds = ServiceAccountCredentials.from_json_keyfile_name('credenciales.json', scope)
    cliente = gspread.authorize(creds)
    # Nombre exacto de tu archivo
    spreadsheet = cliente.open("FinanzasPersonales_data")
    return spreadsheet

def detectar_categoria(hoja_cat, concepto_ingresado):
    """Busca palabras clave dentro de la hoja Categorias"""
    try:
        registros = hoja_cat.get_all_records()
        concepto_lower = concepto_ingresado.lower().strip()
        
        for fila in registros:
            palabra_clave = str(fila.get('Palabra Clave', '')).lower().strip()
            if palabra_clave and palabra_clave in concepto_lower:
                return fila.get('Categoria', 'Varios'), fila.get('Tipo', 'Pasivo')
    except Exception as e:
        print(f"Error detectando categoría: {e}")
        
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

        # 1. Inteligencia: Categorizar automáticamente
        categoria, tipo = detectar_categoria(hoja_categorias, concepto)

        # 2. Guardar en pestaña Transacciones
        # Columnas: Fecha, Hora, Concepto, Monto, Categoria, Mes
        hoja_transacciones.append_row([fecha_hoy, hora_actual, concepto, monto, categoria, nombre_mes])

        # 3. Actualizar la pestaña Resumen si el concepto está listado allí
        try:
            conceptos_resumen = hoja_resumen.col_values(2) # Columna B (CONCEPTO)
            encabezados = hoja_resumen.row_values(1)       # Fila 1 (Meses)

            if concepto.upper() in [c.upper() for c in conceptos_resumen] and nombre_mes in encabezados:
                fila_idx = [c.upper() for c in conceptos_resumen].index(concepto.upper()) + 1
                col_idx = encabezados.index(nombre_mes) + 1

                # Leer valor actual y sumar el nuevo monto
                val_actual = hoja_resumen.cell(fila_idx, col_idx).value or "$0"
                num_actual = float(str(val_actual).replace('$', '').replace('.', '').replace(',', '.').strip() or 0)
                nuevo_monto = num_actual + monto

                hoja_resumen.update_cell(fila_idx, col_idx, f"${nuevo_monto:,.0f}")
        except Exception as err_resumen:
            print(f"Aviso: No se actualizó Resumen (concepto no fijo o formato distinto): {err_resumen}")

        return jsonify({
            "status": "success",
            "message": "Gasto registrado correctamente",
            "categoria": categoria,
            "tipo": tipo
        })

    except Exception as e:
        print(f"❌ ERROR: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True)