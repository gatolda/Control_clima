/*
 * Greenhouse Soil Sensors Hub
 * Lee sensores de humedad y pH de suelo, envia JSON por serial.
 *
 * Hardware:
 * - Arduino Mega 2560 (recomendado por cantidad de pines analogicos)
 * - Sensores capacitivos de humedad de suelo (A0-A14)
 * - Sensores de pH (A15+)
 *
 * Protocolo:
 * - Envia JSON cada 2 segundos por serial a 115200 baud
 * - Formato: {"sensors":[{"id":"suelo_h_1","type":"humidity","zone":"zona_1","value":45.2},...]}
 * - Heartbeat cada 10s si no hay datos: {"heartbeat":true}
 *
 * Conexion: USB al Raspberry Pi (/dev/ttyUSB0)
 */

// === CONFIGURACION ===
// Ajustar segun tu instalacion

const int NUM_HUMIDITY_SENSORS = 6;    // Sensores de humedad
const int NUM_PH_SENSORS = 2;         // Sensores de pH
const unsigned long READ_INTERVAL = 2000;  // ms entre lecturas

// Mapeo de sensores de humedad
struct SoilSensor {
  const char* id;
  const char* zone;
  int pin;
  // Calibracion: valores ADC para seco y mojado
  int dry_value;   // ADC cuando esta seco (~520 para capacitivo)
  int wet_value;   // ADC cuando esta mojado (~260 para capacitivo)
};

SoilSensor humidity_sensors[] = {
  {"suelo_h_1", "zona_1", A0, 520, 260},
  {"suelo_h_2", "zona_1", A1, 520, 260},
  {"suelo_h_3", "zona_1", A2, 520, 260},
  {"suelo_h_4", "zona_2", A3, 520, 260},
  {"suelo_h_5", "zona_2", A4, 520, 260},
  {"suelo_h_6", "zona_2", A5, 520, 260},
};

// Mapeo de sensores de pH
struct PHSensor {
  const char* id;
  const char* zone;
  int pin;
  // Calibracion pH
  float ph4_voltage;   // Voltaje a pH 4.0
  float ph7_voltage;   // Voltaje a pH 7.0
};

PHSensor ph_sensors[] = {
  {"suelo_ph_1", "zona_1", A8, 3.04, 2.54},
  {"suelo_ph_2", "zona_2", A9, 3.04, 2.54},
};

// === VARIABLES ===
unsigned long last_read = 0;
unsigned long last_heartbeat = 0;

void setup() {
  Serial.begin(115200);
  while (!Serial) { ; }  // Esperar conexion serial

  // Configurar pines analogicos
  for (int i = 0; i < NUM_HUMIDITY_SENSORS; i++) {
    pinMode(humidity_sensors[i].pin, INPUT);
  }
  for (int i = 0; i < NUM_PH_SENSORS; i++) {
    pinMode(ph_sensors[i].pin, INPUT);
  }

  delay(1000);
  Serial.println("{\"status\":\"ready\"}");
}

void loop() {
  unsigned long now = millis();

  if (now - last_read >= READ_INTERVAL) {
    last_read = now;
    last_heartbeat = now;
    sendReadings();
  }

  // Heartbeat cada 10 segundos si no hay lecturas
  if (now - last_heartbeat >= 10000) {
    last_heartbeat = now;
    Serial.println("{\"heartbeat\":true}");
  }
}

float readHumidity(SoilSensor &sensor) {
  // Leer 10 muestras y promediar
  long total = 0;
  for (int i = 0; i < 10; i++) {
    total += analogRead(sensor.pin);
    delay(2);
  }
  int raw = total / 10;

  // Convertir a porcentaje (0-100%)
  float humidity = map(raw, sensor.dry_value, sensor.wet_value, 0, 100);
  humidity = constrain(humidity, 0.0, 100.0);
  return humidity;
}

float readPH(PHSensor &sensor) {
  // Leer 10 muestras y promediar
  long total = 0;
  for (int i = 0; i < 10; i++) {
    total += analogRead(sensor.pin);
    delay(2);
  }
  float voltage = (total / 10.0) * 5.0 / 1024.0;

  // Conversion lineal usando calibracion de 2 puntos
  float slope = (7.0 - 4.0) / (sensor.ph7_voltage - sensor.ph4_voltage);
  float ph = 7.0 + slope * (voltage - sensor.ph7_voltage);
  ph = constrain(ph, 0.0, 14.0);
  return ph;
}

void sendReadings() {
  Serial.print("{\"sensors\":[");

  bool first = true;

  // Sensores de humedad
  for (int i = 0; i < NUM_HUMIDITY_SENSORS; i++) {
    float value = readHumidity(humidity_sensors[i]);
    if (!first) Serial.print(",");
    first = false;

    Serial.print("{\"id\":\"");
    Serial.print(humidity_sensors[i].id);
    Serial.print("\",\"type\":\"humidity\",\"zone\":\"");
    Serial.print(humidity_sensors[i].zone);
    Serial.print("\",\"value\":");
    Serial.print(value, 1);
    Serial.print("}");
  }

  // Sensores de pH
  for (int i = 0; i < NUM_PH_SENSORS; i++) {
    float value = readPH(ph_sensors[i]);
    if (!first) Serial.print(",");
    first = false;

    Serial.print("{\"id\":\"");
    Serial.print(ph_sensors[i].id);
    Serial.print("\",\"type\":\"ph\",\"zone\":\"");
    Serial.print(ph_sensors[i].zone);
    Serial.print("\",\"value\":");
    Serial.print(value, 1);
    Serial.print("}");
  }

  Serial.println("]}");
}
