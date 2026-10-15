# B5.3 — Open-Meteo bounded parsing gate

Current endpoint contract: GET HTTPS api.open-meteo.com/v1/forecast with
explicit latitude/longitude, current=temperature_2m,weather_code,
temperature_unit=celsius, timezone=UTC.

A standalone, allocation-free HOST parser accepts only complete, bounded
<=768-byte JSON and unique current.weather_code / temperature_2m keys.
Unknown valid WMO codes fail closed; temperatures are required to have at
most one decimal and lie in [-90.0,70.0] Celsius. Malformed data never
replaces a valid weather sample. Code -> fixed short ASCII condition label.

This milestone does NOT fetch weather. The network side must meet:
- authenticated HTTPS with verifiable CA and hostname, never setInsecure()
- no TLS start without recent verified SNTP for X.509 time validation
- one known host, no redirects, bounded body and Content-Length
- fixed length path and known coordinates selected owner-local
- refuse under insufficient heap/cont-stack/large contiguous block
- never overlap HTTP OTA or telemetry; no retry storms
- ideally MFLN 1024 supported by server, or HOLD HTTPS on ESP8266
- keep B5.2 physical firmware intact, no owner image or OTA
