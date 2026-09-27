# One SmallTV, no soldering: Wi-Fi-only installation decision

**Owner constraints:** one working SmallTV-Ultra on stock V9.0.44, no second board, no soldering or UART/PCB pin wiring, and a USB-C port that does not enumerate a COM device even with a known-good data cable. Work offline until a separate explicit owner authorization for a named flash file and action.

## 27 September 2026 update — FS-less 4m3m direct-path research

**This earlier PR #8 plan is retained as historical evidence and not an owner-upload guide.** The newer [first-install decision packet](FIRST_INSTALL_DECISION_PACKET.md) recognizes the owner-observed factory data size as an exact 4m3m linker fingerprint and rebuilds SHINO's FS-less application as **4m3m**. Direct factory→SHINO U_FLASH staging and later running SHINO→OEM V9.0.44 application staging fall *before* the inferred stock filesystem in the modeled Arduino updater. The older 4m2m rollback or second hop from the 4m1m loader **does NOT** preserve manufacturer file sectors. The source/CI safety decision prioritizes a reviewed direct path over a destructive two-hop fallback, while OEM live OTA acceptance, true owner flash map, boot and brick recovery remain unverified. No hardware operation was authorized or performed.

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
| SHINO application → OEM V9.0.44 | Original app pinned; nominal OTA staging arithmetic under `4m2m` can be modelled | PR #9 implements an authenticated, exact-OEM-only return in both the running SHINO app and boot-loop Rescue mode, with generic OTA removed. Runtime restoration remains untested; OEM filesystem layout and preferences under the custom FS map remain unknown. |
| Loader or SHINO becomes nonbootable | No software-only verification can demonstrate reliable Wi-Fi recovery from a nonbooting application | **No recovery via Wi-Fi** if neither code nor an independent resident rescue service starts. Hardware recovery remains unavailable by owner choice. |

## Interpretation of the preflight result

`tools/wifi_flash_preflight.py` returns `OFFLINE_PREFLIGHT_ONLY__OWNER_FLASH_NOT_AUTHORIZED`, even if all known headers, digests, source layout checks and modeled staging budgets pass. This is intentional. Its success is not a deployment approval.

The official 9.0.44 ESP8266 8-byte image header contains SPI flash size/mode/frequency, **not the original firmware's complete physical filesystem partition map**, and an application OTA package does not contain the 4-MiB owner flash.

### Why we do not embed the OEM BIN inside every SHINO build

It consumes about 494 KiB of valuable application storage, increases OTA-fit problems, duplicates OEM-proprietary code and is inaccessible after a hard boot failure. We instead preserve a user-supplied local verified OEM binary plus an authenticated factory-return endpoint now implemented in SHINO's source (normal and boot-loop Rescue modes), disabled for writes in the default build. Even then, only a working app/recovery route can receive it.

## Preparatory work, no device contact

1. Keep both official V9.0.44 ZIP and its extracted, verified BIN privately on your Windows PC outside GitHub.
2. Compile and inspect the exact current SHINO + loader pair in ephemeral CI, not arbitrary mismatched binaries.
3. Review PR #9's source hardening and validate it at runtime: per-build AP/API/Rescue secrets, no generic OTA or open `/legacyupdate`, no direct or traversal-based `/config.json` serving.
4. Confirm the exact-OEM-only return compiled in **both** SHINO app and its boot-loop Rescue mode. It is default read-only; the experimental path must remain offline until separately approved. Neither mode survives an unbootable CPU/flash/bootloader.
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

## First real offline three-image run (2026-09-26)

The workflow built the **actual source code at the then-current PR head** and matched both OEM and candidate MD5 against the generated experimental loader; the 9 synthetic regressions and full offline transition analysis passed.

| Image | Actual BIN size | SPI header |
|---|---:|---|
| Official Ultra-V9.0.44 | 494,144 bytes | DIO, 4 MB, 40 MHz |
| Candidate-locked SHINO mini-loader | 312,256 bytes | DIO, 4 MB, 40 MHz |
| Current SHINO firmware candidate | 464,448 bytes | DIO, 4 MB, 40 MHz |

Using the **committed** `4m1m` and `4m2m` source layouts, and 4096-byte sector rounding, the simple model estimates **2,363,392 bytes** between the active mini-loader and the SHINO staging start, and **1,134,592 bytes** between active SHINO and the OEM staging start. This is a geometry check of the source assumptions, **not a physical acceptance/restore proof**, and does not establish the manufacturer's live original OTA size or full original filesystem map.

The original stage's capacity and recovery when neither application boots remain **UNKNOWN**; the device upload gate is closed. [CI run](https://github.com/shinobione/SHINO-TV/actions/runs/36265717160).
