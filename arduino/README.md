# Greenhouse Sensor Hub — Arduino Mega 2560

Sketch que lee TODOS los sensores ambientales y de suelo de la carpa y los envía
a la Raspberry Pi por USB serial. La Pi se encarga del control (relés) — el
Arduino solo lee.

## Topología

```
ADENTRO de la carpa  ►  Arduino Mega + sensores
AFUERA de la carpa   ►  Pi + módulo de relés (control 220V)
```

Esta separación es por **durabilidad**: la Pi (con SD card sensible a humedad +
calor) vive afuera en una cajita protegida. El Arduino vive adentro, donde es
mucho más barato reemplazar (~5 USD vs ~50 USD de la Pi) si el ambiente lo daña.

## Sensores soportados (sketch v2)

| Pin    | Sensor              | Notas                                    |
|--------|---------------------|------------------------------------------|
| D2     | DHT22               | Temperatura + humedad. Pull-up 10kΩ a 5V (si el módulo no lo trae) |
| D3     | MH-Z19D PWM         | CO2. Pin INT1 — usa interrupt para timing preciso |
| A0     | Soil moisture S1    | Esquina superior izquierda |
| A1     | Soil moisture S2    | Esquina superior derecha |
| A2     | Soil moisture S3    | Centro fila 2 izquierda |
| A3     | Soil moisture S4    | Centro fila 2 derecha |
| A4     | Soil moisture S5    | Esquina inferior izquierda |
| A5     | Soil moisture S6    | Esquina inferior derecha |

Pines libres para futuros sensores: A6-A15 (10 entradas analógicas) + casi todos
los digitales D4-D53.

## Librerías requeridas

Instalar desde el **Library Manager del Arduino IDE** (Sketch → Include Library
→ Manage Libraries):

- **DHT sensor library** by Adafruit (v1.4.x o superior)
- **Adafruit Unified Sensor** (dependencia de la anterior, suele instalar sola)

EEPROM ya viene con el Arduino IDE, no requiere instalación.

## Cómo flashear

1. Conecta el Arduino Mega al computer via USB
2. Arduino IDE → **Tools → Board** → "Arduino Mega 2560"
3. Tools → Port → el puerto que aparece (Windows: `COM3` típico, Linux/Mac:
   `/dev/ttyACM0` o similar)
4. Abrir `greenhouse_sensors.ino`
5. **Verify** (✓) → debe compilar sin errores
6. **Upload** (→) → tarda ~30s
7. **Serial Monitor** (lupa arriba a la derecha) @ 115200 baud → deberías ver
   líneas JSON cada 5s tipo:
   ```json
   {"sensors":[{"id":"dht22_1","type":"temperature","value":22.5},...]}
   ```

## Calibración de sensores de suelo

**Fundamental hacer esto antes de confiar en lecturas de humedad.**

El sketch usa **2 puntos de calibración por sensor** persistidos en EEPROM:

- `raw_dry`: lectura ADC con sustrato bone-dry (deshidratado o en aire). 0% humedad útil.
- `raw_field_cap`: lectura ADC con sustrato a **capacidad de campo** (saturado
  pero drenado, después de regar abundante + 1h). 100% humedad útil.

La fórmula que usa el sketch:

```
% humedad útil = (raw_dry - raw_actual) / (raw_dry - raw_field_cap) × 100
```

### Por qué NO calibramos sumergiendo en agua

Los tutoriales típicos calibran "100% = sensor sumergido". Eso está mal para
agricultura — sumergido = encharcado = root rot. **Capacidad de campo** es el
estado óptimo para plantas, y por eso es nuestro 100%.

Si el sensor lee >100% en operación, significa que el sustrato está
sobre-saturado (encharcado) — el sistema te alerta.

### Flow de calibración

**Vía la página web** (recomendado, en `/calibrate`):

1. Login al dashboard
2. Sidebar → "Calibración"
3. Por cada sensor (S1-S6):
   - **Punto SECO**: poné el sensor en sustrato seco al aire o sustrato 100%
     deshidratado. Click "Set DRY".
   - **Punto FIELD**: insertá el sensor a la profundidad de uso (3-5cm), riega
     la maceta hasta runoff, esperá 1h, click "Set FIELD".
4. Después de calibrar ambos puntos por sensor, el card cambia de fondo amber
   a normal y la lectura % es confiable.

**Vía Serial Monitor** (debug):

Conectado al Arduino vía USB, podés mandar comandos directamente:

```
CAL_DRY soil_s1
CAL_FIELD soil_s1
GET_CAL
RESET_CAL
```

El Arduino responde con JSON confirmando la operación.

### Recomendaciones

- **Marca el sensor con cinta** a la profundidad de uso (ej. 5cm) para insertar
  siempre igual.
- **Re-calibrá entre ciclos** — sustrato nuevo tiene comportamiento dieléctrico
  distinto.
- **No calibres bajo luz directa de cultivo** — temperatura puede afectar
  lecturas. Calibrá a temperatura típica de operación.
- **Verifica coherencia**: el rango `dry - field` debería ser >150 unidades
  ADC. Si es <100, el sensor puede estar dañado.

## Migration desde sketch v1

Si veniste del sketch viejo (solo soil sensor en A0):

1. **Backup** del `config.yml` actual (lo vamos a modificar después)
2. Cableá los nuevos sensores siguiendo la tabla de pines arriba
3. Flashea `greenhouse_sensors.ino` (sketch v2). El sketch detecta
   automáticamente que la EEPROM está virgen y escribe defaults.
4. **NO modifiques `config.yml` todavía** — la Pi sigue leyendo DHT22 y
   MH-Z19D directamente vía GPIO. El Arduino los está leyendo en paralelo
   pero la Pi los ignora.
5. **Verifica via Serial Monitor del Arduino IDE** que están llegando todas
   las lecturas:
   ```
   {"sensors":[{"id":"dht22_1","type":"temperature","value":22.4}, ...]}
   ```
6. **Calibra los 6 sensores de suelo** vía /calibrate (con la Pi conectada).
7. **Cuando todo funcione**, modificá `config.yml` para cambiar DHT22 y CO2
   a tipo `ARDUINO_SERIAL`:

```yaml
sensores:
  temperatura:
    - id: "dht22_1"
      tipo: ARDUINO_SERIAL
      arduino_field: "temperature"
      ubicacion: "centro"

  humedad:
    - id: "dht22_1"
      tipo: ARDUINO_SERIAL
      arduino_field: "humidity"
      ubicacion: "centro"

  co2:
    - id: "mhz19_1"
      tipo: ARDUINO_SERIAL
      arduino_field: "co2"
      ubicacion: "centro"

  humedad_suelo:
    - id: "soil_s1"
      tipo: ARDUINO_SERIAL
      arduino_field: "humidity"
      zona: "esq_sup_izq"
    - id: "soil_s2"
      tipo: ARDUINO_SERIAL
      arduino_field: "humidity"
      zona: "esq_sup_der"
    - id: "soil_s3"
      tipo: ARDUINO_SERIAL
      arduino_field: "humidity"
      zona: "centro_izq"
    - id: "soil_s4"
      tipo: ARDUINO_SERIAL
      arduino_field: "humidity"
      zona: "centro_der"
    - id: "soil_s5"
      tipo: ARDUINO_SERIAL
      arduino_field: "humidity"
      zona: "esq_inf_izq"
    - id: "soil_s6"
      tipo: ARDUINO_SERIAL
      arduino_field: "humidity"
      zona: "esq_inf_der"

arduino:
  puerto: "/dev/arduino-soil"   # symlink udev existente, podés renombrar a arduino-sensors
  baudrate: 115200
  timeout: 2
```

8. `sudo systemctl restart greenhouse.service` y verificá en `/diagnostics`
   que ahora todos los sensores leen via Arduino (campo `tipo` debe decir
   ARDUINO_SERIAL).

9. **Liberá los pines BCM 4 y BCM 17 de la Pi** (DHT22 y CO2 antiguos) — quedan
   disponibles para futuras expansiones (botón emergencia, LED status, etc.).

## Hardware shopping list (para topología completa)

Ya tenés (probablemente):
- Arduino Mega 2560 ✓
- DHT22 ✓
- MH-Z19D ✓
- 1x sensor capacitivo de suelo ✓ (en A0)

Faltarían para completar el setup recomendado de 6 sensores de suelo:
- 5x sensores capacitivos de suelo v2.0 (~$3 c/u en AliExpress / Mercado Libre)
- Cable plano de 6+ hilos (1m) o cable Cat5/Cat6 para cableado limpio
- Resistencia 10kΩ (si tu DHT22 no trae módulo con pull-up incorporado)

Total estimado: ~15-20 USD adicionales.

## Troubleshooting

**Arduino no aparece en `/dev/arduino-soil`:**
- Verificá la regla udev: `ls -la /etc/udev/rules.d/99-arduino-soil.rules`
- Forzá reload: `sudo udevadm control --reload-rules && sudo udevadm trigger`
- Lista USB devices: `ls /dev/ttyUSB*` o `lsusb` para ver si el chip CH340 está detectado

**No hay lecturas DHT22 (NaN):**
- Verificá pull-up en pin de datos
- DHT22 necesita >2s entre lecturas — el sketch ya lo hace, pero si el Mega arranca y leés inmediatamente puede dar NaN inicial
- Probá cable más corto (DHT22 sufre con cables largos sin shielding)

**CO2 reporta -1:**
- El MH-Z19D tarda ~3 minutos en calentar después de power-on. Es normal el -1 al principio.
- Verificá que el pin PWM esté en D3 (no D2 que es DHT22)
- El sensor necesita 5V — verificá voltaje

**Lecturas de soil dan 0% o 100% siempre:**
- Probablemente sin calibrar (defaults raros). Hacé calibración.
- Verificá que el sensor está en V2.0 (capacitivo). V1.x (resistivos) no son compatibles con esta fórmula.
