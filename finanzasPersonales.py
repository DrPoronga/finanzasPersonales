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

    # ID de tu planilla real
    SPREADSHEET_ID = "1OZy55rSg_6Z0nu-MpCXfTofIfa_ekcDWdywDVj1wlfA"
    
    spreadsheet = cliente.open_by_key(SPREADSHEET_ID)
    return spreadsheet

def detectar_categoria(hoja_cat, concepto_ingresado):
    try:
        registros = hoja_cat.get_all_records()
        concepto_lower = concepto_ingresado.lower().strip()
        
        for fila in registros:
            palabra_clave = str(fila.get('Palabra Clave', '')).lower().strip()
            # Buscamos si la palabra clave existe y coincide
            if palabra_clave and palabra_clave in concepto_lower:
                return fila.get('Categoria', 'Varios'), fila.get('Tipo', 'Pasivo')
    except Exception as e:
        print(f"Aviso detectando categoría: {e}")
        
    return None, None # Ya no retorna "Varios" por defecto, ahora retorna None para saber que no lo encontró

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/registrar_gasto', methods=['POST'])
def registrar_gasto():
    datos = request.get_json()
    concepto = datos.get('concepto', '').strip()
    monto = float(datos.get('monto', 0))
    nueva_categoria = datos.get('nueva_categoria') # Recibimos esto si el usuario la seleccionó en el modal

    ahora = datetime.now()
    fecha_hoy = ahora.strftime("%d/%m/%Y")
    hora_actual = ahora.strftime("%H:%M")
    nombre_mes = MESES[ahora.month]

    try:
        doc = conectar_google_sheets()
        hoja_transacciones = doc.worksheet("Transacciones")
        hoja_categorias = doc.worksheet("Categorias")
        hoja_resumen = doc.worksheet("Resumen")

        # ====== LÓGICA DE APRENDIZAJE ======
        if nueva_categoria:
            # 1. El usuario nos enseñó una nueva categoría a través del modal
            categoria = nueva_categoria
            tipo = "Pasivo" # Por defecto los gastos son Pasivos
            # Guardamos la nueva regla en la pestaña Categorias
            hoja_categorias.append_row([concepto.lower(), categoria, tipo])
        else:
            # 2. Búsqueda normal para ver si ya lo conoce
            categoria, tipo = detectar_categoria(hoja_categorias, concepto)
            
            # Si no lo conoce, le pedimos al frontend que abra el modal
            if not categoria:
                # Buscamos todas las categorías únicas que tienes para armar el desplegable
                cat_records = hoja_categorias.col_values(2)[1:] # Ignoramos el encabezado
                categorias_unicas = sorted(list(set([c for c in cat_records if c.strip()])))
                
                # Por si la hoja está vacía, ponemos unas de base
                if not categorias_unicas:
                    categorias_unicas = ["Alimentación", "Servicios", "Transporte", "Varios"]
                
                return jsonify({
                    "status": "needs_category",
                    "categorias": categorias_unicas
                })

        # ====== GUARDADO NORMAL DEL GASTO ======
        # Guardar en Transacciones
        hoja_transacciones.append_row([fecha_hoy, hora_actual, concepto, monto, categoria, nombre_mes])

        # Actualizar Resumen (solo si coincide el concepto)
        try:
            conceptos_resumen = hoja_resumen.col_values(2)
            encabezados = hoja_resumen.row_values(1)

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