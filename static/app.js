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
    const chkPrescindible = document.getElementById('chkPrescindible');
    const containerPrescindible = document.getElementById('containerPrescindible');
    const btnSubmit = document.getElementById('btnSubmit');
    const mensajeDiv = document.getElementById('mensaje');

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

    let tipoActual = "Pasivo";
    let gastoPendiente = null;
    let necesitaRecargarMetricas = true;
    let detallesTransaccionesCache = [];

    checkAutenticacion();

    async function checkAutenticacion() {
        try {
            const res = await fetch('/check_auth');
            if (res.ok) { desbloquearApp(); } else { bloquearApp(); }
        } catch (e) { bloquearApp(); }
    }

    function desbloquearApp() {
        pantallaPin.classList.add('hidden');
        contenidoApp.classList.remove('hidden');
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

            if (res.ok) { desbloquearApp(); } else { mostrarMensajePin("PIN incorrecto"); }
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
        e.preventDefault();
        tipoActual = "Pasivo";
        btnSubmit.textContent = "Registrar Gasto";
        containerPrescindible.classList.remove('hidden');
        mostrarVista(vistaFormulario);
        activarMenu(menuGasto);
        toggleMenu();
    });

    menuIngreso.addEventListener('click', (e) => {
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

    async function cargarMetricas(mesSeleccionado = '') {
        try {
            const url = mesSeleccionado ? `/obtener_metricas?mes=${encodeURIComponent(mesSeleccionado)}` : '/obtener_metricas';
            const res = await fetch(url);
            if (res.status === 401) { bloquearApp(); return; }
            
            const data = await res.json();
            if (data.status === 'success') {
                necesitaRecargarMetricas = false;
                detallesTransaccionesCache = data.detalles || [];

                // Contadores para Badges de Movimientos
                const cntIngresos = detallesTransaccionesCache.filter(t => t.tipo === 'Activo').length;
                const cntGastos = detallesTransaccionesCache.filter(t => t.tipo === 'Pasivo').length;
                const cntPrescindibles = detallesTransaccionesCache.filter(t => t.tipo === 'Pasivo' && t.prescindible === true).length;

                document.getElementById('cntPrescindibles').textContent = `${cntPrescindibles} movs`;
                document.getElementById('cntIngresos').textContent = `${cntIngresos} movs`;
                document.getElementById('cntGastos').textContent = `${cntGastos} movs`;

                // Comparativas
                document.getElementById('lblCompGastos').textContent = data.comp_gastos || '';
                document.getElementById('lblCompIngresos').textContent = data.comp_ingresos || '';

                // Disponible Hoy
                document.getElementById('lblDisponibleHoyUYU').textContent = data.disponible_hoy_uyu;
                document.getElementById('lblDisponibleHoyUSD').textContent = data.disponible_hoy_usd;

                // Banco
                document.getElementById('lblBalanceUYU').textContent = data.balance_uyu;
                document.getElementById('lblBalanceUSD').textContent = data.balance_usd;

                // Prescindible
                document.getElementById('lblPrescindibleUYU').textContent = data.prescindible_uyu;
                document.getElementById('lblPrescindibleUSD').textContent = data.prescindible_usd;

                // Ingresos
                document.getElementById('lblIngresosUYU').textContent = data.ingresos_uyu;
                document.getElementById('lblIngresosUSD').textContent = data.ingresos_usd;

                // Gastos
                document.getElementById('lblGastosUYU').textContent = data.gastos_uyu;
                document.getElementById('lblGastosUSD').textContent = data.gastos_usd;

                // Promedio Diario
                document.getElementById('lblGastoDiarioUYU').textContent = data.gasto_diario_uyu;
                document.getElementById('lblGastoDiarioUSD').textContent = data.gasto_diario_usd;

                // Tasa Ahorro
                document.getElementById('lblTasaAhorroUYU').textContent = data.tasa_ahorro_uyu;
                document.getElementById('lblTasaAhorroUSD').textContent = data.tasa_ahorro_usd;

                // Top Categoria
                document.getElementById('lblTopCategoria').textContent = data.top_categoria;

                // Desplegable de meses
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

                // Desglose por categoría con barras proporcionales
                const listaContainer = document.getElementById('listaDesglose');
                listaContainer.innerHTML = '';

                if (data.desglose && data.desglose.length > 0) {
                    // Cálculo de gasto mayor para escala relativa de barras
                    const maxGasto = Math.max(...data.desglose.map(d => d.monto_total_aprox || 0));

                    data.desglose.forEach(item => {
                        const divItem = document.createElement('div');
                        divItem.className = 'desglose-item';
                        divItem.setAttribute('data-categoria', item.categoria);
                        
                        let valoresHtml = '';
                        if (item.monto_uyu) {
                            valoresHtml += `<span class="desglose-monto">${item.monto_uyu}</span>`;
                        }
                        if (item.monto_usd) {
                            valoresHtml += `<span class="desglose-monto">${item.monto_usd}</span>`;
                        }

                        // Porcentaje de la barra proporcional
                        const porcentajeBarra = maxGasto > 0 ? ((item.monto_total_aprox / maxGasto) * 100).toFixed(1) : 0;

                        divItem.innerHTML = `
                            <span class="desglose-nombre">${item.categoria}</span>
                            <div class="desglose-valores">
                                ${valoresHtml}
                            </div>
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
    cardPrescindible.addEventListener('click', () => {
        abrirModalDetalles('prescindibles');
    });

    cardIngresos.addEventListener('click', () => {
        abrirModalDetalles('ingresos');
    });

    cardGastos.addEventListener('click', () => {
        abrirModalDetalles('gastos');
    });

    // ABRIR Y MOSTRAR DETALLES
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
        }

        tituloModalDetalle.textContent = titulo;

        // Sumas acumuladas
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
                const fechaTexto = `${item.fecha} ${item.hora}`;

                itemDiv.innerHTML = `
                    <div class="detalle-info">
                        <span class="detalle-concepto">${item.concepto}</span>
                        <div class="detalle-sub">
                            <span>${fechaTexto}</span> • 
                            <span>${item.categoria}</span>
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

    // CIERRE AL TOCAR FUERA DE LA VENTANA MODAL
    modalDetalle.addEventListener('click', (e) => {
        if (e.target === modalDetalle) {
            modalDetalle.classList.add('hidden');
        }
    });

    form.addEventListener('submit', (e) => {
        e.preventDefault();
        const concepto = conceptoInput.value.trim();
        const monto = parseFloat(montoInput.value);
        const moneda = selectMoneda.value;
        const prescindible = tipoActual === "Pasivo" ? chkPrescindible.checked : false;

        if (!concepto || isNaN(monto) || monto <= 0) return;

        gastoPendiente = { concepto, monto, moneda, tipo: tipoActual, prescindible };
        enviarMovimiento(gastoPendiente);
    });

    async function enviarMovimiento(datos) {
        const textoOriginal = btnSubmit.textContent;
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
                chkPrescindible.checked = false;
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