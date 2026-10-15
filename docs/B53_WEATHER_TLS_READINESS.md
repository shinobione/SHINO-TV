# B5.3 Weather HTTPS — source present, physical HOLD

The generated B5.3 *public inert* graph includes a bounded HTTPS Open-Meteo
client. Its call to begin("", "") means it never contacts the service.
Only a future owner-private exact candidate with reviewed geographical
coordinates could activate it. No Wi-Fi/provisioning changes were made.

A fetch requires a native SNTP time sample, authenticated TLS 1.2 with the
public ISRG Root X1 anchor, server MFLN negotiated at 512B, exact
api.open-meteo.com hostname, no redirects/compression, strict bounded HTTP chunked or Content-Length,
headers and decoded JSON <= 768 bytes and strict WMO/temp parser. Failures
never replace a good sample; once-per-30-min attempt, no immediate retry.

Physical B5.2 reported heap 28848 B / stack 2496 B, which fail
B5.3's **pre-TLS** heap >= 36864 B, largest >= 32768 B and continuation
stack >= 3072 B. The guard is intentionally stronger than the OTA resource
floors. DO NOT relax thresholds to get an online weather result.

**PUBLIC NETWORK PASS (2026-10-15):** GitHub Actions verified the
server's TLS1.2 certificate chain against the embedded ISRG Root X1,
accepted MFLN 512, and observed 366 decoded JSON bytes in HTTP chunked
framing. The separate native chunked decoder and public ESP8266 build
passed HOST/CI on the exact source commit. This does NOT prove a native
TLS handshake on the SmallTV.

**PHYSICAL HOLD**: handshake duration, heap/stack peaks, captive portal,
Wi-Fi reconnection and telemetry impact remain unmeasured. The ESP8266 TLS handshake
is synchronous and may exceed the application read deadline. No claim of
24/7 autonomous weather until those checks pass. No HTTP cleartext fallback,
no private candidate, no installation/flash/OTA in this milestone.
