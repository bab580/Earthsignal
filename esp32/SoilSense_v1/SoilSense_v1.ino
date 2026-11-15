#include <WiFi.h>
#include <WebServer.h>
#include <HTTPClient.h>
#include <WiFiClient.h>
#include <string.h>

// =====================================
// TEXORA SOILSENSE v1
// ESP32 Soil Moisture Monitoring
// =====================================

// Sensor configuration
#define SOIL_PIN 34

// WiFi access point
const char* AP_SSID = "TEXORA-SOILSENSE";
const char* AP_PASSWORD = "YOUR_EXISTING_SOILSENSE_AP_PASSWORD";

// EarthSignal uplink configuration. Enter Wi-Fi and device token locally.
const bool ENABLE_EARTHSIGNAL_UPLOAD = true;
const char* STA_SSID = "Mulos Palace";
// Leave empty for an open network; use the Wi-Fi password for a secured network.
const char* STA_PASSWORD = "";
const char* EARTHSIGNAL_URL = "http://10.180.200.218:3000/api/sensors/readings";
const char* EARTHSIGNAL_DEVICE_TOKEN = "SET_THE_SAME_TOKEN_AS_EARTHSIGNAL_DEVICE_TOKEN";
const char* DEVICE_ID = "soilsense-01";
const unsigned long UPLOAD_INTERVAL_MS = 10000;
const unsigned long WIFI_RETRY_INTERVAL_MS = 15000;
const unsigned long WIFI_CONNECT_TIMEOUT_MS = 30000;

// Calibration values - adjust after testing
// These are starting examples, not universal values.
const int DRY_RAW = 3000;
const int WET_RAW = 1500;

WebServer server(80);
unsigned long lastStationAttempt = 0;
unsigned long stationConnectionStartedAt = 0;
unsigned long lastUploadAttempt = 0;
int latestRaw = 0;
int latestMoisture = 0;
String latestStatus = "READING";
bool hasSensorSample = false;
bool stationConnectionPending = false;

// =====================================
// READ SENSOR
// =====================================

int readSoilSensor() {
  long total = 0;

  // Average 20 readings to reduce noise
  for (int i = 0; i < 20; i++) {
    total += analogRead(SOIL_PIN);
    delay(5);
  }

  return total / 20;
}

// =====================================
// CALCULATE MOISTURE PERCENTAGE
// =====================================

int calculateMoisture(int raw) {

  if (DRY_RAW == WET_RAW) {
    return 0;
  }

  long percentage =
    ((long)DRY_RAW - raw) * 100L /
    ((long)DRY_RAW - WET_RAW);

  percentage = constrain(percentage, 0, 100);

  return (int)percentage;
}

// =====================================
// MOISTURE STATUS
// =====================================

String getStatus(int moisture) {

  if (moisture < 30) {
    return "DRY";
  }

  if (moisture < 70) {
    return "MOIST";
  }

  return "WET";
}

// =====================================
// DASHBOARD HTML
// =====================================

const char PAGE[] PROGMEM = R"rawliteral(

<!DOCTYPE html>
<html lang="en">

<head>

<meta charset="UTF-8">

<meta name="viewport"
content="width=device-width, initial-scale=1">

<meta name="theme-color" content="#09152f">

<title>TEXORA SoilSense</title>

<style>

* {
  box-sizing: border-box;
}

body {
  margin: 0;
  background: #eef2f7;
  color: #09152f;
  font-family: Arial, sans-serif;
}

header {
  background: #09152f;
  color: white;
  padding: 23px 20px;
}

.header-inner {
  max-width: 950px;
  margin: auto;
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 15px;
}

.brand {
  font-size: 21px;
  font-weight: bold;
  letter-spacing: .5px;
}

.subtitle {
  color: #aab6c8;
  font-size: 12px;
  margin-top: 6px;
}

.online {
  font-size: 12px;
  color: #86efac;
  white-space: nowrap;
}

.container {
  max-width: 950px;
  margin: auto;
  padding: 22px 16px;
}

.hero {
  background: white;
  border: 1px solid #e0e5ec;
  border-radius: 16px;
  padding: 28px;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 45px;
  flex-wrap: wrap;
}

.ring {
  height: 190px;
  width: 190px;
  border-radius: 50%;
  background: conic-gradient(
    #007ea7 0%,
    #e5eaf0 0%
  );
  display: grid;
  place-items: center;
}

.ring-inner {
  height: 154px;
  width: 154px;
  border-radius: 50%;
  background: white;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
}

.percent {
  font-size: 43px;
  font-weight: bold;
}

.ring-label {
  font-size: 11px;
  color: #7b8798;
  margin-top: 5px;
}

.status-area {
  min-width: 200px;
}

.status-label {
  color: #7b8798;
  font-size: 12px;
  text-transform: uppercase;
  letter-spacing: 1px;
}

.status {
  font-size: 30px;
  font-weight: bold;
  margin: 10px 0;
}

.description {
  color: #758195;
  font-size: 13px;
  line-height: 1.6;
}

.grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 13px;
  margin-top: 18px;
}

.card {
  background: white;
  border: 1px solid #e0e5ec;
  border-radius: 12px;
  padding: 18px;
}

.label {
  font-size: 11px;
  color: #768195;
  font-weight: bold;
  text-transform: uppercase;
  letter-spacing: .5px;
}

.value {
  font-size: 25px;
  font-weight: bold;
  margin-top: 10px;
}

.unit {
  font-size: 12px;
  color: #8792a4;
}

.panel {
  margin-top: 18px;
  background: white;
  border: 1px solid #e0e5ec;
  border-radius: 12px;
  padding: 20px;
}

.panel h3 {
  font-size: 16px;
  margin-top: 0;
}

.bar-bg {
  height: 11px;
  background: #e7edf3;
  border-radius: 20px;
  overflow: hidden;
  margin-top: 15px;
}

.bar-fill {
  height: 100%;
  width: 0%;
  background: #007ea7;
  transition: width .5s ease;
  border-radius: 20px;
}

.info {
  color: #718096;
  font-size: 12px;
  margin-top: 14px;
  line-height: 1.6;
}

.footer {
  text-align: center;
  color: #8b95a5;
  padding: 25px 10px;
  font-size: 11px;
}

@media(max-width:600px) {

  .header-inner {
    align-items: flex-start;
    flex-direction: column;
  }

  .hero {
    gap: 20px;
    padding: 23px 15px;
  }

  .grid {
    grid-template-columns: 1fr;
  }

  .ring {
    width: 165px;
    height: 165px;
  }

  .ring-inner {
    width: 135px;
    height: 135px;
  }

  .percent {
    font-size: 36px;
  }

  .status-area {
    text-align: center;
  }

}

</style>

</head>

<body>

<header>

  <div class="header-inner">

    <div>
      <div class="brand">TEXORA SoilSense</div>
      <div class="subtitle">
        Smart Agriculture / IoT Monitoring
      </div>
    </div>

    <div class="online">
      ● DEVICE ONLINE
    </div>

  </div>

</header>

<main class="container">

  <section class="hero">

    <div class="ring" id="ring">

      <div class="ring-inner">

        <div class="percent" id="moisture">--%</div>

        <div class="ring-label">
          SOIL MOISTURE
        </div>

      </div>

    </div>

    <div class="status-area">

      <div class="status-label">
        Current soil condition
      </div>

      <div class="status" id="status">
        READING
      </div>

      <div class="description" id="description">
        Waiting for sensor data...
      </div>

    </div>

  </section>

  <section class="grid">

    <div class="card">

      <div class="label">Raw Sensor Reading</div>

      <div class="value" id="raw">----</div>

      <div class="unit">ADC value / 4095</div>

    </div>

    <div class="card">

      <div class="label">Moisture Level</div>

      <div class="value" id="level">--%</div>

      <div class="unit">Estimated percentage</div>

    </div>

    <div class="card">

      <div class="label">Device Status</div>

      <div class="value" style="font-size:20px;color:#15803d">
        ONLINE
      </div>

      <div class="unit">ESP32 connected</div>

    </div>

  </section>

  <section class="panel">

    <h3>Moisture Level</h3>

    <div class="bar-bg">

      <div class="bar-fill" id="bar"></div>

    </div>

    <div class="info" id="updated">
      Connecting to sensor...
    </div>

  </section>

  <div class="footer">

    TEXORA TECHNOLOGY SOLUTIONS
    <br><br>
    SoilSense v1 | ESP32 Edge IoT Device

  </div>

</main>

<script>

async function updateData() {

  try {

    const response = await fetch('/api', {
      cache: 'no-store'
    });

    if (!response.ok) {
      throw new Error('Sensor API unavailable');
    }

    const data = await response.json();

    const moisture = data.moisture;

    document.getElementById('moisture').textContent =
      moisture + '%';

    document.getElementById('level').textContent =
      moisture + '%';

    document.getElementById('raw').textContent =
      data.raw;

    document.getElementById('status').textContent =
      data.status;

    document.getElementById('ring').style.background =
      'conic-gradient(#007ea7 ' +
      moisture +
      '%, #e5eaf0 ' +
      moisture +
      '%)';

    document.getElementById('bar').style.width =
      moisture + '%';

    let message = '';

    if (data.status === 'DRY') {
      message = 'The soil is dry. Irrigation may be needed.';
    }

    else if (data.status === 'MOIST') {
      message = 'The soil has moderate moisture.';
    }

    else {
      message = 'The soil is wet. Avoid unnecessary watering.';
    }

    document.getElementById('description').textContent =
      message;

    document.getElementById('updated').textContent =
      'Updated: ' + new Date().toLocaleTimeString();

  }

  catch (error) {

    document.getElementById('updated').textContent =
      'Connection lost. Reconnecting...';

  }

}

updateData();

setInterval(updateData, 2000);

</script>

</body>

</html>

)rawliteral";

// =====================================
// API ENDPOINT
// =====================================

void handleAPI() {

  int raw = readSoilSensor();

  int moisture = calculateMoisture(raw);

  String status = getStatus(moisture);

  String json = "{";

  json += "\"raw\":";
  json += String(raw);

  json += ",\"moisture\":";
  json += String(moisture);

  json += ",\"status\":\"";
  json += status;
  json += "\"";

  json += "}";

  server.send(
    200,
    "application/json",
    json
  );
}

bool stationSettingsReady() {
  return ENABLE_EARTHSIGNAL_UPLOAD &&
    strlen(STA_SSID) > 0 &&
    strcmp(STA_SSID, "YOUR_ROUTER_WIFI_SSID") != 0 &&
    strcmp(STA_PASSWORD, "YOUR_ROUTER_WIFI_PASSWORD") != 0 &&
    strlen(EARTHSIGNAL_DEVICE_TOKEN) > 0 &&
    strcmp(EARTHSIGNAL_DEVICE_TOKEN, "SET_THE_SAME_TOKEN_AS_EARTHSIGNAL_DEVICE_TOKEN") != 0 &&
    strcmp(EARTHSIGNAL_URL, "http://YOUR_COMPUTER_LAN_IP:3000/api/sensors/readings") != 0;
}

void beginStationConnection() {
  if (strlen(STA_PASSWORD) == 0) {
    WiFi.begin(STA_SSID);
  } else {
    WiFi.begin(STA_SSID, STA_PASSWORD);
  }
}

void maintainStationConnection() {
  static bool wasConnected = false;
  const bool connected = WiFi.status() == WL_CONNECTED;
  const unsigned long now = millis();

  if (connected && !wasConnected) {
    Serial.print("EarthSignal network connected; ESP32 station IP: ");
    Serial.println(WiFi.localIP());
    stationConnectionPending = false;
  } else if (!connected && wasConnected) {
    Serial.println("EarthSignal network disconnected; local access point remains available.");
    stationConnectionPending = true;
    stationConnectionStartedAt = now;
  }
  wasConnected = connected;

  if (!stationSettingsReady() || connected) {
    return;
  }

  if (stationConnectionPending) {
    if (now - stationConnectionStartedAt < WIFI_CONNECT_TIMEOUT_MS) {
      return;
    }

    Serial.println("EarthSignal Wi-Fi connection timed out; restarting attempt.");
    WiFi.disconnect(false, false);
    stationConnectionPending = false;
    lastStationAttempt = now;
    return;
  }

  if (now - lastStationAttempt >= WIFI_RETRY_INTERVAL_MS) {
    lastStationAttempt = now;
    stationConnectionStartedAt = now;
    stationConnectionPending = true;
    Serial.println("Retrying EarthSignal Wi-Fi connection...");
    beginStationConnection();
  }
}

void uploadSensorReading(int raw, int moisture, const String& status) {
  WiFiClient client;
  HTTPClient http;

  http.setConnectTimeout(2000);
  http.setTimeout(3000);
  if (!http.begin(client, EARTHSIGNAL_URL)) {
    Serial.println("EarthSignal upload could not start.");
    return;
  }

  http.addHeader("Content-Type", "application/json");
  http.addHeader("X-Device-Token", EARTHSIGNAL_DEVICE_TOKEN);

  String payload = "{\"device_id\":\"";
  payload += DEVICE_ID;
  payload += "\",\"raw\":";
  payload += String(raw);
  payload += ",\"moisture\":";
  payload += String(moisture);
  payload += ",\"status\":\"";
  payload += status;
  payload += "\"}";

  const int responseCode = http.POST(payload);
  if (responseCode >= 200 && responseCode < 300) {
    Serial.printf("EarthSignal reading accepted (HTTP %d).\n", responseCode);
  } else if (responseCode > 0) {
    Serial.printf("EarthSignal rejected reading (HTTP %d).\n", responseCode);
  } else {
    Serial.printf("EarthSignal upload failed: %s\n", http.errorToString(responseCode).c_str());
  }
  http.end();
}

// =====================================
// SETUP
// =====================================

void setup() {

  Serial.begin(115200);

  delay(1000);

  Serial.println();
  Serial.println("==============================");
  Serial.println(" TEXORA SOILSENSE v1");
  Serial.println("==============================");

  pinMode(SOIL_PIN, INPUT);

  analogReadResolution(12);

  // Keep the existing local dashboard AP while optionally joining a router.
  WiFi.mode(WIFI_AP_STA);
  WiFi.setAutoReconnect(false);

  bool started = WiFi.softAP(
    AP_SSID,
    AP_PASSWORD
  );

  if (!started) {

    Serial.println("WiFi AP failed!");

    while (true) {
      delay(1000);
    }

  }

  Serial.println("WiFi AP started!");

  Serial.print("Network: ");
  Serial.println(AP_SSID);

  Serial.print("Dashboard IP: ");
  Serial.println(WiFi.softAPIP());

  if (stationSettingsReady()) {
    Serial.println("Starting EarthSignal Wi-Fi connection...");
    stationConnectionStartedAt = millis();
    stationConnectionPending = true;
    lastStationAttempt = stationConnectionStartedAt;
    beginStationConnection();
  } else {
    Serial.println("EarthSignal uploads disabled; configure the station credentials and device token to enable them.");
  }

  // Web server routes
  server.on("/", HTTP_GET, []() {

    server.send(
      200,
      "text/html",
      PAGE
    );

  });

  server.on("/api", HTTP_GET, handleAPI);

  server.begin();

  Serial.println("Web server started!");
  Serial.println("==============================");

}

// =====================================
// MAIN LOOP
// =====================================

void loop() {

  server.handleClient();

  static unsigned long lastUpdate = 0;

  if (millis() - lastUpdate >= 2000) {

    lastUpdate = millis();

    latestRaw = readSoilSensor();

    latestMoisture = calculateMoisture(latestRaw);
    latestStatus = getStatus(latestMoisture);
    hasSensorSample = true;

    Serial.print("Raw: ");
    Serial.print(latestRaw);

    Serial.print(" | Moisture: ");
    Serial.print(latestMoisture);

    Serial.print("% | Status: ");

    Serial.println(latestStatus);

  }

  maintainStationConnection();

  const unsigned long now = millis();
  if (stationSettingsReady() &&
      WiFi.status() == WL_CONNECTED &&
      hasSensorSample &&
      now - lastUploadAttempt >= UPLOAD_INTERVAL_MS) {
    lastUploadAttempt = now;
    uploadSensorReading(latestRaw, latestMoisture, latestStatus);

  }

  delay(2);

}
