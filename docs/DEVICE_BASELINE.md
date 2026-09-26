# Owner device baseline (2026-09-26)

The following observations are from the owner's own LAN device, shared during troubleshooting. They are *not* proof that all upstream firmware variants expose identical behavior.

## Read-only responses

- `GET /app.json` → `{"theme":5}`.
- `GET /v.json` → `{"m":"SmallTV-Ultra","v":"Ultra-V9.0.44"}`.
- `GET /space.json` → `{"total":3121152,"free":269836}` at the time sampled.
- A theme/rotation response was also observed: `{"list":"1,0,0,0,0,0,0","sw_en":"0","sw_i":"60"}`. Field semantics are tentative until cross-checked.

## UI observations

- `image.html` supports JPG/GIF pictures; UI instructs resizing GIFs to 240×240. At screenshot time, image listing said `fail` and no pictures appeared in the library.
- `weather.html` offers an 80×80 weather GIF, with `80x80-planet-2.gif` (31 KB) shown under `/gif`.
- Following owner deletion of other images/GIFs, both UI pages reported approximately **1063 KB free**, at a later time than the `space.json` sample. This is a **time difference**, not established evidence of contradictory storage accounting.
- Image auto display was checked and the JPG interval shown was 8 seconds.
- Do not infer image/listing status from `fail` without inspecting the route and server response.

## Physical assumptions to verify

Community projects report an ESP8266/ESP-12F, 4 MB flash, a 240×240 ST7789 RGB565 LCD over SPI, and an active-low backlight. Verify these on the physical board before building or flashing. Boot-strap pins GPIO0 and GPIO2 require special care. See:
- https://github.com/Times-Z/GeekMagic-Open-Firmware
- https://github.com/giovi321/smalltv-mod

## Data handling

Do not commit flash dumps, Wi-Fi passwords, API tokens, private photographs, cloud credentials or exact identifying network inventories. Treat local IPs as development configuration rather than constants.

## Current decision

Research and simulator only. Firmware replacement / custom OTA **not approved**; full flash backup and a reviewed recovery procedure are prerequisites.
