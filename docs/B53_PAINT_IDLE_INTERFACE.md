# B5.3 — Owner Paint 240 x 240 IDLE interface

This changes **only B5.3 generated SceneEngine**, preserving frozen B5.2,
native HTTP Digest/HMAC, OTA 4m2m staging, LittleFS, and Windows LINK.

Actual pixels, not design claims:
- Header at y=0..103 (13 cooperative stripes, 8px each).
- "SHINO // TV" at x=87,y=10; 5-character HH:MM centered at x=60,y=32,
  font scale 4 (120x32), with small PC/NT clock authority indicator.
- Weather at y=76 / condition at y=96, **only when fresh**. Otherwise
  literal "WEATHER --" or "WEATHER STALE", never a made-up temperature.
- Metric cards: [x,y,w,h] 6,106,111,60 | 123,106,111,60 |
  6,174,111,60 | 123,174,111,60. Single-line exact
  CPU, GPU, RAM, GPU temp labels (scale 2); compact values scale 3;
  bars 97x4 at offset 7,51.
- Dynamic green/yellow/dark-orange/burgundy band selection retained. CPU
  and GPU are percentages, RAM normalized by actual memoryTotalGb, GPU temp
  normalized via the pre-existing DashboardV2::tempPercent 30..90 C mapping
  (temperature scale, **not** GPU utilization). The displayed sensor values
  are rounded only for readability; measurement transmission is unchanged.
- If telemetry is stale, cards are cleared and "PC OFFLINE / NO PC METRICS"
  appears without changing the clock/weather source. Fresh metric
  reappearance invalidates that offline label before cards repaint.
- All idle rendering remains one cooperative task per step (no new
  framebuffer, image asset, dynamic string or network call).

**Scope of evidence:** generated-source assertions, exact ESP8266
public-inert compile, and host rendering tests when available. B5.2 physical
installation and its validated metrics are not modified. Weather still lacks
an implemented supplier; UI shows an honest placeholder. SNTP physical
source selection, full native heap/stack, thermal bar calibration and owner
LCD comparison remain unverified until separately authorized testing.

Stop on public build or resource failure. No installer, flash, OTA, device
read/write or Windows autostart operation is included in this task.
