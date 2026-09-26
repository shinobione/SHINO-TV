# One SmallTV, no soldering: Wi-Fi-only installation decision

**Owner constraints:** one working SmallTV-Ultra on stock V9.0.44, no second board, no soldering or UART/PCB pin wiring, and a USB-C port that does not enumerate a COM device even with a known-good data cable. Work offline until a separate explicit owner authorization for a named flash file and action.

## Current state

- The owner's original `http://192.168.1.70/update` GET page was personally observed in a screenshot. Merely opening it did not upload anything.
- The **exact official V9.0.44 application OTA** was recovered from the manufacturer's Git history and verified against both outer ZIP and inner BIN SHA-256. This is a rollback *input*, not a full-chip backup.
- We have separate Times-Z-based custom firmware plus a small, private-AP, locally provisioned SHINO OTA trampoline. It is **not persistent**: the second-stage OTA replaces it.
- The one-device `wifi-path-preflight.yml` compiles the ACTUAL candidate and a write-gated mini-loader for it, checks their embedded exact image pins, compares headers/layout assumptions and computes both known staging budgets, all without contacting the device or publishing a firmware image.
- No operation or file upload was made on the physical SmallTV. All firmware PRs remain Draft.

## Safety findings to resolve before any live flash

| Transition | What we can prove in CI | What remains unknown |
|---|---|---|
| Factory 9.0.44 → SHINO mini-loader | Original ZIP verified; mini-loader build checked against independently published community loader-size benchmark | **Actual OTA free size and acceptance on THIS V9.0.44**. Screenshot of `/update` proves the route exists, not that any specific BIN fits or boots. |
| SHINO mini-loader → SHINO application | Both actual images compiled against reviewed ESP8266 4 MiB DIO configs; model staging free space for `4m1m` | Loader AP, HTTP upload, boot behavior and update staging only compiled/simulated, not hardware tested. |
| SHINO application → OEM V9.0.44 | Original app pinned; nominal OTA staging arithmetic under `4m2m` can be modelled | Generic upstream `/api/v1/ota/fw` lacks the **mandatory original-image pinning** we want. Need a dedicated authenticated rollback path and integrity checks before any deployment. OEM original filesystem layout and preferences under our new FS map are still unknown. |
| Loader or SHINO becomes nonbootable | No software-only verification can demonstrate reliable Wi-Fi recovery from a nonbooting application | **No recovery via Wi-Fi** if neither code nor an independent resident rescue service starts. Hardware recovery remains unavailable by owner choice. |

## Interpretation of the preflight result

`tools/wifi_flash_preflight.py` returns `OFFLINE_PREFLIGHT_ONLY__OWNER_FLASH_NOT_AUTHORIZED`, even if all known headers, digests, source layout checks and modeled staging budgets pass. This is intentional. Its success is not a deployment approval.

The official 9.0.44 ESP8266 8-byte image header contains SPI flash size/mode/frequency, **not the original firmware's complete physical filesystem partition map**, and an application OTA package does not contain the 4-MiB owner flash.

### Why we do not embed the OEM BIN inside every SHINO build

It consumes about 494 KiB of valuable application storage, increases OTA-fit problems, duplicates OEM-proprietary code and is inaccessible after a hard boot failure. We instead preserve a user-supplied local verified OEM binary plus a future authenticated factory-return endpoint on the working SHINO app. Even then, only a working app/recovery route can receive it.

## Preparatory work, no device contact

1. Keep both official V9.0.44 ZIP and its extracted, verified BIN privately on your Windows PC outside GitHub.
2. Compile and inspect the exact current SHINO + loader pair in ephemeral CI, not arbitrary mismatched binaries.
3. Close security issues in the normal SHINO app: publicly shared setup AP password, unauthenticated rescue endpoints, `/legacyupdate` when LittleFS fails, unrestricted `/config.json`, and generic OTA without per-image controls.
4. Add an authenticated, exact-OEM-image-only restore route to SHINO app itself (the transient loader is gone after second hop), and independently verify candidate and factory application bytes before staged install.
5. Review **original factory filesystem/data layout** and how custom `4m2m` partitions affect returning to the official application. Must not confuse successful boot with complete factory-state restoration.
6. Only then issue a precise proposed owner-specific Wi-Fi install guide, including an honest list of remaining failure modes. Wait for owner's **new, affirmative permission** for the actual upload. The option to remain indefinitely on original firmware is always available.

## Important conclusions

- A second test unit will **not** be presented as a purchase requirement; no soldering/USB-UART is planned.
- Removing physical recovery means a risk of unrecoverable boot failure remains. Do not claim a completely brick-proof software-only solution.
- No hardware action is performed by any of these scripts/workflows.

Upstream references:
- [Espressif: ESP8266 image header](https://docs.espressif.com/projects/esptool/en/latest/esp8266/advanced-topics/firmware-image-format.html)
- [ESP8266 Arduino flash filesystem layout](https://arduino-esp8266.readthedocs.io/en/latest/filesystem.html)
- [Arduino ESP8266 Updater OTA staging implementation](https://github.com/esp8266/Arduino/blob/master/cores/esp8266/Updater.cpp)
- [smalltv-mod two-stage SmallTV Ultra procedure](https://github.com/giovi321/smalltv-mod/blob/main/docs/src/content/docs/getting-started/flashing.md)
