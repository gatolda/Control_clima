# Cloud Agent

Cliente en la Raspberry Pi que conecta el sistema local con el backend SaaS
`greenhouse-cloud`.

**Principio de diseño:** si el cloud se cae o no hay internet, **el control local
sigue funcionando**. El agente solo envía telemetría y recibe comandos remotos.

## Componentes

- `config.py` — carga/guarda credenciales del device
- `client.py` — cliente HTTP (telemetria, eventos, comandos, ack)
- `queue.py` — cola persistente SQLite (no se pierde telemetría sin red)
- `agent.py` — loops en threads: telemetry, flush, command-polling
- `activate.py` — script para canjear provisioning_token por device_secret

## Flujo de activación

1. Cliente compra el equipo y crea un device en el dashboard → recibe un **provisioning_token** (QR).
2. Se conecta a la Pi y ejecuta:

   ```bash
   python -m cloud_agent.activate <token>
   ```

3. El script intercambia el token por un `device_secret` permanente y lo
   guarda en `~/.greenhouse-agent/agent.json`.
4. Al reiniciar `app.py`, el agente detecta las credenciales y empieza a publicar.

## Integración con app.py

En `app.py`, después de crear `sensor_reader`, `actuator_manager` y `db`:

```python
from cloud_agent.config import AgentConfig
from cloud_agent.agent import CloudAgent

def _read_sensors_for_cloud():
    """Adapta la lectura local al formato que espera el agente."""
    out = []
    data = sensor_reader.read_all()
    temp = data.get("temperatura_humedad", {}).get("temperature")
    hum = data.get("temperatura_humedad", {}).get("humidity")
    co2 = data.get("co2", {}).get("co2")
    if temp is not None:
        out.append({"variable": "temperatura", "sensor_id": "dht22_1", "value": temp})
    if hum is not None:
        out.append({"variable": "humedad", "sensor_id": "dht22_1", "value": hum})
    if co2 is not None:
        out.append({"variable": "co2", "sensor_id": "mhz19", "value": co2})
    return out

def _toggle_actuator_for_cloud(nombre, accion):
    if accion == "on":
        return actuator_manager.turn_on(nombre)
    return actuator_manager.turn_off(nombre)

agent_config = AgentConfig.load()
cloud_agent = CloudAgent(
    config=agent_config,
    read_sensors=_read_sensors_for_cloud,
    toggle_actuator=_toggle_actuator_for_cloud,
)
cloud_agent.start()  # no-op si no está activado
```

## Resiliencia

- **Sin internet:** la cola SQLite acumula hasta `max_queue_size` items (default 10k, ~6h a 30s de intervalo). Los más viejos se descartan si se llena.
- **Backend caído:** los reintentos son transparentes; no hay cola explícita de comandos porque el polling se reanuda solo.
- **Comando desconocido:** se ackea con `success=false` y mensaje de error, sin crashear.

## Configuración

El archivo `~/.greenhouse-agent/agent.json` luce así:

```json
{
  "api_base_url": "https://api.greenhouse.cloud",
  "device_id": "uuid-del-device",
  "device_secret": "token-secreto-del-device",
  "telemetry_interval_seconds": 30,
  "command_poll_interval_seconds": 10,
  "event_flush_interval_seconds": 15,
  "max_queue_size": 10000
}
```

Se puede sobrescribir con variables de entorno:
- `GREENHOUSE_API_URL`
- `DEVICE_ID`
- `DEVICE_SECRET`
- `AGENT_CONFIG` (ruta del archivo JSON)
