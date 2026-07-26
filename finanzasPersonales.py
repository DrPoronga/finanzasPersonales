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

# CACHÉ GLOBAL DE LA CONEXIÓN A GOOGLE SHEETS
SESSIONS_CACHE = {
    "client": None,
    "doc": None
}

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
    moneda = datos.get('moneda', 'USD').upper().strip()
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
            registros_cat = hoja_categorias.get_all_records()
            categoria, tipo = detectar_categoria(registros_cat, concepto)
            if not tipo: 
                tipo = tipo_ingresado

            if not categoria:
                cat_existentes = set([str(r.get('Categoria', '')).strip() for r in registros_cat if str(r.get('Categoria', '')).strip()])
                categorias_unicas = sorted(list(cat_existentes)) if cat_existentes else ["Sueldo", "Alimentación", "Servicios", "Transporte", "Ventas", "Varios"]
                
                return jsonify({
                    "status": "needs_category",
                    "categorias": categorias_unicas
                })

        hoja_transacciones.append_row([fecha_hoy, hora_actual, concepto, monto, moneda, categoria, nombre_mes, tipo, prescindible])

        return jsonify({
            "status": "success",
            "message": "Movimiento registrado correctamente",
            "categoria": categoria,
            "tipo": tipo
        })

    except Exception as e:
        traceback.print_exc()
        # Resetear sesión en caso de error de socket/red expirable
        SESSIONS_CACHE["doc"] = None
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

        # Totales acumulados históricos (Banco)
        ingresos_acum_usd, gastos_acum_usd = 0.0, 0.0
        ingresos_acum_uyu, gastos_acum_uyu = 0.0, 0.0

        # Totales mes filtrado
        ingresos_filtrado_usd, gastos_filtrado_usd, prescindible_filtrado_usd = 0.0, 0.0, 0.0
        ingresos_filtrado_uyu, gastos_filtrado_uyu, prescindible_filtrado_uyu = 0.0, 0.0, 0.0
        
        gastos_por_categoria = {}
        meses_encontrados = set()

        for r in registros:
            monto = float(r.get('Monto', 0) or 0)
            moneda = str(r.get('Moneda', 'UYU')).strip().upper() or 'UYU'
            tipo = str(r.get('Tipo', '')).strip().capitalize()
            cat = str(r.get('Categoria', 'Varios')).strip() or 'Varios'
            presc = str(r.get('Prescindible', '')).strip().capitalize()
            mes_registro = str(r.get('Mes', '')).strip().upper()

            if mes_registro:
                meses_encontrados.add(mes_registro)

            # 1. Banco (Histórico Acumulado)
            if moneda == 'USD':
                if tipo == 'Activo': ingresos_acum_usd += monto
                else: gastos_acum_usd += monto
            else:
                if tipo == 'Activo': ingresos_acum_uyu += monto
                else: gastos_acum_uyu += monto

            # 2. Filtrado por Mes
            es_mes_valido = (mes_solicitado == "TODOS") or (mes_registro == mes_solicitado)
            if es_mes_valido:
                if cat not in gastos_por_categoria:
                    gastos_por_categoria[cat] = {'USD': 0.0, 'UYU': 0.0}

                if moneda == 'USD':
                    if tipo == 'Activo':
                        ingresos_filtrado_usd += monto
                    else:
                        gastos_filtrado_usd += monto
                        gastos_por_categoria[cat]['USD'] += monto
                        if presc in ['Sí', 'Si', 'True']: prescindible_filtrado_usd += monto
                else:
                    if tipo == 'Activo':
                        ingresos_filtrado_uyu += monto
                    else:
                        gastos_filtrado_uyu += monto
                        gastos_por_categoria[cat]['UYU'] += monto
                        if presc in ['Sí', 'Si', 'True']: prescindible_filtrado_uyu += monto

        # Balance
        balance_real_usd = ingresos_acum_usd - gastos_acum_usd
        balance_real_uyu = ingresos_acum_uyu - gastos_acum_uyu

        # Disponible para hoy
        disponible_hoy_usd, disponible_hoy_uyu = 0.0, 0.0
        if mes_solicitado == mes_actual_nombre:
            dias_totales_mes = calendar.monthrange(ahora.year, ahora.month)[1]
            dias_restantes = max(1, dias_totales_mes - ahora.day + 1)
            disponible_hoy_usd = max(0.0, balance_real_usd / dias_restantes)
            disponible_hoy_uyu = max(0.0, balance_real_uyu / dias_restantes)

        # Promedio diario
        divisor_dias = max(1, ahora.day) if mes_solicitado == mes_actual_nombre else 30
        gasto_diario_usd = gastos_filtrado_usd / divisor_dias if divisor_dias > 0 else 0.0
        gasto_diario_uyu = gastos_filtrado_uyu / divisor_dias if divisor_dias > 0 else 0.0

        # Tasa de Ahorro
        tasa_ahorro_usd = ((ingresos_filtrado_usd - gastos_filtrado_usd) / ingresos_filtrado_usd * 100) if ingresos_filtrado_usd > 0 else 0.0
        tasa_ahorro_uyu = ((ingresos_filtrado_uyu - gastos_filtrado_uyu) / ingresos_filtrado_uyu * 100) if ingresos_filtrado_uyu > 0 else 0.0

        # Categoria más alta
        top_cat = "-"
        if gastos_por_categoria:
            top_cat = max(gastos_por_categoria, key=lambda c: (gastos_por_categoria[c]['USD'] * 40) + gastos_por_categoria[c]['UYU'])

        desglose = []
        for cat, montos in sorted(gastos_por_categoria.items(), key=lambda item: (item[1]['USD'] * 40) + item[1]['UYU'], reverse=True):
            if montos['USD'] > 0 or montos['UYU'] > 0:
                desglose.append({
                    "categoria": cat,
                    "monto_usd": f"US${montos['USD']:,.2f}" if montos['USD'] > 0 else None,
                    "monto_uyu": f"${montos['UYU']:,.0f} UYU" if montos['UYU'] > 0 else None
                })

        lista_meses = list(MESES.values())
        meses_ordenados = [m for m in lista_meses if m in meses_encontrados or m == mes_actual_nombre]

        return jsonify({
            "status": "success",
            "mes_actual": mes_solicitado,
            "meses_disponibles": meses_ordenados,
            "disponible_hoy_usd": f"US${disponible_hoy_usd:,.2f}" if mes_solicitado == mes_actual_nombre else "-",
            "disponible_hoy_uyu": f"${disponible_hoy_uyu:,.0f}" if mes_solicitado == mes_actual_nombre else "-",
            "balance_usd": f"US${balance_real_usd:,.2f}",
            "balance_uyu": f"${balance_real_uyu:,.0f}",
            "ingresos_usd": f"US${ingresos_filtrado_usd:,.2f}",
            "ingresos_uyu": f"${ingresos_filtrado_uyu:,.0f}",
            "gastos_usd": f"US${gastos_filtrado_usd:,.2f}",
            "gastos_uyu": f"${gastos_filtrado_uyu:,.0f}",
            "prescindible_usd": f"US${prescindible_filtrado_usd:,.2f}",
            "prescindible_uyu": f"${prescindible_filtrado_uyu:,.0f}",
            "gasto_diario_usd": f"US${gasto_diario_usd:,.2f}",
            "gasto_diario_uyu": f"${gasto_diario_uyu:,.0f}",
            "tasa_ahorro_usd": f"{tasa_ahorro_usd:.1f}%",
            "tasa_ahorro_uyu": f"{tasa_ahorro_uyu:.1f}%",
            "top_categoria": top_cat,
            "desglose": desglose
        })

    except Exception as e:
        traceback.print_exc()
        SESSIONS_CACHE["doc"] = None
        return jsonify({"status": "error", "message": str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True)