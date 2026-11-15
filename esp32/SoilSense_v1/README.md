# SoilSense v1 + EarthSignal

`SoilSense_v1.ino` is a separate integration copy of the supplied sketch. The original source snapshot is not modified. The embedded dashboard HTML, CSS, colors, fonts, layout, local `/api` response, sensor pin and calibration constants are preserved.

## Configure the computer/backend

1. Connect the computer and ESP32 to the same Wi-Fi router or phone hotspot.
2. Find the computer's IPv4 address with `ipconfig`. Use the address on the same network as the ESP32, not `localhost` or `127.0.0.1`.
3. Set `EARTHSIGNAL_DEVICE_TOKEN` in the project's `.env` to a unique token. Restart EarthSignal after changing it.
4. Allow the local Python server through Windows Firewall on the trusted private network if prompted.

The backend listens on port `3000` and must be reachable at `http://<computer-LAN-IP>:3000`.

## Configure and upload the ESP32 sketch

In the integration copy, set:

- `AP_SSID` and `AP_PASSWORD` to the existing hotspot credentials if you want to keep the current local dashboard network unchanged.
- `ENABLE_EARTHSIGNAL_UPLOAD` to `true`.
- `STA_SSID` and `STA_PASSWORD` to the router/hotspot credentials. Leave `STA_PASSWORD` empty (`""`) for an open network; use the network password for a secured network.
- `EARTHSIGNAL_URL` to `http://<computer-LAN-IP>:3000/api/sensors/readings`.
- `EARTHSIGNAL_DEVICE_TOKEN` to the same value configured in the backend `.env`.
- `DEVICE_ID` to the device ID saved in the website's Farmer Dashboard.

Keep your existing access-point credentials private; enter them into the sketch locally to preserve the current hotspot. Open the integration copy in Arduino IDE, select the exact ESP32 board and port, then upload it. Use Serial Monitor at 115200 baud to see Wi-Fi and HTTP status messages.

The ESP32 keeps the local access point and web server while it attempts a station connection to the router. Its existing page remains at the AP IP printed to Serial Monitor (commonly `192.168.4.1`), and its local `/api` endpoint is unchanged.

## Data flow and limits

- The ESP32 sends the latest sampled `raw`, `moisture` and `status` every 10 seconds to EarthSignal using `POST` and the `X-Device-Token` header.
- The station connection is allowed up to 30 seconds to connect before the sketch aborts that attempt and retries. This avoids starting another `WiFi.begin()` while the ESP32 is still connecting.
- EarthSignal records server receive time because this sketch does not yet synchronize a clock or send `recorded_at`.
- The website Farmer Dashboard polls EarthSignal for the latest stored reading.
- Failed uploads are logged to Serial and are not queued for later delivery; offline buffering is not implemented.
- AP+STA behavior, router compatibility, firewall access and upload timing must be checked on the actual ESP32. The synchronous HTTP upload can briefly delay handling the local dashboard request.

This is a local-network demo using HTTP. Do not expose the device token or endpoint over an untrusted/public network; production use needs HTTPS and stronger device credential management.
