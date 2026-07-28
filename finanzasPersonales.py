from flask import Flask, render_template, request, jsonify, session
from datetime import datetime, timedelta
from functools import wraps
import calendar
import os
import json
import time
import traceback
import gspread

app = Flask(__name__)

# ==========================================
# 1. SEGURIDAD (SECRET_KEY Y PIN)
# ==========================================
secret_key = os.environ.get('SECRET_KEY')
if not secret_key:
    secret_key = os.urandom(24).hex()
app.secret_key = secret_key

app.permanent_session_lifetime = timedelta(days=31)

pin_env = os.environ.get('APP_PIN')
if not pin_env:
    pin_env = '4372736'
PIN_CORRECTO = str(pin_env).strip()

MESES = {
    1: "ENERO", 2: "FEBRERO", 3: "MARZO", 4: "ABRIL",
    5: "MAYO", 6: "JUNIO", 7: "JULIO", 8: "AGOSTO",
    9: "SEPTIEMBRE", 10: "OCTUBRE", 11: "NOVIEMBRE", 12: "DICIEMBRE"
}

# ==========================================
# 2. CACHÉ EN MEMORIA (RENDIMIENTO)
# ==========================================
SESSIONS_CACHE = {
    "client": None,
    "doc": None
}

DATA_CACHE = {
    "transacciones": None,
    "categorias": None,
    "timestamp": 0
}
CACHE_TTL = 300  # TTL de 5 minutos

def invalidar_cache():
    DATA_CACHE["transacciones"] = None
    DATA_CACHE["categorias"] = None
    DATA_CACHE["timestamp"] = 0

# ==========================================
# 3. REINTENTOS PARA GSPREAD (RESILIENCIA)
# ==========================================
def con_reintentos(max_intentos=3, delay=1):
    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            ultimo_error = None
            for intento in range(1, max_intentos + 1):
                try:
                    return f(*args, **kwargs)
                except Exception as e:
                    ultimo_error = e
                    print(f"⚠️ Error en gspread (Intento {intento}/{max_intentos}): {e}")
                    SESSIONS_CACHE["doc"] = None
                    time.sleep(delay)
            raise ultimo_error
        return wrapper
    return decorator

@con_reintentos(max_intentos=3, delay=1)
def conectar_google_sheets():
    if SESSIONS_CACHE["doc"]:
        return SESSIONS_CACHE["doc"]

    json_env = os.environ.get('GOOGLE_CREDS_JSON')
    if json_env:
        info_creds = json.loads(json_env)
        cliente = gspread.service_account_from_dict(info_creds)
    else:
        ruta_creds = '/etc/secrets/credenciales.json' if os.path.exists('/etc/secrets/credenciales.json') else 'credenciales.json'
        cliente = gspread.service_account(filename=ruta_creds)

    SPREADSHEET_ID = "1OZy55rSg_6Z0nu-MpCXfTofIfa_ekcDWdywDVj1wlfA"
    doc = cliente.open_by_key(SPREADSHEET_ID)
    
    SESSIONS_CACHE["client"] = cliente
    SESSIONS_CACHE["doc"] = doc
    return doc

@con_reintentos(max_intentos=3, delay=1)
def obtener_registros_cached():
    ahora_ts = time.time()
    
    if (DATA_CACHE["transacciones"] is not None and 
        DATA_CACHE["categorias"] is not None and 
        (ahora_ts - DATA_CACHE["timestamp"]) < CACHE_TTL):
        return DATA_CACHE["transacciones"], DATA_CACHE["categorias"]

    doc = conectar_google_sheets()
    transacciones = doc.worksheet("Transacciones").get_all_records()
    categorias = doc.worksheet("Categorias").get_all_records()

    DATA_CACHE["transacciones"] = transacciones
    DATA_CACHE["categorias"] = categorias
    DATA_CACHE["timestamp"] = ahora_ts

    return transacciones, categorias

def requiere_pin(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        mes_actual = datetime.now().month
        if not session.get('autenticado') or session.get('auth_month') != mes_actual:
            session.clear()
            return jsonify({"status": "unauthorized", "message": "PIN requerido"}), 401
        return f(*args, **kwargs)
    return decorated_function

def detectar_categoria(registros_cat, concepto_ingresado):
    try:
        concepto_lower = concepto_ingresado.lower().strip()
        for fila in registros_cat:
            palabra_clave = str(fila.get('Palabra Clave', '')).lower().strip()
            if palabra_clave and palabra_clave in concepto_lower:
                return fila.get('Categoria', 'Varios')
    except Exception as e:
        print(f"Aviso detectando categoría: {e}")
        
    return None

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/verificar_pin', methods=['POST'])
def verificar_pin():
    datos = request.get_json() or {}
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
    datos = request.get_json() or {}

    concepto = str(datos.get('concepto', '')).strip()
    if not concepto:
        return jsonify({"status": "error", "message": "El concepto es obligatorio."}), 400

    try:
        monto = float(datos.get('monto', 0))
        if monto <= 0:
            return jsonify({"status": "error", "message": "El monto debe ser positivo y mayor a 0."}), 400
    except (ValueError, TypeError):
        return jsonify({"status": "error", "message": "Monto inválido."}), 400

    moneda = str(datos.get('moneda', 'UYU')).upper().strip()
    if moneda not in ['USD', 'UYU']:
        return jsonify({"status": "error", "message": "Moneda no soportada."}), 400

    tipo_ingresado = str(datos.get('tipo', 'Pasivo')).strip().capitalize()
    if tipo_ingresado not in ['Activo', 'Pasivo']:
        return jsonify({"status": "error", "message": "Tipo no válido."}), 400

    prescindible = "Sí" if datos.get('prescindible', False) else "No"
    nueva_categoria = datos.get('nueva_categoria')
    if nueva_categoria:
        nueva_categoria = str(nueva_categoria).strip()

    ahora = datetime.now()
    fecha_hoy = ahora.strftime("%d/%m/%Y")
    hora_actual = ahora.strftime("%H:%M")
    nombre_mes = MESES[ahora.month]

    try:
        doc = conectar_google_sheets()
        hoja_transacciones = doc.worksheet("Transacciones")
        hoja_categorias = doc.worksheet("Categorias")

        tipo = tipo_ingresado

        if nueva_categoria:
            categoria = nueva_categoria
            hoja_categorias.append_row([concepto.lower(), categoria, tipo])
        else:
            _, registros_cat = obtener_registros_cached()
            categoria = detectar_categoria(registros_cat, concepto)

            if not categoria:
                cat_existentes = set([str(r.get('Categoria', '')).strip() for r in registros_cat if str(r.get('Categoria', '')).strip()])
                categorias_unicas = sorted(list(cat_existentes)) if cat_existentes else ["Sueldo", "Alimentación", "Servicios", "Transporte", "Ventas", "Varios"]
                
                return jsonify({
                    "status": "needs_category",
                    "categorias": categorias_unicas
                })

        hoja_transacciones.append_row([fecha_hoy, hora_actual, concepto, monto, moneda, categoria, nombre_mes, tipo, prescindible])

        invalidar_cache()

        return jsonify({
            "status": "success",
            "message": "Movimiento registrado correctamente",
            "categoria": categoria,
            "tipo": tipo
        })

    except Exception as e:
        traceback.print_exc()
        SESSIONS_CACHE["doc"] = None
        invalidar_cache()
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/obtener_metricas', methods=['GET'])
@requiere_pin
def obtener_metricas():
    try:
        registros, _ = obtener_registros_cached()

        ahora = datetime.now()
        mes_actual_nombre = MESES[ahora.month]
        mes_solicitado = request.args.get('mes', mes_actual_nombre).upper().strip()

        # Acumulados Históricos (Banco)
        ingresos_acum_usd, gastos_acum_usd = 0.0, 0.0
        ingresos_acum_uyu, gastos_acum_uyu = 0.0, 0.0

        # Totales mes filtrado
        ingresos_filtrado_usd, gastos_filtrado_usd, prescindible_filtrado_usd = 0.0, 0.0, 0.0
        ingresos_filtrado_uyu, gastos_filtrado_uyu, prescindible_filtrado_uyu = 0.0, 0.0, 0.0
        
        gastos_por_categoria = {}
        meses_encontrados = set()

        historial_fijos = {'USD': {}, 'UYU': {}}
        pagado_fijos_mes_actual = {'USD': {}, 'UYU': {}}

        detalles_filtrados = []

        for r in registros:
            monto = float(r.get('Monto', 0) or 0)
            moneda = str(r.get('Moneda', 'UYU')).strip().upper() or 'UYU'
            tipo = str(r.get('Tipo', '')).strip().capitalize()
            cat = str(r.get('Categoria', 'Varios')).strip() or 'Varios'
            presc = str(r.get('Prescindible', '')).strip().capitalize()
            mes_registro = str(r.get('Mes', '')).strip().upper()

            if mes_registro:
                meses_encontrados.add(mes_registro)

            es_no_prescindible = presc in ['No', 'False', '']

            # Banco
            if moneda == 'USD':
                if tipo == 'Activo': ingresos_acum_usd += monto
                else: gastos_acum_usd += monto
            else:
                if tipo == 'Activo': ingresos_acum_uyu += monto
                else: gastos_acum_uyu += monto

            # Pronóstico
            if tipo == 'Pasivo' and es_no_prescindible and mes_registro:
                if cat not in historial_fijos[moneda]:
                    historial_fijos[moneda][cat] = {}
                historial_fijos[moneda][cat][mes_registro] = historial_fijos[moneda][cat].get(mes_registro, 0.0) + monto

                if mes_registro == mes_actual_nombre:
                    pagado_fijos_mes_actual[moneda][cat] = pagado_fijos_mes_actual[moneda].get(cat, 0.0) + monto

            # Filtro mes
            es_mes_valido = (mes_solicitado == "TODOS") or (mes_registro == mes_solicitado)
            if es_mes_valido:
                if tipo == 'Activo':
                    if moneda == 'USD': ingresos_filtrado_usd += monto
                    else: ingresos_filtrado_uyu += monto
                else:
                    if cat not in gastos_por_categoria:
                        gastos_por_categoria[cat] = {'USD': 0.0, 'UYU': 0.0}

                    if moneda == 'USD':
                        gastos_filtrado_usd += monto
                        gastos_por_categoria[cat]['USD'] += monto
                        if presc in ['Sí', 'Si', 'True']: prescindible_filtrado_usd += monto
                    else:
                        gastos_filtrado_uyu += monto
                        gastos_por_categoria[cat]['UYU'] += monto
                        if presc in ['Sí', 'Si', 'True']: prescindible_filtrado_uyu += monto

                detalles_filtrados.append({
                    "fecha": str(r.get('Fecha', '')).strip(),
                    "hora": str(r.get('Hora', '')).strip(),
                    "concepto": str(r.get('Concepto', '')).strip(),
                    "monto": monto,
                    "moneda": moneda,
                    "categoria": cat,
                    "tipo": tipo,
                    "prescindible": presc in ['Sí', 'Si', 'True']
                })

        balance_real_usd = ingresos_acum_usd - gastos_acum_usd
        balance_real_uyu = ingresos_acum_uyu - gastos_acum_uyu

        compromisos_pendientes_usd = 0.0
        compromisos_pendientes_uyu = 0.0

        for mon in ['USD', 'UYU']:
            pendientes_totales = 0.0
            for cat, meses_data in historial_fijos[mon].items():
                cant_meses = len(meses_data)
                if cant_meses >= 1:
                    promedio_mensual = sum(meses_data.values()) / cant_meses
                    ya_pagado = pagado_fijos_mes_actual[mon].get(cat, 0.0)
                    pendiente_cat = max(0.0, promedio_mensual - ya_pagado)
                    pendientes_totales += pendiente_cat

            if mon == 'USD': compromisos_pendientes_usd = pendientes_totales
            else: compromisos_pendientes_uyu = pendientes_totales

        disponible_hoy_usd, disponible_hoy_uyu = 0.0, 0.0
        if mes_solicitado == mes_actual_nombre:
            dias_totales_mes = calendar.monthrange(ahora.year, ahora.month)[1]
            dias_restantes = max(1, dias_totales_mes - ahora.day + 1)
            
            balance_disponible_usd = max(0.0, balance_real_usd - compromisos_pendientes_usd)
            balance_disponible_uyu = max(0.0, balance_real_uyu - compromisos_pendientes_uyu)

            disponible_hoy_usd = balance_disponible_usd / dias_restantes
            disponible_hoy_uyu = balance_disponible_uyu / dias_restantes

        divisor_dias = max(1, ahora.day) if mes_solicitado == mes_actual_nombre else 30
        gasto_diario_usd = gastos_filtrado_usd / divisor_dias if divisor_dias > 0 else 0.0
        gasto_diario_uyu = gastos_filtrado_uyu / divisor_dias if divisor_dias > 0 else 0.0

        tasa_ahorro_usd = ((ingresos_filtrado_usd - gastos_filtrado_usd) / ingresos_filtrado_usd * 100) if ingresos_filtrado_usd > 0 else 0.0
        tasa_ahorro_uyu = ((ingresos_filtrado_uyu - gastos_filtrado_uyu) / ingresos_filtrado_uyu * 100) if ingresos_filtrado_uyu > 0 else 0.0

        top_cat = "-"
        if gastos_por_categoria:
            top_cat = max(gastos_por_categoria, key=lambda c: (gastos_por_categoria[c]['USD'] * 40) + gastos_por_categoria[c]['UYU'])

        desglose = []
        for cat, montos in sorted(gastos_por_categoria.items(), key=lambda item: (item[1]['USD'] * 40) + item[1]['UYU'], reverse=True):
            if montos['USD'] > 0 or montos['UYU'] > 0:
                desglose.append({
                    "categoria": cat,
                    "monto_uyu": f"${montos['UYU']:,.0f} UYU" if montos['UYU'] > 0 else None,
                    "monto_usd": f"US${montos['USD']:,.2f}" if montos['USD'] > 0 else None
                })

        lista_meses = list(MESES.values())
        meses_ordenados = [m for m in lista_meses if m in meses_encontrados or m == mes_actual_nombre]

        return jsonify({
            "status": "success",
            "mes_actual": mes_solicitado,
            "meses_disponibles": meses_ordenados,
            "disponible_hoy_uyu": f"${disponible_hoy_uyu:,.0f}" if mes_solicitado == mes_actual_nombre else "-",
            "disponible_hoy_usd": f"US${disponible_hoy_usd:,.2f}" if mes_solicitado == mes_actual_nombre else "-",
            "balance_uyu": f"${balance_real_uyu:,.0f}",
            "balance_usd": f"US${balance_real_usd:,.2f}",
            "ingresos_uyu": f"${ingresos_filtrado_uyu:,.0f}",
            "ingresos_usd": f"US${ingresos_filtrado_usd:,.2f}",
            "gastos_uyu": f"${gastos_filtrado_uyu:,.0f}",
            "gastos_usd": f"US${gastos_filtrado_usd:,.2f}",
            "prescindible_uyu": f"${prescindible_filtrado_uyu:,.0f}",
            "prescindible_usd": f"US${prescindible_filtrado_usd:,.2f}",
            "gasto_diario_uyu": f"${gasto_diario_uyu:,.0f}",
            "gasto_diario_usd": f"US${gasto_diario_usd:,.2f}",
            "tasa_ahorro_uyu": f"{tasa_ahorro_uyu:.1f}%",
            "tasa_ahorro_usd": f"{tasa_ahorro_usd:.1f}%",
            "top_categoria": top_cat,
            "desglose": desglose,
            "detalles": detalles_filtrados
        })

    except Exception as e:
        traceback.print_exc()
        SESSIONS_CACHE["doc"] = None
        invalidar_cache()
        return jsonify({"status": "error", "message": str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True)