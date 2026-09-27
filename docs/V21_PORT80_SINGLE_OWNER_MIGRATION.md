# SHINO // TV V2.1 — Single-owner port-80 migration contract (DESIGN ONLY)

**State:** independent, offline-only PR #20. No port-80 switch, no device connection, no new upload route, no Updater or filesystem write. The owner's installed V2 Hotfix `review-002` remains the known working application. Its browser GET cookie is never POST/OTA authority.

## Existing pinned firmware and why a naive mux cannot work

`FirstBootBridge.cpp` currently owns **one `ESP8266WebServer server(80)`** and calls `server.handleClient()` from its normal loop. The library's pinned ESP8266 Arduino Core **3.1.2** `handleClient()` independently calls the private `_server.accept()`, then its `_parseRequest(_currentClient)` consumes the request before invoking a normal handler. A second `WiFiServer(80)` would contend for the same port. Reading the request line on a different server and passing the partly consumed connection to the existing unmodified `ESP8266WebServer` is **not a reviewed or supported handoff**; those consumed bytes would not be available to its parser. Ordinary `server.on(..., HTTP_POST)` is also unsuitable for a firmware body because the core's standard non-multipart POST parser buffers the body in a `String` before dispatch and can overwrite duplicate Host/Content-Length fields.

Sources reviewed against exact core 3.1.2:
- [ESP8266WebServer-impl.h — handleClient](https://github.com/esp8266/Arduino/blob/3.1.2/libraries/ESP8266WebServer/src/ESP8266WebServer-impl.h).
- [Parsing-impl.h — HTTP request/body parsing](https://github.com/esp8266/Arduino/blob/3.1.2/libraries/ESP8266WebServer/src/Parsing-impl.h).
- The actual owner's [FirstBootBridge.cpp](../firmware/src/boot/FirstBootBridge.cpp).

A separate port or domain is **not** an implicit workaround: current UI/CSP and strict private-AP Host/Origin are tied to `http://192.168.4.1`; an alternate port changes browser origin, Digest challenge behavior and CORS/CSRF assumptions. We have **not** enabled that option.

## Source-only routing classifier

`firmware/include/boot/NativeOtaPort80Plan.h` classifies **at most 128 bytes of a complete strict CRLF-terminated request line**. It is a pure routing *proposal*; it consumes no live socket bytes, parses no headers or body, and never invokes a handler. `tools/native_ota_port80_plan_probe.cpp` compiles/executes the classifier; `tools/test_native_ota_port80_plan.py` independently extracts the exact live route set from FirstBootBridge and fails CI if that set changes without an audit.

The matrix is frozen to the existing FirstBootBridge routes:

| Request | Current route/authorization rule | Planned classification |
| --- | --- | --- |
| `GET /` | Digest or valid short-lived **GET-only** browser session; issues session after Digest | LegacyDashboardGet |
| `GET /ui.js` | Digest or valid browser-read session | LegacyJavascriptGet |
| `GET /api/v1/bridge/metrics` | Valid browser-read session; no repetitive background Digest prompt | LegacyMetricsGet |
| `POST /api/v1/bridge/metrics` | Digest, bounded 16–384-byte JSON; updates four RAM-only telemetry values | LegacyMetricsPost |
| `GET /api/v1/bridge/status` | Digest | LegacyStatusGet |
| `GET /api/v1/bridge/fs-plan` | Digest | LegacyFsPlanGet |
| `GET /api/v1/bridge/ota/capabilities` | Digest or GET-read session; explicitly no writer/upload | LegacyCapabilitiesGet |
| `GET /api/v1/bridge/factory-return` | Digest; status only | LegacyFactoryReturnGet |
| `POST /api/v1/bridge/factory-return` | **Only compiled when** `SHINO_ENABLE_FACTORY_RESTORE=1`; separate pinned OEM policy, Digest and independent per-operation approval | LegacyFactoryReturnPost |
| Unknown route | Existing Digest-authenticated 404 | LegacyAuthenticatedNotFound |

The entire `/api/v1/bridge/ota/` namespace **except existing read-only capabilities GET** is reserved before any future buffered legacy parser. A POST to `/arm` or `/upload` yields **OtaReservedArm/OtaReservedUpload** *as a proposed classification only*, NEVER as a registered handler, and any other method/path yields OtaReservedReject. A read cookie cannot authorize these classifications. Strict route matching rejects ambiguous encoded/query/fragment targets; existing legacy-query behavior outside the exact listed routes remains unverified and is an explicit future parity gate.

## Host single-owner TCP shadow — new independent experiment (NOT deployed)

The previous method/path matrix is now exercised by **one real host-only TCP listener**, `tools/native_ota_single_ingress_loopback.cpp`, bound strictly to `127.0.0.1` on an OS-assigned ephemeral port. It feeds `NativeOtaSingleIngressShadow.h`, which uses no actual socket, a maximum **128-byte CRLF request line**, a maximum **2,048-byte header area**, and at most **384 bytes** of temporary test-only metrics body storage. The same ingress receives dashboard GET, metrics GET/POST, diagnostics GET and the read-only capabilities GET. Future OTA arm/upload, any other reserved OTA namespace method, and optional legacy factory-return POST are **rejected before body intake**. It rejects repeated/mixed-case header names, missing/wrong Host, chunked/ambiguous framing, excess or incomplete bodies, pipelined bytes, malformed request targets, and deadline expiry.

**Crucial distinction:** This is an *executable routing/framing shadow*, not a port of the deployed server's behavior. Every recognized legacy route deliberately returns **HTTP 501 Not Implemented / SHADOW_CLASSIFIED_ONLY_NO_DISPATCH**; it does not authenticate the existing private Digest credentials, issue a real browser GET session, serve actual HTML/JavaScript, parse/apply Windows numeric JSON, repaint the four native LCD cards, or perform a factory return. The loopback fixture's rejected requests return **HTTP 403 / SHADOW_REJECTED_NO_WRITER**. No success response claims actual route execution or owner-device installation, and no test currently proves those live behaviors are preserved by a replacement server.

The host C++ and Python regression matrix runs real TCP fragmentation down to **one byte per send**, all named legacy routes and bounded Windows metrics framing, mixed/duplicate Host and Content-Length, full/short/extra payload, reserved OTA requests without receiving any firmware-sized body, and the disabled OEM POST. The active `FirstBootBridge` source and its unique `ESP8266WebServer server(80)`/`server.handleClient()` continue unchanged. No Wi-Fi/AP/device listening is connected.

This shadow establishes an important necessary property — the port-80 routing decision can be made *before* accidentally buffering a reserved OTA request — but NOT a sufficient proof for a safe physical firmware upgrade. Next review must add a single-owner **host legacy-response compatibility harness** that reproduces real read-session and bounded telemetry rules with fixture-only credentials, then type-check the bounded network adapter under the real ESP8266 core without any live startup registration. Only after a separate explicitly authorized owner transition could runtime/UI/LCD parity be measured on the device. The signed flash writer is an independent, still disabled gate.

## Browser read-session and real Windows telemetry parity — host fixtures ONLY

A separate, **disconnected** C++/Python source-regression pair now follows the actual `FirstBootBridge.cpp` and `FslessMetrics.cpp` behaviors rather than assuming that classifying the route is equivalent to serving it:

- `firmware/include/boot/NativeOtaLegacySessionReview.h` models exactly **two volatile GET-only read-session slots**, peer IPv4 binding, the 256-byte Cookie-header cap, a single `SHINO_READ_SESSION` cookie, duplicate rejection, 128-bit externally supplied test-token formatting, 2-hour unsigned-`millis()` expiry, reuse of an existing valid read-cookie on `GET /`, and replacement of an expired/oldest slot. Only an independently authenticated (synthetic-fixture boolean) **GET /** would issue a new cookie. The browser's **GET metrics** with an expired/missing session yields 403 **without a fresh Digest prompt**, preserving the Chrome nonce-storm fix. `GET /ui.js` and read-only OTA capabilities may use a valid read-cookie or Digest; status/fs-plan/factory-return GET require Digest. The Windows **POST metrics** never accepts a GET cookie and still requires distinct Digest authentication. Factory POST and all OTA writes remain disabled in this model. **No real challenge, password, SHA proof, cookie or HTTP response is created**; the flags are test fixture inputs, not owner authorization.
- `firmware/include/boot/NativeOtaLegacyTelemetryReview.h` models the actual typed `FslessMetrics::apply()` semantics as a separate **host RAM test value**, not an actual `ArduinoJson` decoder: `ok=true` and `gpu_available` must be booleans, while `cpu_usage`, `gpu_usage`, `memory_used_gb`, `gpu_vram_mb`, `gpu_temp_c`, `gpu_power` must be finite JSON numeric types inside the source ranges. `memory_total_gb` is optional for older companion samples; when present it must lie within 0.01–256 GiB and not be less than used RAM. Values are converted to `float` before checking bounds, as in the current firmware. A rejected sample must **not** replace the last good host value. The stale limit is **strictly greater than 6,000 ms**, including unsigned clock rollover, and missing total RAM must remain unknown rather than assume a denominator. The screen remains four cards — CPU usage, GPU usage, RAM in use, GPU temperature — but **the fixture does not paint a real LCD or serve its UI**.
- `tools/test_native_ota_legacy_compatibility.py` compiles/executes both C++ models, verifies source rules and frozen numeric field names/bounds against `FslessMetrics.cpp`, and independently JSON-decodes synthetic Windows payloads within the existing **16–384-byte** POST envelope. It explicitly rejects the earlier, incorrect illustrative `{"cpu":..., "gpu":..., "memoryGb":...}` shape. Prior host single-ingress tests also now send a **genuinely valid telemetry schema fixture** instead of merely relying on a well-framed but semantically invalid JSON example. All fixture entropy, usernames and values are synthetic and are never deployed.

These are **necessary behavior-parity assertions, not a complete end-to-end reimplementation of ESP8266WebServer, actual ArduinoJson parsing, the real Windows companion, Chrome browser or the ST7789 screen**. Existing owner `FirstBootBridge` and its web route/credential state remain unchanged. No OTA server, firmware writer, recovery action or device network request has been activated.

## Before replacing the running single-owner server

A separately reviewed new single-owner port-80 ingress must meet ALL of the following, without an unreviewed fork or a blind handoff to the current parser:

1. Own precisely one port-80 listener. Preserve the original request bytes after tentative request-line classification and parse them **once** under one consistent bounded framing policy; if legacy handling still depends on `ESP8266WebServer`, prove a supported full-byte handoff or implement/review equivalent legacy handlers from scratch. Do not claim this classifier does either.
2. Preserve every exact route in the table, the read-session scope, Chrome Digest-prompt fix, Windows POST sample path, same four LCD cards/redraw timing and `server.onNotFound` authorization. Preserve factory-return compile profile and its separately approved owner workflow.
3. Give OTA arm/upload a **separate raw HTTP header and streaming pipeline** before any buffered legacy body parse. Reject duplicate Host/Content-Length/Authorization, transfer encoding, ambiguous Origin, invalid MIME and over-size headers. Never let arbitrary `GET` or `HEAD` fall through to an upload handler.
4. Preserve the exact private-AP interface/peer identity from the accepted socket, hardware-random one-shot nonce and manual consent, dedicated true SHA-256 Digest binding method and route, private owner HA1 and RSA public-key continuity. No long-lived POST cookie authorization.
5. Keep the new OTA review sink **nonwriting** until port-80, browser and live-device RAM/time regression are passed in a separate, owner-reviewed transition. No `Update.begin/write/end`, no `Update.end(true)`, no FS/EEPROM migrations, no automatic restart, no new OEM unsigned exception.
6. Complete separate CI and supervised **single-device, per-operation owner authorization** before ever installing a new firmware. Compiling this routing plan is not that authorization. A boot failure cannot be assumed recoverable through a web server.

**Current result:** host classification/route-parity tests only. The native WiFiClient pump from the previous increment remains disconnected from FirstBootBridge and bound to a reject-all compile fixture. Installed hardware is unchanged; PR #20 remains Draft and **physical_installation_authorized=false**.
