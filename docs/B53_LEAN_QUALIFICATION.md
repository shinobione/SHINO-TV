# B5.3 — LEAN public qualification (NTP + Paint 240×240)

This branch is isolated from the weather HTTPS branch, preserving installed
B5.2, owner credentials, the Windows SHINO LINK autostart and backup markers.
No private image, device reads/writes or OTA.

The lightweight graph is assembled from the exact B5.2 public-inert
generated graph and B5.3's existing strict NTP/UI adapters. It retains:
- authenticated clock publisher and challenge/HMAC endpoints
- 4 CPU/GPU/RAM/GPU temp cards with dynamic bars, owner Paint geometry
- NTP SNTP callback and Europe/Paris DST without requiring a PC
- protected AP and normal LAN telemetry and signed OTA recovery layout 4m2m
- LittleFS and native resource floors

Excluded from lean (both src and includes): B53WeatherHttps.cpp/.h, CA,
HTTP chunked/parser and resource gate. Lean sends no external weather HTTP
requests; weather row remains "WEATHER --", an honest placeholder.

Exact CI compares **both** builds on the **same commit** with pinned Core
and libraries, computes byte hashes/sizes automatically from actual public
BINs and static memory via the ELF resource reporter, confirms source
separation and tests the materialized renderer.

**NOT PROVEN:** device boot, real STA/NTP internet reachability, time drift,
NTP timezone change on hardware, heap/stack live or during OTA, 24x7
stability, and genuine postboot acceptance. Static RAM does not establish
physical free RAM. Any owner-private build or OTA needs a new, explicit
authorization for the exact file and SHA. Do not lower resource thresholds
or claim completion based on a public CI PASS.
