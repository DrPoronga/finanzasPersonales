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

    // Modal
    const modal = document.getElementById('modalCategoria');
    const conceptoModal = document.getElementById('conceptoModal');
    const selectCategoria = document.getElementById('selectCategoria');
    const containerNuevaCategoria = document.getElementById('containerNuevaCategoria');
    const inputNuevaCategoria = document.getElementById('inputNuevaCategoria');
    const btnGuardarCategoria = document.getElementById('btnGuardarCategoria');
    const btnCancelarModal = document.getElementById('btnCancelarModal');

    let tipoActual = "Pasivo";
    let gastoPendiente = null;
    let necesitaRecargarMetricas = true; // Control de caché visual

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
        cargarMetricas(selectMesFiltro.value, true);
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

    async function cargarMetricas(mesSeleccionado = '', forzar = false) {
        try {
            const url = mesSeleccionado ? `/obtener_metricas?mes=${encodeURIComponent(mesSeleccionado)}` : '/obtener_metricas';
            const res = await fetch(url);
            if (res.status === 401) { bloquearApp(); return; }
            
            const data = await res.json();
            if (data.status === 'success') {
                necesitaRecargarMetricas = false; // Métricas al día

                // Disponible hoy
                document.getElementById('lblDisponibleHoyUSD').textContent = data.disponible_hoy_usd;
                document.getElementById('lblDisponibleHoyUYU').textContent = data.disponible_hoy_uyu;

                // Dinero en el banco
                document.getElementById('lblBalanceUSD').textContent = data.balance_usd;
                document.getElementById('lblBalanceUYU').textContent = data.balance_uyu;

                // Prescindibles
                document.getElementById('lblPrescindibleUSD').textContent = data.prescindible_usd;
                document.getElementById('lblPrescindibleUYU').textContent = data.prescindible_uyu;

                // Ingresos
                document.getElementById('lblIngresosUSD').textContent = data.ingresos_usd;
                document.getElementById('lblIngresosUYU').textContent = data.ingresos_uyu;

                // Gastos
                document.getElementById('lblGastosUSD').textContent = data.gastos_usd;
                document.getElementById('lblGastosUYU').textContent = data.gastos_uyu;

                // Promedio diario
                document.getElementById('lblGastoDiarioUSD').textContent = data.gasto_diario_usd;
                document.getElementById('lblGastoDiarioUYU').textContent = data.gasto_diario_uyu;

                // Tasa de ahorro
                document.getElementById('lblTasaAhorroUSD').textContent = data.tasa_ahorro_usd;
                document.getElementById('lblTasaAhorroUYU').textContent = data.tasa_ahorro_uyu;

                // Mayor categoría
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

                // Desglose por categoría
                const listaContainer = document.getElementById('listaDesglose');
                listaContainer.innerHTML = '';

                if (data.desglose && data.desglose.length > 0) {
                    data.desglose.forEach(item => {
                        const divItem = document.createElement('div');
                        divItem.className = 'desglose-item';
                        
                        let valoresHtml = '';
                        if (item.monto_usd) {
                            valoresHtml += `<span class="desglose-monto">${item.monto_usd}</span>`;
                        }
                        if (item.monto_uyu) {
                            valoresHtml += `<span class="desglose-monto">${item.monto_uyu}</span>`;
                        }

                        divItem.innerHTML = `
                            <span class="desglose-nombre">${item.categoria}</span>
                            <div class="desglose-valores">
                                ${valoresHtml}
                            </div>
                        `;
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
                necesitaRecargarMetricas = true; // Forzar recarga de métricas en la próxima visita
            } else {
                mostrarMensaje(`Error: ${data.message}`, 'error');
            }
        } catch (error) {
            mostrarMensaje('Error de conexión', 'error');
        } finally {
            if (!gastoPendiente) {
                btnSubmit.textContent = textoOriginal;
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