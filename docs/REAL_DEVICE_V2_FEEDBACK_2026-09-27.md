# SHINO // TV — first live device feedback and source-only follow-up

**27 Sept 2026. Evidence: owner screenshots/short videos and owner-operated command output. No new physical upload is performed by this PR.**

## Proven on the real SmallTV-Ultra

- Owner manually installed exact private FS-less 4m3m V2 firmware: 398,864 B, SHA-256 `bd8c9b1ea86caace5fd088f889071b8091b083887383cdc0123e5d950b2b5738`. Device screen boots and shows four permanent cards; private `SHINO-FirstBoot-*` Wi-Fi and Digest-protected `192.168.4.1` function.
- Authenticated GET `/api/v1/bridge/status` reports actual flash capacity 4,194,304 B, running sketch 398,864 B, volatile heap ~32,976 B and `FIRST_BOOT_BRIDGE`; its self-reported no-LittleFS/no-EEPROM status is a software diagnostic, **not** a complete physical flash readback.
- Owner's Windows PC has Ethernet plus Wi-Fi to SHINO AP; `Test-NetConnection 192.168.4.1 -Port 80` succeeded from `192.168.4.3`. Private paired Windows sender reports repeated `RAM telemetry accepted`; physical LCD shows changing CPU/GPU/RAM/temperature values. Normal expiration after ~6 seconds on stopping sender was accepted as expected.

## Two user-visible bugs observed

1. Full **horizontal mirror of all LCD glyphs and four cards**, not merely a swapped metric array. Inherited ConfigManager default `lcd_rotation=4`; Arduino_ST7789 rotation 4 enables `MADCTL_MX`. First-boot V2 now requests **rotation 0 in volatile runtime only**, no filesystem config load/save; four-card geometry unchanged.
2. Chrome repeatedly opens HTTP Digest login prompts during 2-second `GET /api/v1/bridge/metrics` background polling even as Windows POSTs continue. ESP8266WebServer uses a **shared nonce** regenerated at each new Digest challenge. Read-only browser session cookie is minted **only following authenticated GET /** with 128 bits from `ESP.random` on live AP; two peer-IP-bound volatile slots, two-hour expiry, exact cookie name and duplicated-cookie refusal. Accepted cookie is allowed **only for dashboard GET /, GET /ui.js, and GET metrics**, never for any POST, factory return, or diagnostic route. Missing/expired GET metrics session returns **403 JSON with no new Digest challenge**; embedded JS stops polling and instructs manual reopen/login, avoiding dialog storms. No generic auth removal, default credentials, local storage, query-parameter tokens or public endpoints.

## Deployment boundary — critically important

This new Draft PR is **source only** and **not** the earlier validated owner's BIN. The currently installed FS-less V2 intentionally exposes NO generic SHINO firmware update route. Its one write-capable optional endpoint is the authenticated, **exact OEM V9.0.44 application-only return**, not SHINO→arbitrary app OTA. Therefore DO NOT instruct the owner to upload this PR's compiled candidate directly to the existing bridge or try the old stock `/update` URL. That would not be supported.

If a later physical correction is chosen, separately review actual recovery/update paths, exact owner-private new build/credentials/sha, the potential return-to-OEM-then-new-OTA risks, and require a new explicit owner decision for each physical writing step. No automatic reflash, FS operation, release BIN or hardware action in this PR. Existing deployed device remains usable for LCD metrics (although mirrored); closing the browser avoids the login spam.
