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
        cargarMetricas();
    });

    selectMesFiltro.addEventListener('change', () => {
        cargarMetricas(selectMesFiltro.value);
    });

    document.getElementById('btnActualizarMetricas').addEventListener('click', () => {
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
                document.getElementById('lblDisponibleHoy').innerHTML = data.disponible_hoy;
                document.getElementById('lblBalance').innerHTML = data.balance;
                document.getElementById('lblPrescindible').innerHTML = data.prescindible;
                document.getElementById('lblIngresos').innerHTML = data.ingresos;
                document.getElementById('lblGastos').innerHTML = data.gastos;
                document.getElementById('lblTasaAhorro').innerHTML = data.tasa_ahorro;
                document.getElementById('lblGastoDiario').innerHTML = data.gasto_diario;
                document.getElementById('lblTopCategoria').innerHTML = data.top_categoria;

                // Actualizar desplegable de meses sin perder selección
                const mesActualFiltro = selectMesFiltro.value;
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

                // Renderizar desglose
                const listaContainer = document.getElementById('listaDesglose');
                listaContainer.innerHTML = '';

                if (data.desglose && data.desglose.length > 0) {
                    data.desglose.forEach(item => {
                        const divItem = document.createElement('div');
                        divItem.className = 'desglose-item';
                        divItem.innerHTML = `
                            <span class="desglose-nombre">${item.categoria}</span>
                            <div class="desglose-valores" style="text-align: right;">
                                <span class="desglose-monto" style="display: block;">${item.monto_uyu}</span>
                                <span class="desglose-pct" style="display: block; margin: 0; font-size: 13px;">${item.monto_usd}</span>
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