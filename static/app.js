document.addEventListener("DOMContentLoaded", () => {
    const btnMenu = document.getElementById('btnMenu');
    const btnCloseMenu = document.getElementById('btnCloseMenu');
    const sideMenu = document.getElementById('sideMenu');
    const overlay = document.getElementById('overlay');
    
    const menuGasto = document.getElementById('menuGasto');
    const menuIngreso = document.getElementById('menuIngreso');
    const menuMetricas = document.getElementById('menuMetricas');
    
    const vistaFormulario = document.getElementById('vistaFormulario');
    const vistaMetricas = document.getElementById('vistaMetricas');

    const form = document.getElementById('registroForm');
    const conceptoInput = document.getElementById('concepto');
    const montoInput = document.getElementById('monto');
    const btnSubmit = document.getElementById('btnSubmit');
    const mensajeDiv = document.getElementById('mensaje');

    const modal = document.getElementById('modalCategoria');
    const conceptoModal = document.getElementById('conceptoModal');
    const selectCategoria = document.getElementById('selectCategoria');
    const containerNuevaCategoria = document.getElementById('containerNuevaCategoria');
    const inputNuevaCategoria = document.getElementById('inputNuevaCategoria');
    const btnGuardarCategoria = document.getElementById('btnGuardarCategoria');
    const btnCancelarModal = document.getElementById('btnCancelarModal');

    let tipoActual = "Pasivo";
    let gastoPendiente = null;

    // --- NAV Y MENÚ ---
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
        mostrarVista(vistaFormulario);
        activarMenu(menuGasto);
        toggleMenu();
    });

    menuIngreso.addEventListener('click', (e) => {
        e.preventDefault();
        tipoActual = "Activo";
        btnSubmit.textContent = "Registrar Ingreso";
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

    document.getElementById('btnActualizarMetricas').addEventListener('click', cargarMetricas);

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

    // --- CARGAR MÉTRICAS AMPLIADAS ---
    async function cargarMetricas() {
        try {
            const res = await fetch('/obtener_metricas');
            const data = await res.json();
            if (data.status === 'success') {
                document.getElementById('lblBalance').textContent = data.balance;
                document.getElementById('lblIngresos').textContent = data.ingresos;
                document.getElementById('lblGastos').textContent = data.gastos;
                document.getElementById('lblTasaAhorro').textContent = data.tasa_ahorro;
                document.getElementById('lblGastoDiario').textContent = data.gasto_diario;
                document.getElementById('lblTopCategoria').textContent = data.top_categoria;

                // Renderizar desglose por categoría
                const listaContainer = document.getElementById('listaDesglose');
                listaContainer.innerHTML = '';

                if (data.desglose && data.desglose.length > 0) {
                    data.desglose.forEach(item => {
                        const divItem = document.createElement('div');
                        divItem.className = 'desglose-item';
                        divItem.innerHTML = `
                            <span class="desglose-nombre">${item.categoria}</span>
                            <div class="desglose-valores">
                                <span class="desglose-monto">${item.monto}</span>
                                <span class="desglose-pct">(${item.porcentaje})</span>
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

    // --- ENVIAR MOVIMIENTO ---
    form.addEventListener('submit', (e) => {
        e.preventDefault();
        const concepto = conceptoInput.value.trim();
        const monto = parseFloat(montoInput.value);

        if (!concepto || isNaN(monto) || monto <= 0) return;

        gastoPendiente = { concepto, monto, tipo: tipoActual };
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

            const data = await response.json();

            if (data.status === 'needs_category') {
                abrirModal(datos.concepto, data.categorias);
            } else if (data.status === 'success') {
                mostrarMensaje(`Registrado correctamente`, 'success');
                form.reset();
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

    // --- MODAL Y NUEVAS CATEGORÍAS ---
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