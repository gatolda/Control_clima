async function actualizarSensores() {
    try {
        const response = await fetch("/api/sensores");
        const datos = await response.json();

        document.getElementById("temp").textContent = datos.temperatura_humedad.temperature || "--";
        document.getElementById("hum").textContent = datos.temperatura_humedad.humidity || "--";
        document.getElementById("co2").textContent = datos.co2.co2 || "--";
    } catch (error) {
        console.error("Error obteniendo sensores:", error);
    }
}

async function toggleActuador(actuador, accion) {
    try {
        await fetch(`/api/actuadores/${actuador}`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ accion })
        });
    } catch (error) {
        console.error("Error cambiando actuador:", error);
    }
}

// Crea los botones
function crearBotones() {
    const actuadores = [
        "ventiladores", "filtro_carbon", "intractor",
        "humidificador", "deshumidificador", "luz",
        "calefactor", "aire_acondicionado", "ozono"
    ];

    const botonesDiv = document.getElementById("botones");

    actuadores.forEach(nombre => {
        const contenedor = document.createElement("div");
        contenedor.innerHTML = `
            <strong>${nombre}</strong>
            <button onclick="toggleActuador('${nombre}', 'on')">ON</button>
            <button onclick="toggleActuador('${nombre}', 'off')">OFF</button>
        `;
        botonesDiv.appendChild(contenedor);
    });
}

crearBotones();
setInterval(actualizarSensores, 5000); // Actualiza cada 5 seg
