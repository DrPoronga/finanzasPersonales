from flask import Flask, render_template, request, jsonify, session
from datetime import datetime, timedelta
from functools import wraps
import calendar
import os
import json
import traceback
import gspread

app = Flask(__name__)

app.secret_key = os.environ.get('SECRET_KEY', 'finanzas_secret_key_2026_super_segura')
app.permanent_session_lifetime = timedelta(days=31)

PIN_CORRECTO = str(os.environ.get('APP_PIN', '4372736')).strip()

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

def requiere_pin(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        mes_actual = datetime.now().month
        if not session.get('autenticado') or session.get('auth_month') != mes_actual:
            session.clear()
            return jsonify({"status": "unauthorized", "message": "PIN requerido"}), 401
        return f(*args, **kwargs)
    return decorated_function

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

@app.route('/verificar_pin', methods=['POST'])
def verificar_pin():
    datos = request.get_json()
    pin_ingresado = str(datos.get('pin', '')).strip()

    if pin_ingresado == PIN_CORRECTO:
        session.permanent = True
        session['autenticado'] = True
        session['auth_month'] = datetime.now().month
        return jsonify({"status": "success"})
    
    return jsonify({"status": "error", "message": "PIN incorrecto"}), 401

@app.route('/check_auth', methods=['GET'])
def check_auth():
    mes_actual = datetime.now().month
    if session.get('autenticado') and session.get('auth_month') == mes_actual:
        return jsonify({"status": "authenticated"})
    
    session.clear()
    return jsonify({"status": "unauthenticated"}), 401

@app.route('/registrar_gasto', methods=['POST'])
@requiere_pin
def registrar_gasto():
    datos = request.get_json()
    concepto = datos.get('concepto', '').strip()
    monto = float(datos.get('monto', 0))
    tipo_ingresado = datos.get('tipo', 'Pasivo')
    prescindible = "Sí" if datos.get('prescindible', False) else "No"
    nueva_categoria = datos.get('nueva_categoria')

    ahora = datetime.now()
    fecha_hoy = ahora.strftime("%d/%m/%Y")
    hora_actual = ahora.strftime("%H:%M")
    nombre_mes = MESES[ahora.month]

    try:
        doc = conectar_google_sheets()
        hoja_transacciones = doc.worksheet("Transacciones")
        hoja_categorias = doc.worksheet("Categorias")

        if nueva_categoria:
            categoria = nueva_categoria
            tipo = tipo_ingresado
            hoja_categorias.append_row([concepto.lower(), categoria, tipo])
        else:
            categoria, tipo = detectar_categoria(hoja_categorias, concepto)
            if not tipo: 
                tipo = tipo_ingresado

            if not categoria:
                cat_records = hoja_categorias.col_values(2)[1:]
                categorias_unicas = sorted(list(set([c for c in cat_records if c.strip()])))
                
                if not categorias_unicas:
                    categorias_unicas = ["Sueldo", "Alimentación", "Servicios", "Transporte", "Ventas", "Varios"]
                
                return jsonify({
                    "status": "needs_category",
                    "categorias": categorias_unicas
                })

        hoja_transacciones.append_row([fecha_hoy, hora_actual, concepto, monto, categoria, nombre_mes, tipo, prescindible])

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
@requiere_pin
def obtener_metricas():
    try:
        doc = conectar_google_sheets()
        hoja_transacciones = doc.worksheet("Transacciones")
        registros = hoja_transacciones.get_all_records()

        ahora = datetime.now()
        mes_actual_nombre = MESES[ahora.month]
        mes_solicitado = request.args.get('mes', mes_actual_nombre).upper().strip()

        total_ingresos_acumulado = 0.0
        total_gastos_acumulado = 0.0

        total_ingresos_filtrado = 0.0
        total_gastos_filtrado = 0.0
        total_prescindible_filtrado = 0.0
        conteo_gastos_filtrado = 0
        gastos_por_categoria = {}

        meses_encontrados = set()

        for r in registros:
            monto = float(r.get('Monto', 0) or 0)
            tipo = str(r.get('Tipo', '')).strip().capitalize()
            cat = str(r.get('Categoria', 'Varios')).strip() or 'Varios'
            presc = str(r.get('Prescindible', '')).strip().capitalize()
            mes_registro = str(r.get('Mes', '')).strip().upper()

            if mes_registro:
                meses_encontrados.add(mes_registro)

            # Acumulado total para saber Dinero Real en el banco
            if tipo == 'Activo':
                total_ingresos_acumulado += monto
            else:
                total_gastos_acumulado += monto

            # Filtro para el mes seleccionado
            es_mes_valido = (mes_solicitado == "TODOS") or (mes_registro == mes_solicitado)
            if es_mes_valido:
                if tipo == 'Activo':
                    total_ingresos_filtrado += monto
                else:
                    total_gastos_filtrado += monto
                    conteo_gastos_filtrado += 1
                    gastos_por_categoria[cat] = gastos_por_categoria.get(cat, 0.0) + monto

                    if presc in ['Sí', 'Si', 'True']:
                        total_prescindible_filtrado += monto

        balance_real = total_ingresos_acumulado - total_gastos_acumulado

        # Cálculo de Disponible para Hoy (solo aplica si estamos viendo el mes actual)
        disponible_hoy_num = 0.0
        if mes_solicitado == mes_actual_nombre:
            dias_totales_mes = calendar.monthrange(ahora.year, ahora.month)[1]
            dias_restantes = max(1, dias_totales_mes - ahora.day + 1)
            disponible_hoy_num = max(0.0, balance_real / dias_restantes)

        # Promedio Diario del mes seleccionado
        if mes_solicitado == mes_actual_nombre:
            divisor_dias = max(1, ahora.day)
        elif mes_solicitado == "TODOS":
            divisor_dias = 30
        else:
            divisor_dias = 30 # Para meses pasados completos
        gasto_diario_num = (total_gastos_filtrado / divisor_dias) if divisor_dias > 0 else 0.0

        tasa_ahorro = ((total_ingresos_filtrado - total_gastos_filtrado) / total_ingresos_filtrado * 100) if total_ingresos_filtrado > 0 else 0.0

        top_cat = "-"
        if gastos_por_categoria:
            top_cat = max(gastos_por_categoria, key=gastos_por_categoria.get)

        desglose = []
        for cat, monto in sorted(gastos_por_categoria.items(), key=lambda item: item[1], reverse=True):
            pct = (monto / total_gastos_filtrado * 100) if total_gastos_filtrado > 0 else 0
            desglose.append({
                "categoria": cat,
                "monto": f"${monto:,.0f}",
                "porcentaje": f"{pct:.1f}%"
            })

        lista_meses = list(MESES.values())
        meses_ordenados = [m for m in lista_meses if m in meses_encontrados or m == mes_actual_nombre]

        return jsonify({
            "status": "success",
            "mes_actual": mes_solicitado,
            "meses_disponibles": meses_ordenados,
            "disponible_hoy": f"${disponible_hoy_num:,.0f}" if mes_solicitado == mes_actual_nombre else "-",
            "balance": f"${balance_real:,.0f}",
            "ingresos": f"${total_ingresos_filtrado:,.0f}",
            "gastos": f"${total_gastos_filtrado:,.0f}",
            "prescindible": f"${total_prescindible_filtrado:,.0f}",
            "tasa_ahorro": f"{tasa_ahorro:.1f}%",
            "gasto_diario": f"${gasto_diario_num:,.0f}",
            "top_categoria": top_cat,
            "desglose": desglose
        })
    except Exception as e:
        traceback.print_exc()
        return jsonify({"status": "error", "message": str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True)