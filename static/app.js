document.getElementById('gasto-form').addEventListener('submit', async function(e) {
    e.preventDefault();

    const concepto = document.getElementById('concepto').value;
    const monto = document.getElementById('monto').value;
    const btn = document.querySelector('.btn-gasto');
    const resultadoDiv = document.getElementById('resultado');

    btn.innerText = "REGISTRANDO...";

    try {
        const respuesta = await fetch('/registrar_gasto', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ concepto: concepto, monto: monto })
        });

        const datos = await respuesta.json();

        if (datos.status === 'success') {
            document.getElementById('gasto-form').reset();
            
            document.getElementById('mensaje-exito').innerText = "¡Gasto registrado!";
            document.getElementById('detalle-categoria').innerText = `Categoría: ${datos.categoria} (${datos.tipo})`;
            resultadoDiv.classList.remove('oculto');
            
            setTimeout(() => {
                resultadoDiv.classList.add('oculto');
            }, 4000);
        } else {
            alert("Error: " + datos.message);
        }
    } catch (error) {
        alert("Hubo un problema de conexión.");
    } finally {
        btn.innerText = "REGISTRAR GASTO";
    }
});