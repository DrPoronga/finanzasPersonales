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
    const btnGuardarCategoria = document.getElementById('btnGuardarCategoria');
    const btnCancelarModal = document.getElementById('btnCancelarModal');

    // Estado global: por defecto es Gasto ("Pasivo")
    let tipoActual = "Pasivo";
    let gastoPendiente = null;

    // --- MENÚ Y NAVEGACIÓN ---
    function toggleMenu() {
        sideMenu.classList.toggle('hidden');
        overlay.classList.toggle('hidden');
    }

    btnMenu.addEventListener('click', toggleMenu);
    btnCloseMenu.addEventListener('click', toggleMenu);
    overlay.addEventListener('click', toggleMenu);

    // Preparar app para Gasto
    menuGasto.addEventListener('click', (e) => {
        e.preventDefault();
        tipoActual = "Pasivo";
        btnSubmit.textContent = "Registrar Gasto";
        mostrarVista(vistaFormulario);
        activarMenu(menuGasto);
        toggleMenu();
    });

    // Preparar app para Ingreso
    menuIngreso.addEventListener('click', (e) => {
        e.preventDefault();
        tipoActual = "Activo";
        btnSubmit.textContent = "Registrar Ingreso";
        mostrarVista(vistaFormulario);
        activarMenu(menuIngreso);
        toggleMenu();
    });

    // Mostrar métricas
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

    // --- MÉTRICAS ---
    async function cargarMetricas() {
        try {
            const res = await fetch('/obtener_metricas');
            const data = await res.json();
            if (data.status === 'success') {
                document.getElementById('lblBalance').textContent = data.balance;
                document.getElementById('lblIngresos').textContent = data.ingresos;
                document.getElementById('lblGastos').textContent = data.gastos;
            }
        } catch (error) {
            console.error("Error al cargar métricas", error);
        }
    }

    // --- ENVÍO DE FORMULARIO ---
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

    // --- MODAL ---
    function abrirModal(concepto, categoriasDisponibles) {
        conceptoModal.textContent = concepto;
        selectCategoria.innerHTML = '';
        categoriasDisponibles.forEach(cat => {
            const opt = document.createElement('option');
            opt.value = cat; opt.textContent = cat;
            selectCategoria.appendChild(opt);
        });
        modal.classList.remove('hidden');
    }

    btnGuardarCategoria.addEventListener('click', () => {
        if (gastoPendiente) {
            gastoPendiente.nueva_categoria = selectCategoria.value;
            modal.classList.add('hidden');
            enviarMovimiento(gastoPendiente);
        }
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