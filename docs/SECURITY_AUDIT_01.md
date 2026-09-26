# SHINO // TV — Imported firmware security gate 01

**Scope:** static code review of the **pinned** Times-Z baseline (`a0c2ddcef4e76fa6eb040f6f544124763a2d85f5`) as imported into `firmware/`. Findings apply to that source version and are not claims about the owner's current proprietary Ultra-V9.0.44. **Physical deployment is blocked until the identified exposures are addressed and tests passed.**

| Finding | Evidence in source | Potential effect | Disposition |
|---|---|---|---|
| Fixed common setup/rescue AP credentials | `firmware/src/main.cpp` defines `AP_SSID`/`AP_PASSWORD`; `WiFiManager.cpp` uses both when STA fails and `RescueMode.cpp` uses them in rescue | Any local party aware of the published password may access recovery AP when active | **Block physical deployment**: per-unit provisioning/pairing and reviewed local fallback |
| Rescue operations do not authenticate | `firmware/src/boot/RescueMode.cpp` registers `POST /api/v1/rescue/token`, `/reboot`, `/reset`, `/ota` without Bearer check | Nearby connected client could reset token or attempt arbitrary firmware update | **Block physical deployment**: authenticated or physically gated rescue design and negative tests |
| Rescue OTA error checks are limited | `RescueMode.cpp` calls `Update.begin/write/end` but the endpoint infers outcome mainly from `Update.hasError()` | Unclear treatment of incomplete/aborted uploads or length verification | Code-path audit, explicit results and tests before deploying |
| No-credential legacy update fallback | `firmware/src/main.cpp`: `httpUpdater.setup(&webserver->raw(), "/legacyupdate")` when LittleFS missing/empty; no credentials passed | Potential unauthenticated OTA path in degraded filesystem state | Verify library auth semantics; disable or gate before deploy |
| API CORS wildcard | `firmware/src/web/Api.cpp` and rescue code send `Access-Control-Allow-Origin: *` | Expands browser-accessible origin surface; token validation still required for normal API | Threat-model, restrict where feasible; do not treat CORS as auth |
| Configuration static path | `main.cpp` serves `/config.json` when filesystem mounted; `ConfigManager.cpp` migrates credentials, then rewrites config | Factory/pre-migration config may include secrets; validate actual lifecycle | Remove unrestricted endpoint or return sanitized fields |
| “SecureStorage” is obfuscation, not encryption | `SecureStorage.cpp`: SHA-256-derived repeating XOR key from chip ID/MAC/public salt | Full flash backup or hardware access cannot be assumed to protect credentials | Treat backups as secrets, encrypt off-device, avoid public artefacts |
| New scene JSON bound checked after server receives request | `firmware/src/web/Api.cpp` uses `raw().arg("plain")` then checks 512 bytes | Bound protects parser/scene but not necessarily earlier HTTP server buffering | Add ingress/content-length guard or test memory behavior; keep local-only |
| Device output format is ASCII-only v1 | `firmware/src/scenes/SceneManager.cpp` rejects nonprintable/non-ASCII and validates fields | Accented characters cannot currently be displayed by built-in bitmap font | Documented limitation; add font/UTF-8 support separately, not an auth issue |

## Security review completion criteria

1. Deployment-critical paths (rescue, setup AP, degraded filesystem updater, config) have explicit risk treatment and regression tests. Rescue access must remain possible after a legitimate recovery attempt without relying on a public/shared password.
2. HTTP scene endpoints enforce authentication and size/type bounds; missing/invalid token is denied.
3. Threat model assumes a *trusted, segmented home LAN* for first hardware validation, no port forwarding, and restricted access to the PC metrics bridge.
4. Backups are classified as sensitive; no flash contents, passwords or API tokens in source control, CI artifacts, issues or public chat.
5. A separate owner go/no-go before any firmware write remains required even after CI succeeds.

## Non-goals

This is a code audit, not a proof that any device was compromised. We deliberately do not probe or exploit the owner's proprietary firmware. No OTA/reboot/reset calls were made.
