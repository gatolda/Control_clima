/*
 * Greenhouse Sensor Hub v2 — Arduino Mega 2560
 *
 * Lee TODOS los sensores de ambiente y suelo dentro de la carpa,
 * y los envía por USB serial a la Raspberry Pi (que vive afuera).
 *
 * Topología:
 *   Adentro de la carpa  ► Arduino + sensores
 *   Afuera de la carpa   ► Pi + módulo de relés (control)
 *
 * Sensores:
 *   D2  ── DHT22 #1                 (temperatura + humedad, ubicación principal)
 *   D3  ── MH-Z19D PWM out          (CO2; pin de interrupt INT1)
 *   D4  ── DHT22 #2                 (temperatura + humedad, ubicación secundaria)
 *   A0  ── Capacitive soil moisture S1 (esquina sup izq)
 *   A1  ── ...                       S2 (esquina sup der)
 *   A2  ── ...                       S3 (centro fila 2 izq)
 *   A3  ── ...                       S4 (centro fila 2 der)
 *   A4  ── ...                       S5 (esquina inf izq)
 *   A5  ── ...                       S6 (esquina inf der)
 *
 * Protocolo: JSON line-delimited @ 115200 baud
 *
 * Calibración: cada sensor de suelo tiene 2 puntos (raw_dry + raw_field_cap)
 * persistidos en EEPROM. Comandos por serial:
 *   "CAL_DRY soil_s1\n"   → guarda raw actual como punto seco para S1
 *   "CAL_FIELD soil_s1\n" → guarda raw actual como capacidad de campo
 *   "GET_CAL\n"           → lista todas las calibraciones
 *   "RESET_CAL\n"         → vuelve a defaults
 *
 * Libraries requeridas (Library Manager del Arduino IDE):
 *   - DHT sensor library by Adafruit (v1.4.x)
 *   - Adafruit Unified Sensor (dependencia de la anterior)
 */

#include <DHT.h>
#include <EEPROM.h>

// ══════════════════════════════════════════════════════════════
// CONFIG
// ══════════════════════════════════════════════════════════════

const unsigned long SEND_INTERVAL_MS = 5000UL;     // 5s entre envíos
const unsigned long HEARTBEAT_INTERVAL_MS = 30000UL;

// DHT22
#define DHT_PIN_1 2
#define DHT_PIN_2 4
#define DHT_TYPE DHT22

// MH-Z19D (UART via Serial3: D14=TX3 al Rx del sensor, D15=RX3 al Tx del sensor)
// UART es mas preciso que PWM y necesario para que el sensor entre en modo
// "midiendo activamente" (los 2 LEDs encendidos). Power-cycle requerido si
// veniste de modo PWM puro.
#define CO2_SERIAL Serial3
const unsigned long CO2_BAUD = 9600;
const unsigned long CO2_QUERY_INTERVAL_MS = 5000UL;

// Suelo capacitivo
#define SOIL_COUNT 6
const int   SOIL_PINS[SOIL_COUNT]  = { A0, A1, A2, A3, A4, A5 };
const char* SOIL_IDS[SOIL_COUNT]   = { "soil_s1", "soil_s2", "soil_s3", "soil_s4", "soil_s5", "soil_s6" };
const char* SOIL_ZONES[SOIL_COUNT] = { "esq_sup_izq", "esq_sup_der", "centro_izq", "centro_der", "esq_inf_izq", "esq_inf_der" };

// EEPROM layout
#define EEPROM_MAGIC      0xCAFE
#define EEPROM_VERSION    2
#define ADDR_MAGIC        0
#define ADDR_VERSION      2
#define ADDR_CAL_BASE     16  // padding por si agregamos más

// Defaults razonables si EEPROM viene en blanco
const uint16_t DEFAULT_RAW_DRY        = 600;
const uint16_t DEFAULT_RAW_FIELD_CAP  = 320;

// ══════════════════════════════════════════════════════════════
// STATE
// ══════════════════════════════════════════════════════════════

DHT dht1(DHT_PIN_1, DHT_TYPE);
DHT dht2(DHT_PIN_2, DHT_TYPE);

struct SoilCal {
    uint16_t raw_dry;
    uint16_t raw_field_cap;
};
SoilCal calibrations[SOIL_COUNT];

// CO2 UART: ultimo valor leido (consulta cada 5s desde loop)
int  co2_last_ppm  = -1;

unsigned long last_send_ms = 0;
unsigned long last_heartbeat_ms = 0;

// ══════════════════════════════════════════════════════════════
// SETUP & LOOP
// ══════════════════════════════════════════════════════════════

void setup() {
    Serial.begin(115200);
    while (!Serial) { ; }

    dht1.begin();
    dht2.begin();

    CO2_SERIAL.begin(CO2_BAUD);

    for (int i = 0; i < SOIL_COUNT; i++) {
        pinMode(SOIL_PINS[i], INPUT);
    }

    loadCalibrations();

    delay(2500);  // dejar que sensores se estabilicen al arranque

    // Deshabilitar ABC del MH-Z19D al boot. La Auto Baseline Correction asume
    // que el min de 24h = 400 ppm fresh air, y en ambientes mal ventilados
    // (o despues de exposicion a humo) corrompe la baseline y el sensor
    // queda stuck en 5000 ppm. Disable + zero calibration en aire fresco = fix.
    sendMHZCommand(0x79, 0x00);

    Serial.print(F("{\"status\":\"ready\",\"version\":4,\"sensors\":"));
    Serial.print(SOIL_COUNT + 3);
    Serial.println(F("}"));
}

// Manda un comando MH-Z19D con un solo byte de payload (byte 3).
// Para comandos que toman mas data, hay sendMHZCommandFull.
void sendMHZCommand(uint8_t cmd, uint8_t payload) {
    while (CO2_SERIAL.available()) CO2_SERIAL.read();
    uint8_t pkt[9] = { 0xFF, 0x01, cmd, payload, 0, 0, 0, 0, 0 };
    uint8_t sum = 0;
    for (int i = 1; i < 8; i++) sum += pkt[i];
    pkt[8] = (uint8_t)(0xFF - sum + 1);
    CO2_SERIAL.write(pkt, 9);
    CO2_SERIAL.flush();
    // No esperamos respuesta para comandos write (algunos sensores no responden)
}

void loop() {
    if (Serial.available()) {
        handleSerialCommand();
    }

    unsigned long now = millis();

    if (now - last_send_ms >= SEND_INTERVAL_MS) {
        last_send_ms = now;
        last_heartbeat_ms = now;
        sendReadings();
    }

    if (now - last_heartbeat_ms >= HEARTBEAT_INTERVAL_MS) {
        last_heartbeat_ms = now;
        Serial.println(F("{\"heartbeat\":true}"));
    }
}

// ══════════════════════════════════════════════════════════════
// CO2 UART (MH-Z19D)
// ══════════════════════════════════════════════════════════════
// Protocolo: master envia 9 bytes (cmd 0x86 = read CO2), sensor responde
// 9 bytes. ppm = response[2]*256 + response[3]. Checksum byte 8.

bool readCO2_uart(int &ppm) {
    // Vaciar buffer de basura previa
    while (CO2_SERIAL.available()) CO2_SERIAL.read();

    // Comando READ CO2: FF 01 86 00 00 00 00 00 79
    static const uint8_t cmd[9] = { 0xFF, 0x01, 0x86, 0x00, 0x00, 0x00, 0x00, 0x00, 0x79 };
    CO2_SERIAL.write(cmd, 9);
    CO2_SERIAL.flush();

    // Esperar hasta 200ms por los 9 bytes de respuesta
    uint8_t resp[9];
    unsigned long start = millis();
    int got = 0;
    while (got < 9 && (millis() - start) < 200UL) {
        if (CO2_SERIAL.available()) {
            resp[got++] = CO2_SERIAL.read();
        }
    }
    if (got < 9) return false;
    if (resp[0] != 0xFF || resp[1] != 0x86) return false;

    // Checksum: ~(sum bytes 1..7) + 1 == byte 8
    uint8_t sum = 0;
    for (int i = 1; i < 8; i++) sum += resp[i];
    if ((uint8_t)(0xFF - sum + 1) != resp[8]) return false;

    ppm = ((int)resp[2] << 8) | resp[3];
    return true;
}

// ══════════════════════════════════════════════════════════════
// SOIL (capacitive + calibración por sensor)
// ══════════════════════════════════════════════════════════════

int readSoilRaw(int pin) {
    long total = 0;
    for (int i = 0; i < 10; i++) {
        total += analogRead(pin);
        delay(2);
    }
    return total / 10;
}

float soilHumidityPct(int raw, int idx) {
    int dry  = calibrations[idx].raw_dry;
    int wet  = calibrations[idx].raw_field_cap;
    if (dry == wet) return 0.0;
    float pct = (float)(dry - raw) / (float)(dry - wet) * 100.0;
    // Clamp 0-110 (>100 indica sobre-saturación = encharcamiento)
    if (pct < 0)   pct = 0;
    if (pct > 110) pct = 110;
    return pct;
}

int findSoilIndex(const String& id) {
    for (int i = 0; i < SOIL_COUNT; i++) {
        if (id == SOIL_IDS[i]) return i;
    }
    return -1;
}

// ══════════════════════════════════════════════════════════════
// EEPROM CALIBRATION
// ══════════════════════════════════════════════════════════════

void loadCalibrations() {
    uint16_t magic = 0;
    EEPROM.get(ADDR_MAGIC, magic);

    if (magic != EEPROM_MAGIC) {
        // Primera ejecución (EEPROM en blanco), escribir defaults
        for (int i = 0; i < SOIL_COUNT; i++) {
            calibrations[i].raw_dry        = DEFAULT_RAW_DRY;
            calibrations[i].raw_field_cap  = DEFAULT_RAW_FIELD_CAP;
        }
        saveCalibrations();
        EEPROM.put(ADDR_MAGIC, (uint16_t)EEPROM_MAGIC);
        EEPROM.put(ADDR_VERSION, (uint8_t)EEPROM_VERSION);
        return;
    }

    for (int i = 0; i < SOIL_COUNT; i++) {
        EEPROM.get(ADDR_CAL_BASE + i * sizeof(SoilCal), calibrations[i]);
        // Sanity: clamp si EEPROM tiene valores absurdos
        if (calibrations[i].raw_dry == 0 || calibrations[i].raw_dry > 1023 ||
            calibrations[i].raw_field_cap == 0 || calibrations[i].raw_field_cap > 1023) {
            calibrations[i].raw_dry       = DEFAULT_RAW_DRY;
            calibrations[i].raw_field_cap = DEFAULT_RAW_FIELD_CAP;
        }
    }
}

void saveCalibrations() {
    for (int i = 0; i < SOIL_COUNT; i++) {
        EEPROM.put(ADDR_CAL_BASE + i * sizeof(SoilCal), calibrations[i]);
    }
}

// ══════════════════════════════════════════════════════════════
// SERIAL COMMANDS (calibración remota desde la Pi)
// ══════════════════════════════════════════════════════════════

void handleSerialCommand() {
    String cmd = Serial.readStringUntil('\n');
    cmd.trim();
    if (cmd.length() == 0) return;

    if (cmd.startsWith("CAL_DRY ")) {
        String id = cmd.substring(8);
        int idx = findSoilIndex(id);
        if (idx < 0) {
            Serial.print(F("{\"error\":\"unknown_sensor\",\"id\":\""));
            Serial.print(id); Serial.println(F("\"}"));
            return;
        }
        int raw = readSoilRaw(SOIL_PINS[idx]);
        calibrations[idx].raw_dry = raw;
        saveCalibrations();
        Serial.print(F("{\"calibrated\":\""));
        Serial.print(id);
        Serial.print(F("\",\"point\":\"dry\",\"raw\":"));
        Serial.print(raw);
        Serial.println(F("}"));
    }
    else if (cmd.startsWith("CAL_FIELD ")) {
        String id = cmd.substring(10);
        int idx = findSoilIndex(id);
        if (idx < 0) {
            Serial.print(F("{\"error\":\"unknown_sensor\",\"id\":\""));
            Serial.print(id); Serial.println(F("\"}"));
            return;
        }
        int raw = readSoilRaw(SOIL_PINS[idx]);
        calibrations[idx].raw_field_cap = raw;
        saveCalibrations();
        Serial.print(F("{\"calibrated\":\""));
        Serial.print(id);
        Serial.print(F("\",\"point\":\"field\",\"raw\":"));
        Serial.print(raw);
        Serial.println(F("}"));
    }
    else if (cmd == "GET_CAL") {
        sendCalibrations();
    }
    else if (cmd == "RESET_CAL") {
        for (int i = 0; i < SOIL_COUNT; i++) {
            calibrations[i].raw_dry        = DEFAULT_RAW_DRY;
            calibrations[i].raw_field_cap  = DEFAULT_RAW_FIELD_CAP;
        }
        saveCalibrations();
        Serial.println(F("{\"reset\":true}"));
    }
    else if (cmd == "CO2_ABC_OFF") {
        sendMHZCommand(0x79, 0x00);
        Serial.println(F("{\"mhz_abc\":\"off\"}"));
    }
    else if (cmd == "CO2_ABC_ON") {
        sendMHZCommand(0x79, 0xA0);
        Serial.println(F("{\"mhz_abc\":\"on\"}"));
    }
    else if (cmd == "CO2_CAL_ZERO") {
        // PELIGRO: solo usar si el sensor lleva 20+ min en aire fresco (~400 ppm).
        // Esto re-calibra el zero del sensor al valor actual asumiendo 400 ppm.
        sendMHZCommand(0x87, 0x00);
        Serial.println(F("{\"mhz_zero_cal\":\"sent\"}"));
    }
    else {
        Serial.print(F("{\"error\":\"unknown_command\",\"cmd\":\""));
        Serial.print(cmd);
        Serial.println(F("\"}"));
    }
}

void sendCalibrations() {
    Serial.print(F("{\"calibrations\":["));
    for (int i = 0; i < SOIL_COUNT; i++) {
        if (i > 0) Serial.print(F(","));
        Serial.print(F("{\"id\":\""));
        Serial.print(SOIL_IDS[i]);
        Serial.print(F("\",\"dry\":"));
        Serial.print(calibrations[i].raw_dry);
        Serial.print(F(",\"field\":"));
        Serial.print(calibrations[i].raw_field_cap);
        Serial.print(F("}"));
    }
    Serial.println(F("]}"));
}

// ══════════════════════════════════════════════════════════════
// SEND READINGS (JSON)
// ══════════════════════════════════════════════════════════════

void sendReadings() {
    float temp_c_1 = dht1.readTemperature();
    float hum_1    = dht1.readHumidity();
    float temp_c_2 = dht2.readTemperature();
    float hum_2    = dht2.readHumidity();

    int co2_value = -1;
    if (readCO2_uart(co2_value)) {
        co2_last_ppm = co2_value;
    }
    int co2 = co2_last_ppm;

    Serial.print(F("{\"sensors\":["));
    bool first = true;

    // DHT22 #1 - temperature
    if (!isnan(temp_c_1)) {
        Serial.print(F("{\"id\":\"dht22_1\",\"type\":\"temperature\",\"value\":"));
        Serial.print(temp_c_1, 1);
        Serial.print(F("}"));
        first = false;
    }

    // DHT22 #1 - humidity
    if (!isnan(hum_1)) {
        if (!first) Serial.print(F(","));
        Serial.print(F("{\"id\":\"dht22_1\",\"type\":\"humidity\",\"value\":"));
        Serial.print(hum_1, 1);
        Serial.print(F("}"));
        first = false;
    }

    // DHT22 #2 - temperature
    if (!isnan(temp_c_2)) {
        if (!first) Serial.print(F(","));
        Serial.print(F("{\"id\":\"dht22_2\",\"type\":\"temperature\",\"value\":"));
        Serial.print(temp_c_2, 1);
        Serial.print(F("}"));
        first = false;
    }

    // DHT22 #2 - humidity
    if (!isnan(hum_2)) {
        if (!first) Serial.print(F(","));
        Serial.print(F("{\"id\":\"dht22_2\",\"type\":\"humidity\",\"value\":"));
        Serial.print(hum_2, 1);
        Serial.print(F("}"));
        first = false;
    }

    // MH-Z19D
    if (co2 >= 0) {
        if (!first) Serial.print(F(","));
        Serial.print(F("{\"id\":\"mhz19_1\",\"type\":\"co2\",\"value\":"));
        Serial.print(co2);
        Serial.print(F("}"));
        first = false;
    }

    // Soil sensors
    for (int i = 0; i < SOIL_COUNT; i++) {
        int raw = readSoilRaw(SOIL_PINS[i]);
        float pct = soilHumidityPct(raw, i);
        bool calibrated = (calibrations[i].raw_dry != DEFAULT_RAW_DRY ||
                           calibrations[i].raw_field_cap != DEFAULT_RAW_FIELD_CAP);

        if (!first) Serial.print(F(","));
        Serial.print(F("{\"id\":\""));
        Serial.print(SOIL_IDS[i]);
        Serial.print(F("\",\"type\":\"humidity\",\"zone\":\""));
        Serial.print(SOIL_ZONES[i]);
        Serial.print(F("\",\"value\":"));
        Serial.print(pct, 1);
        Serial.print(F(",\"raw\":"));
        Serial.print(raw);
        Serial.print(F(",\"dry\":"));
        Serial.print(calibrations[i].raw_dry);
        Serial.print(F(",\"field\":"));
        Serial.print(calibrations[i].raw_field_cap);
        Serial.print(F(",\"calibrated\":"));
        Serial.print(calibrated ? F("true") : F("false"));
        Serial.print(F("}"));
        first = false;
    }

    Serial.println(F("]}"));
}
