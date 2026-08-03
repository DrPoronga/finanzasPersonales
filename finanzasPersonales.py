from flask import Flask, render_template, request, jsonify, session
from datetime import datetime, timedelta
from functools import wraps
import calendar
import re
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
    secret_key = 'clave_secreta_fija_mi_app_finanzas'
app.secret_key = secret_key

app.permanent_session_lifetime = timedelta(days=31)

pin_env = os.environ.get('APP_PIN')
if not pin_env:
    pin_env = '437273'
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

    # Soporte para Tarjetas y Cuotas
    medio_pago = str(datos.get('medio_pago', 'Banco')).strip().capitalize()
    if medio_pago not in ['Banco', 'Tickets', 'Tarjeta']:
        medio_pago = 'Banco'

    tarjeta_nombre = str(datos.get('tarjeta', '')).strip()
    try:
        cuotas = int(datos.get('cuotas', 1))
        if cuotas < 1: cuotas = 1
    except ValueError:
        cuotas = 1

    prescindible = "Sí" if datos.get('prescindible', False) else "No"
    nueva_categoria = datos.get('nueva_categoria')
    if nueva_categoria:
        nueva_categoria = str(nueva_categoria).strip()

    ahora = datetime.now()
    fecha_hoy = ahora.strftime("%d/%m/%Y")
    hora_actual = ahora.strftime("%H:%M")

    try:
        doc = conectar_google_sheets()
        hoja_transacciones = doc.worksheet("Transacciones")
        hoja_categorias = doc.worksheet("Categorias")

        tipo = tipo_ingresado

        if nueva_categoria:
            categoria = nueva_categoria
            _, registros_cat = obtener_registros_cached()
            ya_existe = any(str(r.get('Palabra Clave', '')).lower().strip() == concepto.lower() for r in registros_cat)
            
            if not ya_existe:
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

        # ==========================================
        # LÓGICA DE DIVISION EN CUOTAS HACIA EL FUTURO
        # ==========================================
        medio_pago_final = f"Tarjeta - {tarjeta_nombre}" if medio_pago == 'Tarjeta' else medio_pago

        if medio_pago == 'Tarjeta' and cuotas > 1:
            monto_por_cuota = monto / cuotas
            mes_actual_num = ahora.month
            
            filas_a_insertar = []
            for i in range(1, cuotas + 1):
                # Calculamos el mes saltando hacia adelante, si pasa de diciembre vuelve a enero
                mes_cuota_num = ((mes_actual_num + i - 2) % 12) + 1
                nombre_mes_cuota = MESES[mes_cuota_num]
                
                concepto_cuota = f"{concepto} (Cuota {i} de {cuotas})"
                
                filas_a_insertar.append([
                    fecha_hoy, hora_actual, concepto_cuota, monto_por_cuota, 
                    moneda, categoria, nombre_mes_cuota, tipo, prescindible, medio_pago_final
                ])
                
            # Insertamos todas las cuotas de golpe en la hoja
            hoja_transacciones.append_rows(filas_a_insertar, value_input_option='RAW')
            
        else:
            # Gasto normal o tarjeta en 1 pago
            nombre_mes = MESES[ahora.month]
            concepto_final = f"{concepto} (1 pago)" if medio_pago == 'Tarjeta' else concepto
            
            hoja_transacciones.append_row(
                [fecha_hoy, hora_actual, concepto_final, monto, moneda, categoria, nombre_mes, tipo, prescindible, medio_pago_final],
                value_input_option='RAW'
            )

        invalidar_cache()

        return jsonify({
            "status": "success",
            "message": "Movimiento registrado correctamente",
            "categoria": categoria,
            "tipo": tipo
        })

    except Exception as e:
        import traceback
        traceback.print_exc()
        SESSIONS_CACHE["doc"] = None
        invalidar_cache()
        return jsonify({"status": "error", "message": str(e)}), 500
        
import re  # <-- Asegúrate de incluir esta importación al principio del archivo

def detectar_categoria(registros_cat, concepto_ingresado):
    try:
        concepto_lower = concepto_ingresado.lower().strip()
        for fila in registros_cat:
            palabra_clave = str(fila.get('Palabra Clave', '')).lower().strip()
            # Búsqueda con límites de palabra para evitar falsos positivos
            if palabra_clave and re.search(r'\b' + re.escape(palabra_clave) + r'\b', concepto_lower):
                return fila.get('Categoria', 'Varios')
    except Exception as e:
        print(f"Aviso detectando categoría: {e}")
        
    return None

import re

# ==========================================
# AYUDANTES DE NORMALIZACIÓN Y DETECCIÓN
# ==========================================
def normalizar_moneda(m):
    m_str = str(m or '').strip().upper()
    if m_str in ['USD', 'US$', 'DOLARES', 'DOLAR', 'U$S']:
        return 'USD'
    return 'UYU'

def es_pasivo(tipo):
    t = str(tipo or '').strip().lower()
    return t not in ['activo', 'activos', 'ingreso', 'ingresos']

def coincide_gasto_fijo(fijo_nombre, concepto_r):
    c = str(concepto_r or '').strip().upper()
    f = str(fijo_nombre or '').strip().upper()

    # Diccionario de alias exactos
    ALIAS_EXACTOS = {
        "PATENTE AUTO": ["PATENTE"],
        "CHACRA CUOTA": ["CHACRA"],
        "CAMILA VISA": ["VISA CAMILA", "TARJETA CAMILA"],
        "JIU-JITSU": ["JIU JITSU", "JIUJITSU"]
    }

    # 1. Coincidencia exacta de la cadena completa
    if c == f:
        return True

    # 2. Coincidencia con alias exacto autorizado
    if f in ALIAS_EXACTOS and c in ALIAS_EXACTOS[f]:
        return True

    return False
    
@app.route('/obtener_metricas', methods=['GET'])
@requiere_pin
def obtener_metricas():
    try:
        force_reload = request.args.get('force', 'false').lower() == 'true'
        if force_reload:
            invalidar_cache()

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

        # Acumulados
        ingresos_acum_usd, gastos_acum_usd = 0.0, 0.0
        ingresos_acum_uyu, gastos_acum_uyu = 0.0, 0.0
        ingresos_tickets_uyu, gastos_tickets_uyu = 0.0, 0.0

        # Totales mes filtrado
        ingresos_filtrado_usd, gastos_filtrado_usd, prescindible_filtrado_usd = 0.0, 0.0, 0.0
        ingresos_filtrado_uyu, gastos_filtrado_uyu, prescindible_filtrado_uyu = 0.0, 0.0, 0.0
        
        # Totales mes anterior
        ingresos_prev_usd, gastos_prev_usd = 0.0, 0.0
        ingresos_prev_uyu, gastos_prev_uyu = 0.0, 0.0

        gastos_por_categoria = {}
        gastos_por_concepto_especifico = {}
        meses_encontrados = set()
        fechas_unicas_filtradas = set()

        historial_fijos = {'USD': {}, 'UYU': {}}
        pagado_fijos_mes_actual = {'USD': {}, 'UYU': {}}

        prescindibles_historicos_uyu = {}
        prescindibles_historicos_usd = {}

        detalles_filtrados = []
        fechas_prescindibles = []
        
        gastado_semana_actual_uyu = 0.0
        gastado_semana_actual_usd = 0.0
        inicio_semana_actual = ahora.date() - timedelta(days=ahora.weekday())

        for r in registros:
            try:
                monto_raw = str(r.get('Monto', 0)).replace(',', '.').strip()
                monto = float(monto_raw) if monto_raw else 0.0
            except (ValueError, TypeError):
                monto = 0.0
            moneda = normalizar_moneda(r.get('Moneda'))
            tipo = str(r.get('Tipo', '')).strip().capitalize()
            cat = str(r.get('Categoria', 'Varios')).strip() or 'Varios'
            concepto_raw = str(r.get('Concepto', '')).strip()
            presc = str(r.get('Prescindible', '')).strip().capitalize()
            mes_registro = str(r.get('Mes', '')).strip().upper()
            fecha_str = str(r.get('Fecha', '')).strip()

            medio_pago_raw = r.get('Cuenta') or r.get('Medio de Pago') or 'Banco'
            medio_pago = str(medio_pago_raw).strip().capitalize()
            if medio_pago not in ['Banco', 'Tickets']:
                medio_pago = 'Banco'

            if mes_registro:
                meses_encontrados.add(mes_registro)

            es_prescindible = presc in ['Sí', 'Si', 'True']
            es_no_prescindible = not es_prescindible
            es_ajuste = (cat.upper() == "AJUSTE") or ("AJUSTE DE SALDO" in concepto_raw.upper())

            if es_pasivo(tipo) and es_prescindible and mes_registro:
                if moneda == 'USD':
                    prescindibles_historicos_usd[mes_registro] = prescindibles_historicos_usd.get(mes_registro, 0.0) + monto
                else:
                    prescindibles_historicos_uyu[mes_registro] = prescindibles_historicos_uyu.get(mes_registro, 0.0) + monto

            if es_pasivo(tipo) and es_prescindible and fecha_str:
                try:
                    dt = datetime.strptime(fecha_str, "%d/%m/%Y").date()
                    fechas_prescindibles.append(dt)

                    if dt >= inicio_semana_actual:
                        if moneda == 'USD': gastado_semana_actual_usd += monto
                        else: gastado_semana_actual_uyu += monto
                except ValueError:
                    pass

            # SEPARACIÓN BANCO VS TICKETS
            if medio_pago == 'Tickets':
                if not es_pasivo(tipo): ingresos_tickets_uyu += monto
                else: gastos_tickets_uyu += monto
            else:
                if moneda == 'USD':
                    if not es_pasivo(tipo): ingresos_acum_usd += monto
                    else: gastos_acum_usd += monto
                else:
                    if not es_pasivo(tipo): ingresos_acum_uyu += monto
                    else: gastos_acum_uyu += monto

            # Pronóstico Fijos
            if medio_pago != 'Tickets' and es_pasivo(tipo) and es_no_prescindible and mes_registro:
                if mes_registro != mes_actual_nombre:
                    if cat not in historial_fijos[moneda]:
                        historial_fijos[moneda][cat] = {}
                    historial_fijos[moneda][cat][mes_registro] = historial_fijos[moneda][cat].get(mes_registro, 0.0) + monto
                else:
                    pagado_fijos_mes_actual[moneda][cat] = pagado_fijos_mes_actual[moneda].get(cat, 0.0) + monto

            # Comparativa Mes Anterior
            if mes_prev_nombre and mes_registro == mes_prev_nombre:
                if not es_pasivo(tipo):
                    if moneda == 'USD': ingresos_prev_usd += monto
                    else: ingresos_prev_uyu += monto
                else:
                    if moneda == 'USD': gastos_prev_usd += monto
                    else: gastos_prev_uyu += monto

            # Filtro mes
            es_mes_valido = (mes_solicitado == "TODOS") or (mes_registro == mes_solicitado)
            if es_mes_valido:
                if fecha_str:
                    fechas_unicas_filtradas.add(fecha_str)

                if not es_pasivo(tipo):
                    if moneda == 'USD': ingresos_filtrado_usd += monto
                    else: ingresos_filtrado_uyu += monto
                else:
                    if moneda == 'USD':
                        gastos_filtrado_usd += monto
                        if es_prescindible: prescindible_filtrado_usd += monto
                        if not es_ajuste:
                            if cat not in gastos_por_categoria: gastos_por_categoria[cat] = {'USD': 0.0, 'UYU': 0.0}
                            conc_key = concepto_raw.title()
                            if conc_key not in gastos_por_concepto_especifico: gastos_por_concepto_especifico[conc_key] = {'USD': 0.0, 'UYU': 0.0, 'categoria': cat}
                            gastos_por_categoria[cat]['USD'] += monto
                            gastos_por_concepto_especifico[conc_key]['USD'] += monto
                    else:
                        gastos_filtrado_uyu += monto
                        if es_prescindible: prescindible_filtrado_uyu += monto
                        if not es_ajuste:
                            if cat not in gastos_por_categoria: gastos_por_categoria[cat] = {'USD': 0.0, 'UYU': 0.0}
                            conc_key = concepto_raw.title()
                            if conc_key not in gastos_por_concepto_especifico: gastos_por_concepto_especifico[conc_key] = {'USD': 0.0, 'UYU': 0.0, 'categoria': cat}
                            gastos_por_categoria[cat]['UYU'] += monto
                            gastos_por_concepto_especifico[conc_key]['UYU'] += monto

                detalles_filtrados.append({
                    "fecha": fecha_str,
                    "hora": str(r.get('Hora', '')).strip(),
                    "concepto": concepto_raw,
                    "monto": monto,
                    "moneda": moneda,
                    "categoria": cat,
                    "tipo": tipo,
                    "prescindible": es_prescindible,
                    "medio_pago": medio_pago
                })

        saldo_tickets_uyu = ingresos_tickets_uyu - gastos_tickets_uyu

        cant_meses_hist = max(1, len(prescindibles_historicos_uyu))
        promedio_prescindible_uyu = sum(prescindibles_historicos_uyu.values()) / cant_meses_hist if prescindibles_historicos_uyu else prescindible_filtrado_uyu
        if promedio_prescindible_uyu <= 0: promedio_prescindible_uyu = 4000.0

        cant_meses_filtrados = len(meses_encontrados) if mes_solicitado == "TODOS" else 1
        meta_mensual_prescindible_uyu = (promedio_prescindible_uyu * 0.80) * cant_meses_filtrados
        disponible_meta_mensual_uyu = meta_mensual_prescindible_uyu - prescindible_filtrado_uyu

        meta_semanal_prescindible_uyu = (promedio_prescindible_uyu * 0.80) / 4.0
        disponible_meta_semanal_uyu = meta_semanal_prescindible_uyu - gastado_semana_actual_uyu

        pct_prescindible_utilizado = min(100.0, (prescindible_filtrado_uyu / meta_mensual_prescindible_uyu * 100)) if meta_mensual_prescindible_uyu > 0 else 0.0

        hoy_date = ahora.date()
        if not fechas_prescindibles:
            racha_dias = 30
        else:
            ultima_fecha_p = max(fechas_prescindibles)
            racha_dias = 0 if ultima_fecha_p == hoy_date else (hoy_date - ultima_fecha_p).days

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

        # DISPONIBLE PARA HOY (Corregido)
        disponible_hoy_usd, disponible_hoy_uyu = 0.0, 0.0
        if mes_solicitado == mes_actual_nombre:
            dias_totales_mes = calendar.monthrange(ahora.year, ahora.month)[1]
            dias_restantes = max(1, dias_totales_mes - ahora.day + 1)
            
            neto_mes_restante_uyu = max(0.0, ingresos_filtrado_uyu - compromisos_pendientes_uyu - gastos_filtrado_uyu)
            neto_mes_restante_usd = max(0.0, ingresos_filtrado_usd - compromisos_pendientes_usd - gastos_filtrado_usd)

            disponible_hoy_uyu = neto_mes_restante_uyu / dias_restantes
            disponible_hoy_usd = neto_mes_restante_usd / dias_restantes

        if mes_solicitado == "TODOS":
            divisor_dias = len(fechas_unicas_filtradas) if fechas_unicas_filtradas else 1
        elif mes_solicitado == mes_actual_nombre:
            divisor_dias = max(1, ahora.day)
        else:
            num_m = MESES_INV.get(mes_solicitado, ahora.month)
            divisor_dias = calendar.monthrange(ahora.year, num_m)[1]

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

        desglose_conceptos = []
        for conc, montos in sorted(gastos_por_concepto_especifico.items(), key=lambda item: (item[1]['USD'] * 40) + item[1]['UYU'], reverse=True):
            if montos['USD'] > 0 or montos['UYU'] > 0:
                desglose_conceptos.append({
                    "concepto": conc,
                    "categoria": montos['categoria'],
                    "monto_uyu": f"${montos['UYU']:,.0f} UYU" if montos['UYU'] > 0 else None,
                    "monto_usd": f"US${montos['USD']:,.2f}" if montos['USD'] > 0 else None,
                    "monto_total_aprox": montos['UYU'] + (montos['USD'] * 40)
                })

        lista_meses = list(MESES.values())
        meses_ordenados = [m for m in lista_meses if m in meses_encontrados or m == mes_actual_nombre]

        GASTOS_FIJOS_DECLARADOS = [
            "UTE", "PATENTE AUTO", "ANTEL", 
            "TARJETA BBVA PESOS", "TARJETA BBVA DOLARES", "OSE", 
            "PRESTAMO OCA", "TARJETA OCA PESOS", "TARJETA OCA DOLARES", 
            "TARJETA SANTANDER PESOS", "TARJETA SANTANDER DOLARES", 
            "CAMILA VISA", "PRESTAMO ITAU", "JIU-JITSU", "CHACRA CUOTA"
        ]

        detalles_fijos = []
        for fijo_nombre in GASTOS_FIJOS_DECLARADOS:
            monto_pagado_uyu = 0.0
            monto_pagado_usd = 0.0
            fue_pagado = False
            
            for r in registros:
                tipo_r = r.get('Tipo', '')
                concepto_r = r.get('Concepto', '')
                monto_r = float(r.get('Monto', 0) or 0)
                moneda_r = normalizar_moneda(r.get('Moneda'))
                mes_r = str(r.get('Mes', '')).strip().upper()

                es_mes_valido = (mes_solicitado == "TODOS") or (mes_r == mes_solicitado)

                if es_pasivo(tipo_r) and es_mes_valido:
                    if coincide_gasto_fijo(fijo_nombre, concepto_r):
                        fue_pagado = True
                        if moneda_r == 'USD': monto_pagado_usd += monto_r
                        else: monto_pagado_uyu += monto_r

            es_fijo_usd = "DOLARES" in fijo_nombre
            
            if monto_pagado_usd > 0 and monto_pagado_uyu == 0:
                moneda_final = "USD"
                monto_final = monto_pagado_usd
            elif monto_pagado_uyu > 0 and monto_pagado_usd == 0:
                moneda_final = "UYU"
                monto_final = monto_pagado_uyu
            elif monto_pagado_usd > 0 and monto_pagado_uyu > 0:
                moneda_final = "USD" if es_fijo_usd else "UYU"
                monto_final = monto_pagado_usd if es_fijo_usd else monto_pagado_uyu
            else:
                moneda_final = "USD" if es_fijo_usd else "UYU"
                monto_final = 0.0

            detalles_fijos.append({
                "concepto": fijo_nombre,
                "moneda": moneda_final,
                "monto_pagado": monto_final,
                "estado": "Pagado" if fue_pagado else "Pendiente"
            })

        detalles_fijos.sort(key=lambda x: (0 if x['estado'] == 'Pendiente' else 1, x['concepto']))

        return jsonify({
            "status": "success",
            "mes_actual": mes_solicitado,
            "balance_uyu_num": balance_real_uyu,
            "balance_usd_num": balance_real_usd,
            "meses_disponibles": meses_ordenados,
            "racha_dias": racha_dias,
            "saldo_tickets_uyu": f"${saldo_tickets_uyu:,.0f}",
            "saldo_tickets_num": saldo_tickets_uyu,
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
            "desglose_conceptos": desglose_conceptos,
            "detalles": detalles_filtrados,
            "fijos": detalles_fijos
        })

    except Exception as e:
        traceback.print_exc()
        SESSIONS_CACHE["doc"] = None
        invalidar_cache()
        return jsonify({"status": "error", "message": str(e)}), 500
    
@app.route('/obtener_conceptos', methods=['GET'])
@requiere_pin
def obtener_conceptos():
    try:
        registros, _ = obtener_registros_cached()
        
        # Filtramos y normalizamos conceptos únicos en formato Title
        pasivos = set()
        activos = set()
        
        for r in registros:
            c = str(r.get('Concepto', '')).strip().title()
            if not c:
                continue
            if es_pasivo(r.get('Tipo')):
                pasivos.add(c)
            else:
                activos.add(c)

        return jsonify({
            "status": "success",
            "pasivos": sorted(list(pasivos)),
            "activos": sorted(list(activos))
        })
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500
        
if __name__ == '__main__':
    app.run(debug=True)