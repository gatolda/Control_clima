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
 *   D2  ── DHT22                    (temperatura + humedad)
 *   D3  ── MH-Z19D PWM out          (CO2; pin de interrupt INT1)
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
#define DHT_PIN 2
#define DHT_TYPE DHT22

// MH-Z19D (PWM)
#define CO2_PWM_PIN 3
const long CO2_RANGE_PPM = 5000;  // datasheet: rango 0-5000 ppm

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

DHT dht(DHT_PIN, DHT_TYPE);

struct SoilCal {
    uint16_t raw_dry;
    uint16_t raw_field_cap;
};
SoilCal calibrations[SOIL_COUNT];

// CO2 PWM medido por interrupt (asincrono)
volatile unsigned long co2_high_us  = 0;
volatile unsigned long co2_total_us = 0;
volatile unsigned long co2_last_rise_us = 0;
volatile bool          co2_ready    = false;

unsigned long last_send_ms = 0;
unsigned long last_heartbeat_ms = 0;

// ══════════════════════════════════════════════════════════════
// SETUP & LOOP
// ══════════════════════════════════════════════════════════════

void setup() {
    Serial.begin(115200);
    while (!Serial) { ; }

    dht.begin();

    pinMode(CO2_PWM_PIN, INPUT);
    attachInterrupt(digitalPinToInterrupt(CO2_PWM_PIN), co2_isr, CHANGE);

    for (int i = 0; i < SOIL_COUNT; i++) {
        pinMode(SOIL_PINS[i], INPUT);
    }

    loadCalibrations();

    delay(2500);  // dejar que sensores se estabilicen al arranque
    Serial.print(F("{\"status\":\"ready\",\"version\":2,\"sensors\":"));
    Serial.print(SOIL_COUNT + 2);
    Serial.println(F("}"));
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
// CO2 PWM (MH-Z19D)
// ══════════════════════════════════════════════════════════════

void co2_isr() {
    unsigned long now = micros();
    if (digitalRead(CO2_PWM_PIN) == HIGH) {
        // rising edge
        if (co2_last_rise_us > 0) {
            co2_total_us = now - co2_last_rise_us;
        }
        co2_last_rise_us = now;
    } else {
        // falling edge
        if (co2_last_rise_us > 0) {
            co2_high_us = now - co2_last_rise_us;
            co2_ready = true;
        }
    }
}

int readCO2() {
    // MH-Z19D: 1 Hz cycle, ppm = range * (high_ms - 2) / (cycle_ms - 4)
    if (!co2_ready) return -1;

    noInterrupts();
    unsigned long high_us  = co2_high_us;
    unsigned long total_us = co2_total_us;
    interrupts();

    if (total_us < 900000UL || total_us > 1100000UL) return -1;  // ciclo no es ~1Hz

    long ppm = CO2_RANGE_PPM * ((long)high_us - 2000L) / ((long)total_us - 4000L);
    if (ppm < 0) ppm = 0;
    if (ppm > CO2_RANGE_PPM) ppm = CO2_RANGE_PPM;
    return (int)ppm;
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
    float temp_c = dht.readTemperature();
    float hum    = dht.readHumidity();
    int   co2    = readCO2();

    Serial.print(F("{\"sensors\":["));
    bool first = true;

    // DHT22 - temperature
    if (!isnan(temp_c)) {
        Serial.print(F("{\"id\":\"dht22_1\",\"type\":\"temperature\",\"value\":"));
        Serial.print(temp_c, 1);
        Serial.print(F("}"));
        first = false;
    }

    // DHT22 - humidity
    if (!isnan(hum)) {
        if (!first) Serial.print(F(","));
        Serial.print(F("{\"id\":\"dht22_1\",\"type\":\"humidity\",\"value\":"));
        Serial.print(hum, 1);
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
