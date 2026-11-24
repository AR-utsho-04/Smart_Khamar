/*
  Example firmware: ESP32 smart collar -> Livestock Health Monitoring System
  Sends the animal's body temperature (and battery level) to the server every minute.

  STATUS: example code. It has NOT been tested on real hardware. Check wiring and values before using it on an animal.

  Parts (example): ESP32 dev board, DS18B20 temperature probe (waterproof), 4.7k ohm resistor, LiPo battery.
  Wiring: DS18B20 red -> 3V3, black -> GND, yellow (data) -> GPIO 4, and a 4.7k resistor between data and 3V3.
  Optional battery sensor: two equal resistors (100k) as a voltage divider from battery+ to GND, middle point -> GPIO 34.

  Libraries (Arduino IDE -> Library Manager): "OneWire" and "DallasTemperature".
  Heart rate and activity are optional fields in the API. Add a pulse sensor or accelerometer later and
  send heart_rate_bpm and activity_index in the same JSON.
*/
#include <WiFi.h>
#include <WiFiClientSecure.h>
#include <HTTPClient.h>
#include <OneWire.h>
#include <DallasTemperature.h>

// ---------- EDIT THESE ----------
const char* WIFI_SSID  = "YOUR_WIFI_NAME";
const char* WIFI_PASS  = "YOUR_WIFI_PASSWORD";
// Local test:  http://192.168.0.10:8000/api/v1/iot/telemetry   (your PC's address)
// Online:      https://your-site.onrender.com/api/v1/iot/telemetry
const char* API_URL    = "http://192.168.0.10:8000/api/v1/iot/telemetry";
const char* DEVICE_KEY = "PASTE_THE_DEVICE_KEY_FROM_THE_DEVICES_PAGE";
const unsigned long INTERVAL_MS = 60000;   // one reading per minute
// --------------------------------

const int ONE_WIRE_PIN = 4;
const int BATTERY_PIN  = 34;
OneWire oneWire(ONE_WIRE_PIN);
DallasTemperature sensors(&oneWire);
WiFiClient plainClient;
WiFiClientSecure secureClient;

float readBatteryPct() {
  // 100k + 100k divider: pin sees half of the battery voltage. 3.3 V = empty, 4.2 V = full.
  float volts = analogRead(BATTERY_PIN) / 4095.0f * 3.3f * 2.0f;
  float pct = (volts - 3.3f) / (4.2f - 3.3f) * 100.0f;
  return constrain(pct, 0.0f, 100.0f);
}

void connectWifi() {
  if (WiFi.status() == WL_CONNECTED) return;
  WiFi.begin(WIFI_SSID, WIFI_PASS);
  for (int i = 0; i < 40 && WiFi.status() != WL_CONNECTED; i++) delay(500);
}

void sendReading() {
  sensors.requestTemperatures();
  float tempC = sensors.getTempCByIndex(0);
  if (tempC == DEVICE_DISCONNECTED_C || tempC < 25 || tempC > 45) {
    Serial.println("Bad temperature reading, skipped");
    return;
  }
  String body = String("{\"temperature_c\":") + String(tempC, 2) + ",\"battery_pct\":" + String(readBatteryPct(), 0) + "}";
  // No timestamp is sent: the server uses the time the reading arrives.

  HTTPClient http;
  bool tls = String(API_URL).startsWith("https");
  if (tls) { secureClient.setInsecure(); http.begin(secureClient, API_URL); }  // setInsecure(): demo only, skips certificate check
  else     { http.begin(plainClient, API_URL); }
  http.addHeader("Content-Type", "application/json");
  http.addHeader("X-Device-Key", DEVICE_KEY);
  int code = http.POST(body);
  Serial.printf("POST %s -> HTTP %d\n", body.c_str(), code);
  if (code > 0) Serial.println(http.getString());
  http.end();
}

void setup() {
  Serial.begin(115200);
  sensors.begin();
  connectWifi();
}

void loop() {
  connectWifi();
  if (WiFi.status() == WL_CONNECTED) sendReading();
  else Serial.println("No WiFi, will retry");
  delay(INTERVAL_MS);
}
