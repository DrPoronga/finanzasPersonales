document.addEventListener("DOMContentLoaded", () => {
    // PIN
    const pantallaPin = document.getElementById('pantallaPin');
    const contenidoApp = document.getElementById('contenidoApp');
    const formPin = document.getElementById('formPin');
    const inputPin = document.getElementById('inputPin');
    const btnPin = document.getElementById('btnPin');
    const mensajePin = document.getElementById('mensajePin');

    // Menú
    const btnMenu = document.getElementById('btnMenu');
    const btnCloseMenu = document.getElementById('btnCloseMenu');
    const sideMenu = document.getElementById('sideMenu');
    const overlay = document.getElementById('overlay');
    
    const menuGasto = document.getElementById('menuGasto');
    const menuIngreso = document.getElementById('menuIngreso');
    const menuMetricas = document.getElementById('menuMetricas');
    
    const vistaFormulario = document.getElementById('vistaFormulario');
    const vistaMetricas = document.getElementById('vistaMetricas');

    // Formulario
    const form = document.getElementById('registroForm');
    const conceptoInput = document.getElementById('concepto');
    const montoInput = document.getElementById('monto');
    const selectMoneda = document.getElementById('selectMoneda');
    const selectMedioPago = document.getElementById('selectMedioPago');
    const chkPrescindible = document.getElementById('chkPrescindible');
    const containerPrescindible = document.getElementById('containerPrescindible');
    const btnSubmit = document.getElementById('btnSubmit');
    const mensajeDiv = document.getElementById('mensaje');

    // Toggles
    const radioBanco = document.getElementById('pagoBanco');
    const radioTickets = document.getElementById('pagoTickets');
    const msgTicketsStatus = document.getElementById('msgTicketsStatus');
	const radioTarjeta = document.getElementById('pagoTarjeta');
    const containerTarjeta = document.getElementById('containerTarjeta');
    const selectTarjeta = document.getElementById('selectTarjeta');
    const inputCuotas = document.getElementById('inputCuotas');

    // Métricas
    const selectMesFiltro = document.getElementById('selectMesFiltro');
    const cardPrescindible = document.getElementById('cardPrescindible');
    const cardIngresos = document.getElementById('cardIngresos');
    const cardGastos = document.getElementById('cardGastos');

    // Modal Clasificar
    const modal = document.getElementById('modalCategoria');
    const conceptoModal = document.getElementById('conceptoModal');
    const selectCategoria = document.getElementById('selectCategoria');
    const containerNuevaCategoria = document.getElementById('containerNuevaCategoria');
    const inputNuevaCategoria = document.getElementById('inputNuevaCategoria');
    const btnGuardarCategoria = document.getElementById('btnGuardarCategoria');
    const btnCancelarModal = document.getElementById('btnCancelarModal');

    // Modal Ver Detalles
    const modalDetalle = document.getElementById('modalDetalle');
    const tituloModalDetalle = document.getElementById('tituloModalDetalle');
    const resumenModalDetalle = document.getElementById('resumenModalDetalle');
    const listaModalDetalle = document.getElementById('listaModalDetalle');

    let balanceUYUNum = 0;
    let balanceUSDNum = 0;
    let saldoTicketsDisponibleNum = 0;
    let tipoActual = "Pasivo";
    let gastoPendiente = null;
    let necesitaRecargarMetricas = true;
    let detallesTransaccionesCache = [];
    let gastosFijosCache = [];
    const cardFijos = document.getElementById('cardFijos');

    checkAutenticacion();
	
    // Normalización de comas y decimales (.00)
    montoInput.addEventListener('input', () => {
        montoInput.value = montoInput.value.replace(',', '.');
    });

    montoInput.addEventListener('blur', () => {
        let val = montoInput.value.trim();
        if (val !== '' && !isNaN(val)) {
            montoInput.value = parseFloat(val).toFixed(2);
        }
    });

    // TOGGLE DE MONEDA
    const radioUYU = document.getElementById('monedaUYU');
    const radioUSD = document.getElementById('monedaUSD');
    const inputMoneda = document.getElementById('selectMoneda');

    if (radioUYU && radioUSD) {
        radioUYU.addEventListener('change', () => inputMoneda.value = 'UYU');
        radioUSD.addEventListener('change', () => inputMoneda.value = 'USD');
    }

    // TOGGLE DE MEDIO DE PAGO
    if (radioBanco && radioTickets && radioTarjeta) {
        radioBanco.addEventListener('change', () => {
            selectMedioPago.value = 'Banco';
            msgTicketsStatus.classList.add('hidden');
            containerTarjeta.classList.add('hidden');
        });

        radioTickets.addEventListener('change', () => {
            containerTarjeta.classList.add('hidden');
            if (tipoActual === 'Pasivo' && saldoTicketsDisponibleNum <= 0) {
                radioBanco.checked = true;
                selectMedioPago.value = 'Banco';
                msgTicketsStatus.classList.remove('hidden');
            } else {
                selectMedioPago.value = 'Tickets';
                msgTicketsStatus.classList.add('hidden');
            }
        });

        radioTarjeta.addEventListener('change', () => {
            selectMedioPago.value = 'Tarjeta';
            msgTicketsStatus.classList.add('hidden');
            if (tipoActual === 'Pasivo') {
                containerTarjeta.classList.remove('hidden');
            } else {
                containerTarjeta.classList.add('hidden');
            }
        });
    }

    async function checkAutenticacion() {
        try {
            const res = await fetch('/check_auth');
            if (res.ok) { desbloquearApp(); } else { bloquearApp(); }
        } catch (e) { bloquearApp(); }
    }

    // --- LÓGICA PULL-TO-REFRESH ESTILO IOS ---
    const ptrIndicator = document.getElementById('ptrIndicator');
    const ptrText = document.getElementById('ptrText');
    const ptrSpinner = document.getElementById('ptrSpinner');

    let touchStartY = 0;
    let touchMoveY = 0;
    let isPulling = false;

    window.addEventListener('touchstart', (e) => {
        if (window.scrollY <= 5 && !vistaMetricas.classList.contains('hidden')) {
            touchStartY = e.touches[0].clientY;
            isPulling = true;
        }
    }, { passive: true });

    window.addEventListener('touchmove', (e) => {
        if (!isPulling) return;
        touchMoveY = e.touches[0].clientY;
        const diff = touchMoveY - touchStartY;

        if (diff > 30) {
            ptrIndicator.classList.add('visible');
            if (diff > 80) {
                ptrText.textContent = "Suelta para actualizar";
            } else {
                ptrText.textContent = "Desliza para actualizar";
            }
        }
    }, { passive: true });

    window.addEventListener('touchend', () => {
        if (!isPulling) return;
        const diff = touchMoveY - touchStartY;
		
        if (diff > 80) {
            ptrText.textContent = "Actualizando...";
            ptrSpinner.classList.remove('hidden');
			
            cargarMetricas(selectMesFiltro.value, true).finally(() => {
                setTimeout(() => {
                    ptrIndicator.classList.remove('visible');
                    ptrSpinner.classList.add('hidden');
                }, 500);
            });
        } else {
            ptrIndicator.classList.remove('visible');
        }
		
        isPulling = false;
        touchStartY = 0;
        touchMoveY = 0;
    });
	
window.editarSaldo = async function(medioPago, moneda) {
    // 1. Forzamos la actualización de métricas para traer saldos reales
    await cargarMetricas(selectMesFiltro.value, true);

    let saldoActual = 0;
    if (medioPago === 'Tickets') {
        saldoActual = saldoTicketsDisponibleNum || 0;
    } else if (moneda === 'USD') {
        saldoActual = balanceUSDNum || 0; // Utiliza SOLO el saldo en USD
    } else {
        saldoActual = balanceUYUNum || 0; // Utiliza SOLO el saldo en UYU
    }

    const simbolo = moneda === 'USD' ? 'US$' : '$';
    const nombreMoneda = moneda === 'USD' ? 'DÓLARES (USD)' : 'PESOS (UYU)';

    const promptMsg = `=== AJUSTAR CUENTA EN ${nombreMoneda} ===\n\n` +
                      `Saldo actual en base de datos: ${simbolo}${saldoActual.toFixed(2)}\n\n` +
                      `Escribe el nuevo saldo TOTAL REAL que tienes en ${moneda}:`;

    const nuevoSaldoStr = prompt(promptMsg, saldoActual.toFixed(2));
    if (nuevoSaldoStr === null) return;

    let valorLimpio = nuevoSaldoStr.trim();
    if (valorLimpio.includes('.') && valorLimpio.includes(',')) {
        if (valorLimpio.lastIndexOf(',') > valorLimpio.lastIndexOf('.')) {
            valorLimpio = valorLimpio.replace(/\./g, '').replace(',', '.');
        } else {
            valorLimpio = valorLimpio.replace(/,/g, '');
        }
    } else if (valorLimpio.includes(',')) {
        valorLimpio = valorLimpio.replace(',', '.');
    }

    const nuevoSaldo = parseFloat(valorLimpio);
    if (isNaN(nuevoSaldo)) {
        alert("Por favor ingrese un número válido.");
        return;
    }

    const diferencia = nuevoSaldo - saldoActual;
    if (Math.abs(diferencia) < 0.01) {
        alert("El saldo ingresado es igual al actual.");
        return;
    }

    const tipoAjuste = diferencia > 0 ? "Activo" : "Pasivo";
    const montoAjuste = Math.abs(diferencia);

    const datosAjuste = {
        concepto: "Ajuste de Saldo",
        monto: montoAjuste,
        moneda: moneda,
        medio_pago: medioPago,
        tipo: tipoAjuste,
        prescindible: false,
        nueva_categoria: "Ajuste"
    };

    try {
        const res = await fetch('/registrar_gasto', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(datosAjuste)
        });

        const resData = await res.json();
        if (resData.status === 'success') {
            alert(`Saldo ajustado correctamente en ${moneda}.`);
            cargarMetricas(selectMesFiltro.value, true);
        } else {
            alert("Error ajustando saldo: " + resData.message);
        }
    } catch (e) {
        alert("Error de conexión al ajustar saldo.");
    }
};

    let conceptosCache = { pasivos: [], activos: [] };

    async function cargarConceptos() {
        try {
            const res = await fetch('/obtener_conceptos');
            if (!res.ok) return;
            const data = await res.json();
            if (data.status === 'success') {
                conceptosCache.pasivos = data.pasivos || [];
                conceptosCache.activos = data.activos || [];
                actualizarDatalist();
            }
        } catch (e) {
            console.error("Error cargando lista de autocompletado", e);
        }
    }

    function actualizarDatalist() {
        const datalist = document.getElementById('listaConceptosAuto');
        if (!datalist) return;
        
        datalist.innerHTML = '';
        const lista = (tipoActual === "Pasivo") ? conceptosCache.pasivos : conceptosCache.activos;

        lista.forEach(item => {
            const option = document.createElement('option');
            option.value = item;
            datalist.appendChild(option);
        });
    }

    function desbloquearApp() {
        pantallaPin.classList.add('hidden');
        contenidoApp.classList.remove('hidden');
        cargarConceptos();
    }

    function bloquearApp() {
        pantallaPin.classList.remove('hidden');
        contenidoApp.classList.add('hidden');
    }

    formPin.addEventListener('submit', async (e) => {
        e.preventDefault();
        const pin = inputPin.value.trim();
        if (!pin) return;

        btnPin.textContent = "Verificando...";
        btnPin.disabled = true;

        try {
            const res = await fetch('/verificar_pin', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ pin })
            });

            if (res.ok) { 
                desbloquearApp(); 
            } else { 
                mostrarMensajePin("PIN incorrecto"); 
            }
        } catch (e) {
            mostrarMensajePin("Error de conexión");
        } finally {
            btnPin.textContent = "Ingresar";
            btnPin.disabled = false;
        }
    });

    function mostrarMensajePin(texto) {
        mensajePin.textContent = texto;
        mensajePin.className = 'error';
        setTimeout(() => { mensajePin.className = 'hidden'; }, 3000);
    }

    function toggleMenu() {
        sideMenu.classList.toggle('hidden');
        overlay.classList.toggle('hidden');
    }

    btnMenu.addEventListener('click', toggleMenu);
    btnCloseMenu.addEventListener('click', toggleMenu);
    overlay.addEventListener('click', toggleMenu);

    menuGasto.addEventListener('click', (e) => {
        actualizarDatalist();
        e.preventDefault();
        tipoActual = "Pasivo";
        btnSubmit.textContent = "Registrar Gasto";
        containerPrescindible.classList.remove('hidden');
        mostrarVista(vistaFormulario);
        activarMenu(menuGasto);
        toggleMenu();
    });

    menuIngreso.addEventListener('click', (e) => {
        actualizarDatalist();
        e.preventDefault();
        tipoActual = "Activo";
        btnSubmit.textContent = "Registrar Ingreso";
        containerPrescindible.classList.add('hidden');
        mostrarVista(vistaFormulario);
        activarMenu(menuIngreso);
        toggleMenu();
    });

    menuMetricas.addEventListener('click', (e) => {
        e.preventDefault();
        mostrarVista(vistaMetricas);
        activarMenu(menuMetricas);
        toggleMenu();
        if (necesitaRecargarMetricas) {
            cargarMetricas();
        }
    });

    selectMesFiltro.addEventListener('change', () => {
        cargarMetricas(selectMesFiltro.value);
    });

    function mostrarVista(vista) {
        vistaFormulario.classList.add('hidden');
        vistaMetricas.classList.add('hidden');
        vista.classList.remove('hidden');
    }

    function activarMenu(elementoActivo) {
        menuGasto.classList.remove('active');
        menuIngreso.classList.remove('active');
        menuMetricas.classList.remove('active');
        elementoActivo.classList.add('active');
    }

    function abrirModalDetalles(filtroTipo, categoriaNombre = '') {
        let listaFiltrada = [];
        let titulo = '';

        if (filtroTipo === 'prescindibles') {
            titulo = 'Gastos Prescindibles';
            listaFiltrada = detallesTransaccionesCache.filter(t => t.tipo === 'Pasivo' && t.prescindible === true);
        } else if (filtroTipo === 'ingresos') {
            titulo = 'Detalle de Ingresos';
            listaFiltrada = detallesTransaccionesCache.filter(t => t.tipo === 'Activo');
        } else if (filtroTipo === 'gastos') {
            titulo = 'Detalle de Gastos';
            listaFiltrada = detallesTransaccionesCache.filter(t => t.tipo === 'Pasivo');
        } else if (filtroTipo === 'categoria') {
            titulo = `Gastos en ${categoriaNombre}`;
            listaFiltrada = detallesTransaccionesCache.filter(t => t.tipo === 'Pasivo' && t.categoria === categoriaNombre);
        } else if (filtroTipo === 'fijos') {
            titulo = 'Control de Gastos Fijos';
        }

        tituloModalDetalle.textContent = titulo;

        if (filtroTipo === 'fijos') {
            const pend = gastosFijosCache.filter(f => f.estado === 'Pendiente').length;
            const pag = gastosFijosCache.filter(f => f.estado === 'Pagado').length;

            resumenModalDetalle.innerHTML = `
                <div>Pendientes: <span>${pend}</span></div>
                <div>Pagados: <span>${pag}</span></div>
            `;

            listaModalDetalle.innerHTML = '';
            gastosFijosCache.forEach(fijo => {
                const itemDiv = document.createElement('div');
                itemDiv.className = 'detalle-item';

                const esPagado = fijo.estado === 'Pagado';
                const badgeClass = esPagado ? 'badge-pagado' : 'badge-pendiente';
                const monedaSym = fijo.moneda === 'USD' ? 'US$' : '$';
                const montoFmt = `${monedaSym}${fijo.monto_pagado.toLocaleString('es-UY', {maximumFractionDigits:0})}`;

                const textoSub = esPagado 
                    ? `Pagado: ${montoFmt}` 
                    : `Pendiente de pago`;

                itemDiv.innerHTML = `
                    <div class="detalle-info">
                        <span class="detalle-concepto">${fijo.concepto}</span>
                        <div class="detalle-sub">
                            <span>${textoSub}</span>
                        </div>
                    </div>
                    <div style="text-align: right;">
                        <span class="badge-fijo ${badgeClass}">${fijo.estado}</span>
                    </div>
                `;
                listaModalDetalle.appendChild(itemDiv);
            });

            modalDetalle.classList.remove('hidden');
            return;
        }

        let sumUSD = 0;
        let sumUYU = 0;
        listaFiltrada.forEach(item => {
            if (item.moneda === 'USD') sumUSD += item.monto;
            else sumUYU += item.monto;
        });

        let resumenHtml = '';
        if (sumUYU > 0) resumenHtml += `<div>UYU: <span>$${sumUYU.toLocaleString('es-UY', {maximumFractionDigits: 0})}</span></div>`;
        if (sumUSD > 0) resumenHtml += `<div>USD: <span>US$${sumUSD.toLocaleString('en-US', {minimumFractionDigits: 2, maximumFractionDigits: 2})}</span></div>`;
        if (sumUSD === 0 && sumUYU === 0) resumenHtml = '<div>Sin movimientos registrados</div>';

        resumenModalDetalle.innerHTML = resumenHtml;
        listaModalDetalle.innerHTML = '';

        if (filtroTipo === 'categoria' && listaFiltrada.length > 0) {
            const agrupado = {};
            listaFiltrada.forEach(item => {
                const conc = item.concepto.trim();
                if (!agrupado[conc]) agrupado[conc] = { uyu: 0, usd: 0 };
                if (item.moneda === 'USD') agrupado[conc].usd += item.monto;
                else agrupado[conc].uyu += item.monto;
            });

            const subBox = document.createElement('div');
            subBox.className = 'subdesglose-box';
            let subHtml = '<strong style="display:block; margin-bottom: 6px; font-size:12px; color:var(--subtext);">TOTALES POR ÍTEM:</strong>';

            Object.keys(agrupado).sort((a,b) => agrupado[b].uyu - agrupado[a].uyu).forEach(conc => {
                const mUYU = agrupado[conc].uyu > 0 ? `$${agrupado[conc].uyu.toLocaleString('es-UY', {maximumFractionDigits:0})}` : '';
                const mUSD = agrupado[conc].usd > 0 ? `US$${agrupado[conc].usd.toLocaleString('en-US', {minimumFractionDigits:2})}` : '';
                const mFmt = [mUYU, mUSD].filter(Boolean).join(' / ');
                subHtml += `<div class="subdesglose-row"><span>${conc}</span><strong>${mFmt}</strong></div>`;
            });

            subBox.innerHTML = subHtml;
            listaModalDetalle.appendChild(subBox);
        }

        if (listaFiltrada.length === 0) {
            listaModalDetalle.innerHTML = '<div style="color: var(--subtext); text-align: center; padding: 20px;">No hay registros para este filtro.</div>';
        } else {
            listaFiltrada.forEach(item => {
                const itemDiv = document.createElement('div');
                itemDiv.className = 'detalle-item';

                const esActivo = item.tipo === 'Activo';
                const signo = esActivo ? '+' : '-';
                const formatoMonto = item.moneda === 'USD' 
                    ? `${signo}US$${item.monto.toLocaleString('en-US', {minimumFractionDigits: 2, maximumFractionDigits: 2})}`
                    : `${signo}$${item.monto.toLocaleString('es-UY', {maximumFractionDigits: 0})}`;

                const badgePrescindible = item.prescindible ? '<span class="badge-prescindible">Prescindible</span>' : '';
                const medioPagoTag = item.medio_pago === 'Tickets' ? '<span class="badge" style="background:#FEF3C7; color:#92400E;">Tickets</span>' : '';
                const fechaTexto = `${item.fecha} ${item.hora}`;

                itemDiv.innerHTML = `
                    <div class="detalle-info">
                        <span class="detalle-concepto">${item.concepto}</span>
                        <div class="detalle-sub">
                            <span>${fechaTexto}</span> • 
                            <span>${item.categoria}</span>
                            ${medioPagoTag}
                            ${badgePrescindible}
                        </div>
                    </div>
                    <div class="detalle-monto ${esActivo ? 'monto-activo' : 'monto-pasivo'}">
                        ${formatoMonto}
                    </div>
                `;
                listaModalDetalle.appendChild(itemDiv);
            });
        }

        modalDetalle.classList.remove('hidden');
    }
	
    async function cargarMetricas(mesSeleccionado = '', force = false) {
        try {
            let url = mesSeleccionado ? `/obtener_metricas?mes=${encodeURIComponent(mesSeleccionado)}` : '/obtener_metricas';
            if (force) {
                url += (url.includes('?') ? '&' : '?') + 'force=true';
            }

            const res = await fetch(url);
            if (res.status === 401) { bloquearApp(); return; }
            
            const data = await res.json();
            if (data.status === 'success') {
                balanceUYUNum = data.balance_uyu_num || 0;
                balanceUSDNum = data.balance_usd_num || 0;
                saldoTicketsDisponibleNum = data.saldo_tickets_num || 0;

                const lblSaldoTickets = document.getElementById('lblSaldoTickets');
                if (lblSaldoTickets) {
                    lblSaldoTickets.textContent = data.saldo_tickets_uyu;
                }

                const lblRachaDias = document.getElementById('lblRachaDias');
                const racha = data.racha_dias || 0;
                if (lblRachaDias) {
                    lblRachaDias.textContent = `${racha} ${racha === 1 ? 'Día' : 'Días'}`;
                }

                document.getElementById('lblMetaSemanal').textContent = `Meta: ${data.meta_semanal_uyu}`;
                document.getElementById('lblGastadoSemana').textContent = data.gastado_semana_uyu;
                document.getElementById('lblDisponibleSemana').textContent = data.disponible_semana_uyu;

                document.getElementById('lblMetaMensual').textContent = `Meta: ${data.meta_mensual_uyu}`;
                document.getElementById('lblGastadoMes').textContent = data.gastado_mes_uyu;
                document.getElementById('lblDisponibleMes').textContent = data.disponible_mes_uyu;

                const pctUtilizado = data.pct_prescindible_utilizado || 0;
                const fillBar = document.getElementById('barPrescindibleFill');
                if (fillBar) {
                    fillBar.style.width = `${pctUtilizado}%`;
                    fillBar.classList.remove('fill-warning', 'fill-danger');
                    if (pctUtilizado > 85) {
                        fillBar.classList.add('fill-danger');
                    } else if (pctUtilizado > 60) {
                        fillBar.classList.add('fill-warning');
                    }
                }

                const listaFijos = document.getElementById('listaFijos');
                if (listaFijos) {
                    listaFijos.innerHTML = '';
                    gastosFijosCache = data.fijos || [];
                    const top3 = gastosFijosCache.slice(0, 3);

                    if (top3.length > 0) {
                        top3.forEach(fijo => {
                            const itemDiv = document.createElement('div');
                            itemDiv.className = 'fijo-item';

                            const esPagado = fijo.estado === 'Pagado';
                            const badgeClass = esPagado ? 'badge-pagado' : 'badge-pendiente';
                            const monedaSym = fijo.moneda === 'USD' ? 'US$' : '$';
                            const montoFmt = `${monedaSym}${fijo.monto_pagado.toLocaleString('es-UY', {maximumFractionDigits:0})}`;

                            const textoMonto = esPagado 
                                ? `<span>Pagado: <strong>${montoFmt}</strong></span>`
                                : `<span style="color: var(--subtext);">Pendiente de pago</span>`;

                            itemDiv.innerHTML = `
                                <div class="fijo-header">
                                    <span class="fijo-nombre">${fijo.concepto}</span>
                                    <span class="badge-fijo ${badgeClass}">${fijo.estado}</span>
                                </div>
                                <div class="fijo-monto">
                                    ${textoMonto}
                                </div>
                            `;
                            listaFijos.appendChild(itemDiv);
                        });
                    }
                }
                
                necesitaRecargarMetricas = false;
                detallesTransaccionesCache = data.detalles || [];

                const cntIngresos = detallesTransaccionesCache.filter(t => t.tipo === 'Activo').length;
                const cntGastos = detallesTransaccionesCache.filter(t => t.tipo === 'Pasivo').length;
                const cntPrescindibles = detallesTransaccionesCache.filter(t => t.tipo === 'Pasivo' && t.prescindible === true).length;

                document.getElementById('cntPrescindibles').textContent = `${cntPrescindibles} movs`;
                document.getElementById('cntIngresos').textContent = `${cntIngresos} movs`;
                document.getElementById('cntGastos').textContent = `${cntGastos} movs`;

                document.getElementById('lblCompGastos').textContent = data.comp_gastos || '';
                document.getElementById('lblCompIngresos').textContent = data.comp_ingresos || '';

                document.getElementById('lblDisponibleHoyUYU').textContent = data.disponible_hoy_uyu;
                document.getElementById('lblDisponibleHoyUSD').textContent = data.disponible_hoy_usd;

                document.getElementById('lblBalanceUYU').textContent = data.balance_uyu;
                document.getElementById('lblBalanceUSD').textContent = data.balance_usd;

                document.getElementById('lblPrescindibleUYU').textContent = data.prescindible_uyu;
                document.getElementById('lblPrescindibleUSD').textContent = data.prescindible_usd;

                document.getElementById('lblIngresosUYU').textContent = data.ingresos_uyu;
                document.getElementById('lblIngresosUSD').textContent = data.ingresos_usd;

                document.getElementById('lblGastosUYU').textContent = data.gastos_uyu;
                document.getElementById('lblGastosUSD').textContent = data.gastos_usd;

                document.getElementById('lblGastoDiarioUYU').textContent = data.gasto_diario_uyu;
                document.getElementById('lblGastoDiarioUSD').textContent = data.gasto_diario_usd;

                document.getElementById('lblTasaAhorroUYU').textContent = data.tasa_ahorro_uyu;
                document.getElementById('lblTasaAhorroUSD').textContent = data.tasa_ahorro_usd;

                document.getElementById('lblTopCategoria').textContent = data.top_categoria;

                selectMesFiltro.innerHTML = '';
                data.meses_disponibles.forEach(mes => {
                    const opt = document.createElement('option');
                    opt.value = mes;
                    opt.textContent = mes;
                    if (mes === data.mes_actual) opt.selected = true;
                    selectMesFiltro.appendChild(opt);
                });

                const optTodos = document.createElement('option');
                optTodos.value = "TODOS";
                optTodos.textContent = "TODO EL HISTORIAL";
                if (data.mes_actual === "TODOS") optTodos.selected = true;
                selectMesFiltro.appendChild(optTodos);

                const listaConceptosContainer = document.getElementById('listaConceptos');
                if (listaConceptosContainer) {
                    listaConceptosContainer.innerHTML = '';
                    if (data.desglose_conceptos && data.desglose_conceptos.length > 0) {
                        const maxConcepto = Math.max(...data.desglose_conceptos.map(d => d.monto_total_aprox || 0));

                        data.desglose_conceptos.slice(0, 8).forEach(item => {
                            const divItem = document.createElement('div');
                            divItem.className = 'desglose-item';
                            
                            let valoresHtml = '';
                            if (item.monto_uyu) valoresHtml += `<span class="desglose-monto">${item.monto_uyu}</span>`;
                            if (item.monto_usd) valoresHtml += `<span class="desglose-monto">${item.monto_usd}</span>`;

                            const porcentajeBarra = maxConcepto > 0 ? ((item.monto_total_aprox / maxConcepto) * 100).toFixed(1) : 0;

                            divItem.innerHTML = `
                                <div>
                                    <span class="desglose-nombre">${item.concepto}</span>
                                    <span class="concepto-subcat">${item.categoria}</span>
                                </div>
                                <div class="desglose-valores">${valoresHtml}</div>
                                <div class="desglose-bar" style="width: ${porcentajeBarra}%;"></div>
                            `;
                            listaConceptosContainer.appendChild(divItem);
                        });
                    } else {
                        listaConceptosContainer.innerHTML = '<div style="color: var(--subtext); font-size: 14px;">Sin datos registrados.</div>';
                    }
                }

                const listaContainer = document.getElementById('listaDesglose');
                listaContainer.innerHTML = '';

                if (data.desglose && data.desglose.length > 0) {
                    const maxGasto = Math.max(...data.desglose.map(d => d.monto_total_aprox || 0));

                    data.desglose.forEach(item => {
                        const divItem = document.createElement('div');
                        divItem.className = 'desglose-item';
                        divItem.setAttribute('data-categoria', item.categoria);
                        
                        let valoresHtml = '';
                        if (item.monto_uyu) valoresHtml += `<span class="desglose-monto">${item.monto_uyu}</span>`;
                        if (item.monto_usd) valoresHtml += `<span class="desglose-monto">${item.monto_usd}</span>`;

                        const porcentajeBarra = maxGasto > 0 ? ((item.monto_total_aprox / maxGasto) * 100).toFixed(1) : 0;

                        divItem.innerHTML = `
                            <span class="desglose-nombre">${item.categoria}</span>
                            <div class="desglose-valores">${valoresHtml}</div>
                            <div class="desglose-bar" style="width: ${porcentajeBarra}%;"></div>
                        `;

                        divItem.addEventListener('click', () => {
                            abrirModalDetalles('categoria', item.categoria);
                        });

                        listaContainer.appendChild(divItem);
                    });
                } else {
                    listaContainer.innerHTML = '<div style="color: var(--subtext); font-size: 14px;">Sin gastos registrados.</div>';
                }
            }
        } catch (error) {
            console.error("Error cargando métricas", error);
        }
    }
	
    // TARJETAS INTERACTIVAS
    cardPrescindible.addEventListener('click', () => { abrirModalDetalles('prescindibles'); });
    cardIngresos.addEventListener('click', () => { abrirModalDetalles('ingresos'); });
    cardGastos.addEventListener('click', () => { abrirModalDetalles('gastos'); });
    if (cardFijos) { cardFijos.addEventListener('click', () => { abrirModalDetalles('fijos'); }); }

    modalDetalle.addEventListener('click', (e) => {
        if (e.target === modalDetalle) {
            modalDetalle.classList.add('hidden');
        }
    });

    form.addEventListener('submit', (e) => {
        e.preventDefault();
        const concepto = conceptoInput.value.trim();
        const valorLimpio = montoInput.value.replace(',', '.').trim();
        const monto = parseFloat(valorLimpio);

        const radioMonedaChecked = document.querySelector('input[name="monedaRadio"]:checked');
        const moneda = radioMonedaChecked ? radioMonedaChecked.value : 'UYU';

        const medio_pago = selectMedioPago.value;
        const prescindible = tipoActual === "Pasivo" ? chkPrescindible.checked : false;
        
        // Atrapamos tarjeta y cuotas
        const tarjeta = selectMedioPago.value === 'Tarjeta' ? selectTarjeta.value : '';
        const cuotas = selectMedioPago.value === 'Tarjeta' ? parseInt(inputCuotas.value) || 1 : 1;

        if (!concepto || isNaN(monto) || monto <= 0) return;

        gastoPendiente = { concepto, monto, moneda, medio_pago, tipo: tipoActual, prescindible, cuotas, tarjeta };
        enviarMovimiento(gastoPendiente);
    });
	
    async function enviarMovimiento(datos) {
        btnSubmit.textContent = "Procesando...";
        btnSubmit.disabled = true;

        try {
            const response = await fetch('/registrar_gasto', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(datos)
            });

            if (response.status === 401) { bloquearApp(); return; }

            const data = await response.json();

            if (data.status === 'needs_category') {
                abrirModal(datos.concepto, data.categorias);
            } else if (data.status === 'success') {
                mostrarMensaje(`Registrado correctamente`, 'success');
                form.reset();
                if (radioUYU) radioUYU.checked = true;
                if (inputMoneda) inputMoneda.value = 'UYU';
                chkPrescindible.checked = false;
                radioBanco.checked = true;
                selectMedioPago.value = 'Banco';
                msgTicketsStatus.classList.add('hidden');
                gastoPendiente = null;
                necesitaRecargarMetricas = true;
            } else {
                mostrarMensaje(`Error: ${data.message}`, 'error');
            }
        } catch (error) {
            mostrarMensaje('Error de conexión', 'error');
        } finally {
            if (!gastoPendiente) {
                btnSubmit.textContent = tipoActual === "Activo" ? "Registrar Ingreso" : "Registrar Gasto";
                btnSubmit.disabled = false;
            }
        }
    }

    function abrirModal(concepto, categoriasDisponibles) {
        conceptoModal.textContent = concepto;
        selectCategoria.innerHTML = '';
        inputNuevaCategoria.value = '';
        containerNuevaCategoria.classList.add('hidden');

        categoriasDisponibles.forEach(cat => {
            const opt = document.createElement('option');
            opt.value = cat; opt.textContent = cat;
            selectCategoria.appendChild(opt);
        });

        const optNueva = document.createElement('option');
        optNueva.value = "__NUEVA__";
        optNueva.textContent = "+ Crear nueva categoría...";
        selectCategoria.appendChild(optNueva);

        modal.classList.remove('hidden');
    }

    selectCategoria.addEventListener('change', () => {
        if (selectCategoria.value === "__NUEVA__") {
            containerNuevaCategoria.classList.remove('hidden');
            inputNuevaCategoria.focus();
        } else {
            containerNuevaCategoria.classList.add('hidden');
        }
    });

    btnGuardarCategoria.addEventListener('click', () => {
        if (!gastoPendiente) return;

        let categoriaFinal = selectCategoria.value;

        if (categoriaFinal === "__NUEVA__") {
            categoriaFinal = inputNuevaCategoria.value.trim();
            if (!categoriaFinal) {
                alert("Ingresa un nombre para la categoría.");
                return;
            }
        }

        gastoPendiente.nueva_categoria = categoriaFinal;
        modal.classList.add('hidden');
        enviarMovimiento(gastoPendiente);
    });

    btnCancelarModal.addEventListener('click', () => {
        modal.classList.add('hidden');
        gastoPendiente = null;
        btnSubmit.textContent = tipoActual === "Activo" ? "Registrar Ingreso" : "Registrar Gasto";
        btnSubmit.disabled = false;
    });

    function mostrarMensaje(texto, tipo) {
        mensajeDiv.textContent = texto;
        mensajeDiv.className = tipo;
        setTimeout(() => { mensajeDiv.className = 'hidden'; }, 3000);
    }
});