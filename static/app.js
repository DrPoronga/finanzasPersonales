document.addEventListener("DOMContentLoaded", () => {
    // Vistas y Menú
    const btnMenu = document.getElementById('btnMenu');
    const btnCloseMenu = document.getElementById('btnCloseMenu');
    const sideMenu = document.getElementById('sideMenu');
    const overlay = document.getElementById('overlay');
    
    const menuRegistrar = document.getElementById('menuRegistrar');
    const menuMetricas = document.getElementById('menuMetricas');
    const vistaRegistrar = document.getElementById('vistaRegistrar');
    const vistaMetricas = document.getElementById('vistaMetricas');

    // Elementos del Formulario
    const form = document.getElementById('gastoForm');
    const conceptoInput = document.getElementById('concepto');
    const montoInput = document.getElementById('monto');
    const btnSubmit = document.getElementById('btnSubmit');
    const mensajeDiv = document.getElementById('mensaje');

    // Modal
    const modal = document.getElementById('modalCategoria');
    const conceptoModal = document.getElementById('conceptoModal');
    const selectCategoria = document.getElementById('selectCategoria');
    const btnGuardarCategoria = document.getElementById('btnGuardarCategoria');
    const btnCancelarModal = document.getElementById('btnCancelarModal');

    let gastoPendiente = null;

    // --- MANEJO DEL MENU HAMBURGUESA ---
    function toggleMenu() {
        sideMenu.classList.toggle('hidden');
        overlay.classList.toggle('hidden');
    }

    btnMenu.addEventListener('click', toggleMenu);
    btnCloseMenu.addEventListener('click', toggleMenu);
    overlay.addEventListener('click', toggleMenu);

    // Navegación entre Vistas
    menuRegistrar.addEventListener('click', (e) => {
        e.preventDefault();
        vistaRegistrar.classList.remove('hidden');
        vistaMetricas.classList.add('hidden');
        menuRegistrar.classList.add('active');
        menuMetricas.classList.remove('active');
        toggleMenu();
    });

    menuMetricas.addEventListener('click', (e) => {
        e.preventDefault();
        vistaMetricas.classList.remove('hidden');
        vistaRegistrar.classList.add('hidden');
        menuMetricas.classList.add('active');
        menuRegistrar.classList.remove('active');
        toggleMenu();
        cargarMetricas();
    });

    document.getElementById('btnActualizarMetricas').addEventListener('click', cargarMetricas);

    // --- Cargar Métricas desde Backend ---
    async function cargarMetricas() {
        try {
            const res = await fetch('/obtener_metricas');
            const data = await res.json();
            if(data.status === 'success') {
                document.getElementById('lblBalance').textContent = data.balance;
                document.getElementById('lblIngresos').textContent = data.ingresos;
                document.getElementById('lblGastos').textContent = data.gastos;
            }
        } catch(e) {
            console.error("Error cargando métricas:", e);
        }
    }

    // --- ENVIAR MOVIMIENTO ---
    form.addEventListener('submit', async (e) => {
        e.preventDefault();
        const concepto = conceptoInput.value.trim();
        const monto = parseFloat(montoInput.value);
        const tipo = document.querySelector('input[name="tipoMovimiento"]:checked').value;

        if (!concepto || isNaN(monto) || monto <= 0) return;

        gastoPendiente = { concepto, monto, tipo };
        enviarGasto(gastoPendiente);
    });

    async function enviarGasto(datos) {
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
                mostrarMensaje(`¡Registrado! (${data.tipo}: ${data.categoria})`, 'success');
                form.reset();
                gastoPendiente = null;
                btnSubmit.disabled = false;
            }
        } catch (error) {
            mostrarMensaje('Error de conexión.', 'error');
            btnSubmit.disabled = false;
        }
    }

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
            enviarGasto(gastoPendiente);
        }
    });

    btnCancelarModal.addEventListener('click', () => {
        modal.classList.add('hidden');
        gastoPendiente = null;
        btnSubmit.disabled = false;
    });

    function mostrarMensaje(texto, tipo) {
        mensajeDiv.textContent = texto;
        mensajeDiv.className = tipo;
        setTimeout(() => { mensajeDiv.className = 'hidden'; }, 4000);
    }
});