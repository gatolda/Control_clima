/*
 * Greenhouse Soil Sensors Hub
 * Arduino Mega 2560 -> Raspberry Pi via USB serial
 *
 * Sensores:
 * - Capacitive Soil Moisture Sensor v2.0 en A0 (3.3V)
 *
 * Protocolo: JSON por serial a 115200 baud
 * Agregar mas sensores: duplicar bloque en sendReadings()
 */

// === CONFIGURACION ===
const unsigned long READ_INTERVAL = 2000;  // ms entre lecturas
const unsigned long HEARTBEAT_INTERVAL = 10000;

// Sensor capacitivo v2.0 en A0
// Calibracion: seco ~520, mojado ~260 (ajustar con tus valores)
const int CAP_PIN = A0;
const int CAP_DRY = 596;    // Valor ADC en aire (seco) - calibrado en Pi
const int CAP_WET = 240;    // Valor ADC en agua (mojado) - estimado, recalibrar con agua

// === VARIABLES ===
unsigned long last_read = 0;
unsigned long last_heartbeat = 0;

void setup() {
  Serial.begin(115200);
  while (!Serial) { ; }

  pinMode(CAP_PIN, INPUT);

  delay(1000);
  Serial.println("{\"status\":\"ready\",\"sensors\":1}");
}

void loop() {
  unsigned long now = millis();

  if (now - last_read >= READ_INTERVAL) {
    last_read = now;
    last_heartbeat = now;
    sendReadings();
  }

  if (now - last_heartbeat >= HEARTBEAT_INTERVAL) {
    last_heartbeat = now;
    Serial.println("{\"heartbeat\":true}");
  }
}

float readCapacitive() {
  long total = 0;
  for (int i = 0; i < 10; i++) {
    total += analogRead(CAP_PIN);
    delay(2);
  }
  int raw = total / 10;
  float humidity = (float)(CAP_DRY - raw) / (float)(CAP_DRY - CAP_WET) * 100.0;
  return constrain(humidity, 0.0, 100.0);
}

void sendReadings() {
  float cap_hum = readCapacitive();
  int cap_raw = analogRead(CAP_PIN);

  Serial.print("{\"sensors\":[");
  Serial.print("{\"id\":\"suelo_h_1\",\"type\":\"humidity\",\"zone\":\"zona_1\",\"value\":");
  Serial.print(cap_hum, 1);
  Serial.print(",\"raw\":");
  Serial.print(cap_raw);
  Serial.print("}");
  Serial.println("]}");
}
