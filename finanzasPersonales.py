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

        MESES_INV = {v: k for k, v in MESES.items()}
        mes_prev_nombre = None
        if mes_solicitado in MESES_INV:
            num_mes = MESES_INV[mes_solicitado]
            num_mes_prev = 12 if num_mes == 1 else num_mes - 1
            mes_prev_nombre = MESES[num_mes_prev]

        # Acumulados Históricos (Banco)
        ingresos_acum_usd, gastos_acum_usd = 0.0, 0.0
        ingresos_acum_uyu, gastos_acum_uyu = 0.0, 0.0

        # Totales mes filtrado
        ingresos_filtrado_usd, gastos_filtrado_usd, prescindible_filtrado_usd = 0.0, 0.0, 0.0
        ingresos_filtrado_uyu, gastos_filtrado_uyu, prescindible_filtrado_uyu = 0.0, 0.0, 0.0
        
        # Totales mes anterior
        ingresos_prev_usd, gastos_prev_usd = 0.0, 0.0
        ingresos_prev_uyu, gastos_prev_uyu = 0.0, 0.0

        gastos_por_categoria = {}
        meses_encontrados = set()

        historial_fijos = {'USD': {}, 'UYU': {}}
        pagado_fijos_mes_actual = {'USD': {}, 'UYU': {}}

        # Estructura para promedio histórico de prescindibles por mes
        prescindibles_historicos_uyu = {}
        prescindibles_historicos_usd = {}

        detalles_filtrados = []
        fechas_prescindibles = []
        
        # Gastos prescindibles de la semana actual del mes
        gastado_semana_actual_uyu = 0.0
        gastado_semana_actual_usd = 0.0
        inicio_semana_actual = ahora.date() - timedelta(days=ahora.weekday())

        for r in registros:
            monto = float(r.get('Monto', 0) or 0)
            moneda = str(r.get('Moneda', 'UYU')).strip().upper() or 'UYU'
            tipo = str(r.get('Tipo', '')).strip().capitalize()
            cat = str(r.get('Categoria', 'Varios')).strip() or 'Varios'
            presc = str(r.get('Prescindible', '')).strip().capitalize()
            mes_registro = str(r.get('Mes', '')).strip().upper()
            fecha_str = str(r.get('Fecha', '')).strip()

            if mes_registro:
                meses_encontrados.add(mes_registro)

            es_prescindible = presc in ['Sí', 'Si', 'True']
            es_no_prescindible = not es_prescindible

            # Acumular prescindibles por mes para el promedio histórico
            if tipo == 'Pasivo' and es_prescindible and mes_registro:
                if moneda == 'USD':
                    prescindibles_historicos_usd[mes_registro] = prescindibles_historicos_usd.get(mes_registro, 0.0) + monto
                else:
                    prescindibles_historicos_uyu[mes_registro] = prescindibles_historicos_uyu.get(mes_registro, 0.0) + monto

            # Guardar fechas de prescindibles para la Racha
            if tipo == 'Pasivo' and es_prescindible and fecha_str:
                try:
                    dt = datetime.strptime(fecha_str, "%d/%m/%Y").date()
                    fechas_prescindibles.append(dt)

                    # Calcular cuánto se gastó en prescindibles esta semana
                    if dt >= inicio_semana_actual:
                        if moneda == 'USD': gastado_semana_actual_usd += monto
                        else: gastado_semana_actual_uyu += monto
                except ValueError:
                    pass

            # Banco
            if moneda == 'USD':
                if tipo == 'Activo': ingresos_acum_usd += monto
                else: gastos_acum_usd += monto
            else:
                if tipo == 'Activo': ingresos_acum_uyu += monto
                else: gastos_acum_uyu += monto

            # Pronóstico Fijos
            if tipo == 'Pasivo' and es_no_prescindible and mes_registro:
                if cat not in historial_fijos[moneda]:
                    historial_fijos[moneda][cat] = {}
                historial_fijos[moneda][cat][mes_registro] = historial_fijos[moneda][cat].get(mes_registro, 0.0) + monto

                if mes_registro == mes_actual_nombre:
                    pagado_fijos_mes_actual[moneda][cat] = pagado_fijos_mes_actual[moneda].get(cat, 0.0) + monto

            # Comparativa Mes Anterior
            if mes_prev_nombre and mes_registro == mes_prev_nombre:
                if tipo == 'Activo':
                    if moneda == 'USD': ingresos_prev_usd += monto
                    else: ingresos_prev_uyu += monto
                else:
                    if moneda == 'USD': gastos_prev_usd += monto
                    else: gastos_prev_uyu += monto

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
                        if es_prescindible: prescindible_filtrado_usd += monto
                    else:
                        gastos_filtrado_uyu += monto
                        gastos_por_categoria[cat]['UYU'] += monto
                        if es_prescindible: prescindible_filtrado_uyu += monto

                detalles_filtrados.append({
                    "fecha": fecha_str,
                    "hora": str(r.get('Hora', '')).strip(),
                    "concepto": str(r.get('Concepto', '')).strip(),
                    "monto": monto,
                    "moneda": moneda,
                    "categoria": cat,
                    "tipo": tipo,
                    "prescindible": es_prescindible
                })

        # CÁLCULO DE PROMEDIO HISTÓRICO DE PRESCINDIBLES
        cant_meses_hist = max(1, len(prescindibles_historicos_uyu))
        promedio_prescindible_uyu = sum(prescindibles_historicos_uyu.values()) / cant_meses_hist if prescindibles_historicos_uyu else prescindible_filtrado_uyu
        if promedio_prescindible_uyu <= 0: promedio_prescindible_uyu = 4000.0  # Base por defecto si está vacío

        # OBJETIVO MENSUAL (Reducir 20% respecto al promedio histórico)
        meta_mensual_prescindible_uyu = promedio_prescindible_uyu * 0.80
        disponible_meta_mensual_uyu = meta_mensual_prescindible_uyu - prescindible_filtrado_uyu

        # OBJETIVO SEMANAL (Tope mensual dividido en 4 semanas)
        meta_semanal_prescindible_uyu = meta_mensual_prescindible_uyu / 4.0
        disponible_meta_semanal_uyu = meta_semanal_prescindible_uyu - gastado_semana_actual_uyu

        # Porcentaje de la meta consumida este mes
        pct_prescindible_utilizado = min(100.0, (prescindible_filtrado_uyu / meta_mensual_prescindible_uyu * 100)) if meta_mensual_prescindible_uyu > 0 else 0.0

        # CÁLCULO DE RACHA (DÍAS INVICTO)
        hoy_date = ahora.date()
        if not fechas_prescindibles:
            racha_dias = 30
        else:
            ultima_fecha_p = max(fechas_prescindibles)
            if ultima_fecha_p == hoy_date:
                racha_dias = 0
            else:
                racha_dias = (hoy_date - ultima_fecha_p).days

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

        def calcular_comparativa(act_uyu, act_usd, prev_uyu, prev_usd):
            tot_act = act_uyu + (act_usd * 40)
            tot_prev = prev_uyu + (prev_usd * 40)
            if tot_prev <= 0 or mes_solicitado == "TODOS":
                return ""
            diff = ((tot_act - tot_prev) / tot_prev) * 100
            flecha = "↑" if diff > 0 else ("↓" if diff < 0 else "=")
            return f"{flecha} {abs(diff):.1f}% vs {mes_prev_nombre}"

        comp_gastos = calcular_comparativa(gastos_filtrado_uyu, gastos_filtrado_usd, gastos_prev_uyu, gastos_prev_usd)
        comp_ingresos = calcular_comparativa(ingresos_filtrado_uyu, ingresos_filtrado_usd, ingresos_prev_uyu, ingresos_prev_usd)

        top_cat = "-"
        if gastos_por_categoria:
            top_cat = max(gastos_por_categoria, key=lambda c: (gastos_por_categoria[c]['USD'] * 40) + gastos_por_categoria[c]['UYU'])

        desglose = []
        for cat, montos in sorted(gastos_por_categoria.items(), key=lambda item: (item[1]['USD'] * 40) + item[1]['UYU'], reverse=True):
            if montos['USD'] > 0 or montos['UYU'] > 0:
                desglose.append({
                    "categoria": cat,
                    "monto_uyu": f"${montos['UYU']:,.0f} UYU" if montos['UYU'] > 0 else None,
                    "monto_usd": f"US${montos['USD']:,.2f}" if montos['USD'] > 0 else None,
                    "monto_total_aprox": montos['UYU'] + (montos['USD'] * 40)
                })

        lista_meses = list(MESES.values())
        meses_ordenados = [m for m in lista_meses if m in meses_encontrados or m == mes_actual_nombre]

        GASTOS_FIJOS_DECLARADOS = [
            "UTE", "PATENTE AUTO", "ANTEL", 
            "TARJETA BBVA PESOS", "TARJETA BBVA DOLARES", "OSE", 
            "PRESTAMO OCA", "PRESTAMO VW GOL", 
            "TARJETA OCA PESOS", "TARJETA OCA DOLARES", 
            "TARJETA ITAU PESOS", "TARJETA ITAU DOLARES", 
            "TARJETA SANTANDER PESOS", "TARJETA SANTANDER DOLARES", 
            "CAMILA VISA", "PRESTAMO ITAU", "JIU-JITSU", "CHACRA CUOTA"
        ]

        detalles_fijos = []
        for fijo_nombre in GASTOS_FIJOS_DECLARADOS:
            nombre_lower = fijo_nombre.lower().strip()
            monto_pagado_uyu, monto_pagado_usd = 0.0, 0.0
            fue_pagado = False
            
            for r in registros:
                tipo_r = str(r.get('Tipo', '')).strip().capitalize()
                concepto_r = str(r.get('Concepto', '')).lower().strip()
                monto_r = float(r.get('Monto', 0) or 0)
                moneda_r = str(r.get('Moneda', 'UYU')).strip().upper()
                mes_r = str(r.get('Mes', '')).strip().upper()

                es_mes_valido = (mes_solicitado == "TODOS") or (mes_r == mes_solicitado)

                if tipo_r == 'Pasivo' and es_mes_valido:
                    if nombre_lower in concepto_r or concepto_r in nombre_lower:
                        fue_pagado = True
                        if moneda_r == 'USD': monto_pagado_usd += monto_r
                        else: monto_pagado_uyu += monto_r

            es_usd = "DOLARES" in fijo_nombre
            moneda_fijo = "USD" if es_usd else "UYU"
            monto_final = monto_pagado_usd if es_usd else monto_pagado_uyu

            detalles_fijos.append({
                "concepto": fijo_nombre,
                "moneda": moneda_fijo,
                "monto_pagado": monto_final,
                "estado": "Pagado" if fue_pagado else "Pendiente"
            })

        detalles_fijos.sort(key=lambda x: (0 if x['estado'] == 'Pendiente' else 1, x['concepto']))

        return jsonify({
            "status": "success",
            "mes_actual": mes_solicitado,
            "meses_disponibles": meses_ordenados,
            "racha_dias": racha_dias,
            "meta_semanal_uyu": f"${meta_semanal_prescindible_uyu:,.0f}",
            "gastado_semana_uyu": f"${gastado_semana_actual_uyu:,.0f}",
            "disponible_semana_uyu": f"${disponible_meta_semanal_uyu:,.0f}",
            "meta_mensual_uyu": f"${meta_mensual_prescindible_uyu:,.0f}",
            "gastado_mes_uyu": f"${prescindible_filtrado_uyu:,.0f}",
            "disponible_mes_uyu": f"${disponible_meta_mensual_uyu:,.0f}",
            "pct_prescindible_utilizado": round(pct_prescindible_utilizado, 1),
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
            "comp_gastos": comp_gastos,
            "comp_ingresos": comp_ingresos,
            "top_categoria": top_cat,
            "desglose": desglose,
            "detalles": detalles_filtrados,
            "fijos": detalles_fijos
        })

    except Exception as e:
        traceback.print_exc()
        SESSIONS_CACHE["doc"] = None
        invalidar_cache()
        return jsonify({"status": "error", "message": str(e)}), 500
        
if __name__ == '__main__':
    app.run(debug=True)