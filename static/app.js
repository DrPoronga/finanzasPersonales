document.getElementById('gasto-form').addEventListener('submit', async function(e) {
    e.preventDefault(); // Evita que la página se recargue

    // Capturamos los valores
    const concepto = document.getElementById('concepto').value;
    const monto = document.getElementById('monto').value;
    const btn = document.querySelector('.btn-gasto');

    // Cambiamos el texto del botón mientras carga
    btn.innerText = "REGISTRANDO...";

    try {
        // Enviamos los datos al backend (Python)
        const respuesta = await fetch('/registrar_gasto', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ concepto: concepto, monto: monto })
        });

        const datos = await respuesta.json();

        if (datos.status === 'success') {
            // Mostramos mensaje de éxito y vaciamos los campos
            document.getElementById('gasto-form').reset();
            const mensaje = document.getElementById('mensaje-exito');
            mensaje.style.display = 'block';
            
            // Ocultamos el mensaje a los 3 segundos
            setTimeout(() => {
                mensaje.style.display = 'none';
            }, 3000);
        }
    } catch (error) {
        alert("Hubo un error al registrar el gasto.");
    } finally {
        btn.innerText = "REGISTRAR GASTO";
    }
});