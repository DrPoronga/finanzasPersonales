document.addEventListener("DOMContentLoaded", () => {
    const form = document.getElementById('gastoForm');
    const conceptoInput = document.getElementById('concepto');
    const montoInput = document.getElementById('monto');
    const btnSubmit = document.getElementById('btnSubmit');
    const mensajeDiv = document.getElementById('mensaje');

    // Elementos del Modal
    const modal = document.getElementById('modalCategoria');
    const conceptoModal = document.getElementById('conceptoModal');
    const selectCategoria = document.getElementById('selectCategoria');
    const btnGuardarCategoria = document.getElementById('btnGuardarCategoria');
    const btnCancelarModal = document.getElementById('btnCancelarModal');

    // Aquí guardamos el gasto en pausa mientras le preguntamos al usuario
    let gastoPendiente = null;

    form.addEventListener('submit', async (e) => {
        e.preventDefault();
        
        const concepto = conceptoInput.value.trim();
        const monto = parseFloat(montoInput.value);

        if (!concepto || isNaN(monto) || monto <= 0) {
            mostrarMensaje('Por favor, ingresa datos válidos.', 'error');
            return;
        }

        gastoPendiente = { concepto, monto };
        enviarGasto(gastoPendiente);
    });

    async function enviarGasto(datos) {
        btnSubmit.textContent = "Procesando...";
        btnSubmit.disabled = true;
        mensajeDiv.className = "hidden";

        try {
            const response = await fetch('/registrar_gasto', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(datos)
            });

            const data = await response.json();

            if (data.status === 'needs_category') {
                // El backend no conoce este gasto, abrimos el modal
                abrirModal(datos.concepto, data.categorias);
            } else if (data.status === 'success') {
                // Se guardó perfecto
                mostrarMensaje(`¡Guardado! (Categoría: ${data.categoria})`, 'success');
                form.reset();
                gastoPendiente = null; // Limpiamos
                btnSubmit.textContent = "Registrar Gasto";
                btnSubmit.disabled = false;
            } else {
                mostrarMensaje(`Error: ${data.message}`, 'error');
                btnSubmit.textContent = "Registrar Gasto";
                btnSubmit.disabled = false;
            }
        } catch (error) {
            mostrarMensaje('Error de conexión con el servidor.', 'error');
            btnSubmit.textContent = "Registrar Gasto";
            btnSubmit.disabled = false;
        }
    }

    function abrirModal(concepto, categoriasDisponibles) {
        conceptoModal.textContent = concepto;
        
        // Limpiar opciones anteriores
        selectCategoria.innerHTML = '';
        
        // Llenar con las categorías que mandó el bot desde Google Sheets
        categoriasDisponibles.forEach(cat => {
            const option = document.createElement('option');
            option.value = cat;
            option.textContent = cat;
            selectCategoria.appendChild(option);
        });

        // Agregamos Varios al final por las dudas
        const optionVarios = document.createElement('option');
        optionVarios.value = "Varios";
        optionVarios.textContent = "Varios";
        selectCategoria.appendChild(optionVarios);

        // Mostrar la ventana
        modal.classList.remove('hidden');
    }

    // Botón Aprender del Modal
    btnGuardarCategoria.addEventListener('click', () => {
        const categoriaElegida = selectCategoria.value;
        if (gastoPendiente) {
            // Le inyectamos la categoría que el usuario eligió y lo reenviamos
            gastoPendiente.nueva_categoria = categoriaElegida;
            modal.classList.add('hidden');
            enviarGasto(gastoPendiente);
        }
    });

    // Botón Cancelar del Modal
    btnCancelarModal.addEventListener('click', () => {
        modal.classList.add('hidden');
        gastoPendiente = null;
        btnSubmit.textContent = "Registrar Gasto";
        btnSubmit.disabled = false;
    });

    function mostrarMensaje(texto, tipo) {
        mensajeDiv.textContent = texto;
        mensajeDiv.className = tipo; // 'success' o 'error'
        
        // El mensaje desaparece a los 4 segundos
        setTimeout(() => {
            mensajeDiv.className = 'hidden';
        }, 4000);
    }
});