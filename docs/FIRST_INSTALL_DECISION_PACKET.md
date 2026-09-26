# SHINO // TV — first-owner-device Wi-Fi decision packet (NO FLASH)

**Status:** source/CI and offline private-file review only. **The owner's ONE real SmallTV-Ultra remains stock Ultra-V9.0.44.** There is no spare card, soldering, hardware UART, actual device COM port, owner-specific full-chip backup or tested nonbooting Wi-Fi rescue. No BIN upload, merge, public release or device operation is authorized by this packet.

## 1. Precisely identified starting point

- Owner's prior safe GET-only report: **SmallTV-Ultra / Ultra-V9.0.44**. Photo/GIF FS \`total=3,121,152\`, \`free=1,056,268\` bytes. \`/update\` page has a multipart POST form and file field \`firmware\`, but has **not accepted any test file**. These storage numbers are **not** the stock application OTA capacity.
- Manufacturer's [matching official source ZIP at immutable commit \`55d7877\`](https://github.com/GeekMagicClock/smalltv-ultra/blob/55d7877fcba8b1cb7a66a0830d35d5b374bc8540/Ultra-V9.0.44/FW-Smalltv-Ultra-V9.0.44.zip): 349,377 B; SHA-256 \`cfbef50754ec552f9791878931c5f3643734de15f3c81cebdecf7ce05b28230f\`. Its ONE inner \`FW-Smalltv-Ultra-V9.0.44.bin\` is **494,144 B**, SHA-256 \`a6421f5bfee7860d97bed26620c346b8008f503e513702d4bfdf6e01010a7718\`. The ZIP is **only an application OTA package**: NO owner-specific 4-MiB readback, original FS/assets/settings/bootloader backup or guarantee of restoration from a nonbooting custom firmware.
- Exactly \`3,121,152\` B corresponds to the Arduino ESP8266 \`eagle.flash.4m3m.ld\` filesystem region \`0x100000…0x3FA000\` (exclusive end). This is a strong owner-report fingerprint of **4m3m-like FS geometry**, not source confirmation of the proprietary manufacturer's actual updater/layout.
- Four permanent LCD values and dynamic bar palette are locked by [Native UI V2](NATIVE_UI_V2_240_SPEC.md). The actual FS-less first-boot code has no application LittleFS mount/format or EEPROM initialization, serves flash-embedded authenticated UI and volatile RAM-only PC telemetry. Firmware's optional experimental OEM receiver is PINNED TO THIS ONE OFFICIAL APP IMAGE; **default firmware deliberately has NO OEM-return POST**.

## 2. Corrected decision from direct-vs-loader comparison

The earlier 4m2m SHINO source meant later U_FLASH staging could erase original manufacturer FS sectors even while our own dashboard never mounts a filesystem. The source branch for **this decision packet** therefore links the FS-less V2 under **\`eagle.flash.4m3m.ld\`** (one-MiB application+OTA ceiling), while still NEVER mounting or provisioning LittleFS. Linker \`FS_start\` determines Arduino's U_FLASH stage endpoint, even when the application uses no filesystem.

The table below is based on the reviewed ESP8266 Arduino [\`UpdaterClass::begin(size, U_FLASH)\`](https://github.com/esp8266/Arduino/blob/1475ed7d49fef5c5167061ac76abb6eced9abda5/cores/esp8266/Updater.cpp) and \`EspClass::getFreeSketchSpace()\`, not on a live trace of GeekMagic V9.0.44. It uses the last verified V2 experimental BIN snapshot **398,544 B** at PR #15 and the **312,256 B** temporary loader; the actual new 4m3m candidate size MUST be reinserted from the latest CI and independently checked private build before any physical decision. All addresses are byte offsets in a 4-MiB device; staging length is rounded upward to 4,096-byte sectors.

| Hypothetical transition | Source linkage used for modeled OTA | Stage sector range | Sectors inside inferred original stock FS |
|---|---|---|---:|
| Stock OEM → SHINO V2 DIRECT | Stock **inferred** 4m3m ceiling \`0x100000\` | \`0x09E000…0x100000\` | **0 B**, under 4m3m hypothesis |
| Stock OEM → mini-loader | Stock **inferred** 4m3m ceiling \`0x100000\` | \`0x0B3000…0x100000\` | **0 B**, under hypothesis |
| Mini-loader → SHINO V2 | Mini-loader source \`4m1m\`, OTA ceiling \`0x300000\` | \`0x29E000…0x300000\` | **401,408 B** — NOT original-data preserving |
| Old SHINO V2 (4m2m) → OEM app | Old source \`4m2m\`, OTA ceiling \`0x200000\` | \`0x187000…0x200000\` | **495,616 B** — NOT full factory restoration |
| **New FS-less SHINO (4m3m) → OEM app** | New reviewed source \`4m3m\`, OTA ceiling \`0x100000\` | \`0x087000…0x100000\` | **0 B**, under 4m3m hypothesis |

The OEM 494,144-B incoming image occupies **495,616 B of rounded staging sectors**. This new 4m3m layout also keeps future size-fitting SHINO→SHINO Arduino application OTA staging **before \`0x100000\`**. It cannot guarantee all manufacturer FS content survives unrelated proprietary update/SDK writes or hardware interruption. The temporary mini-loader is deliberately **NOT a preservation fallback** simply because its first BIN fits the manufacturer's nominal slot: its second update takes part of the original stock user-data area.

For all modelled transitions, the actual stock \`Update.begin()\` route and free OTA slot remain **UNKNOWN**, and the matched OEM bytes are not evidence that either restore route works on the owner hardware.

## 3. Option comparison — not a physical installation order

| Choice | What is supported by evidence | What is NOT supported |
|---|---|---|
| Stay on official V9.0.44 | No change to a currently working owner device. | Does not run the custom V2 LCD firmware. |
| **Research direct stock → exact private FS-less 4m3m V2** | Candidate smaller than current official application, exact source 4m3m stage model under inferred old FS start; one application OTA rather than two. | First OEM OTA acceptance, power-cut safety, real boot, exact owner FS and private AP/Digest communication have not been measured. If it does not boot, there is no guaranteed Wi-Fi rescue. |
| Stock → transient 4m1m loader → V2 | Source model says two images stage without colliding with running sketch. | **Overwrites old stock-file sectors on its second hop.** The trampoline itself is overwritten by the next OTA; no permanent recovery. Not a drop-in alternative if preserving stock GIFs/photos matters. |
| Later **running** experimental FS-less 4m3m SHINO → pinned OEM V9.0.44 app | The exact original ZIP and app digest are checked and the optional authenticated handler compiles; 4m3m source stages OEM before inferred stock FS. | Returning **only app bytes** cannot recreate deleted OEM files/settings, and if the app fails to boot no Wi-Fi rollback can be invoked. Runtime has NOT been tested. |
| Default read-only FS-less build | No application factory-return POST route at all, and no LittleFS image. | It cannot perform an owner-requested rollback over Wi-Fi; do not confuse it with the experimental OEM-return build. |

There is no brick-proof option available under the stated owner constraints. Direct software arithmetic is **not** owner authorization or guaranteed reversibility.

## 4. Exact private files that would have to exist BEFORE asking for permission

The publicly accessible GitHub CI intentionally deletes all generated BINs and per-build credentials. **The CI log byte count is NOT an exact, obtainable, owner's flashable release.** No named owner-ready artifact has been generated by this research task. If the owner later wants a physical decision, freeze one reviewed Git SHA and use a private Windows checkout to build/retain ONE PAIR of original and candidate data, never regenerate the firmware with mismatched random credentials afterward:

- \`official_9_0_44_original.zip\`: exact historical manufacturer ZIP with the two pinned SHA-256 checks.
- \`FW-Smalltv-Ultra-V9.0.44.bin\`: extracted and SHA-256-checked **application-only** BIN (kept separately; never a full owner flash backup).
- **ONE** candidate \`firmware/.pio/build/esp12e/firmware.bin\`, SHA-256, byte size and ESP8266 header from that same checkout; final owner candidate must be a **conservative FS-less 4m3m boot profile** with **experimental exact-OEM app-return enabled** if the owner wants Wi-Fi return while SHINO remains bootable.
- The **corresponding private \`firmware/include/shino_private_policy.h\` and \`firmware/private/credentials.txt\`** from that SAME build, protected locally, with separate randomized private first-boot AP password and HTTP Digest secret. Never include secrets in a public PR, CI artifact, report, screenshot or chat. The documented AP is \`SHINO-FirstBoot-<chip-id>\` — not the older \`SHINO-TV-...\` or the temporary loader's different \`SHINO-Recovery-...\`.
- No \`firmware/data/config.json\`, \`littlefs.bin\`, custom image ZIP pretending to be OEM, generic OTA writer or automatic FS migration.
- A sanitized offline \`owner_install_packet_gate.py\` report containing original and candidate SHA-256, no passwords/tokens, literal first/return staging models and explicit \`permission_to_flash: false\`. A separately verified \`python -m esptool image-info\` check must inspect the **same** candidate and OEM BIN to verify ESP image checksum without communicating with a serial port.

The optional mini-loader has separate credentials, own image pins and risks. It is NOT the assumed selected path. Its matching policy/BIN should never be mixed with the direct-candidate build.

### Private offline verification tool (does not create a firmware)

After all owner-private files were locally produced under an explicitly reviewed Git SHA, and when the original ZIP is available locally, run from that private checkout:

\`\`\`powershell
py tools/owner_install_packet_gate.py --official-zip "PRIVATE_PATH_TO_ORIGINAL_ZIP" --candidate-bin "firmware/.pio/build/esp12e/firmware.bin" --policy "firmware/include/shino_private_policy.h" --credentials "firmware/private/credentials.txt" --candidate-ini "firmware/platformio.ini" --out "research-local/owner-decision-report.json"
\`\`\`

Create the ignored \`research-local/\` folder beforehand. The checker only READS provided firmware/policy/secret files, compares them without publishing secret values, and creates a **new non-overwriting, sanitized report**. It fails if candidate/config/output is mismatched, the full factory OEM MD5 is absent from the compiled BIN, actual active AP/Digest secrets do not match the build, optional OEM writer was not compiled, chip header/size/map is wrong or the modeled direct/return stage touches old FS sectors. The script cannot independently establish OEM updater acceptance, a correct actual flash chip ID or an error-free physical OTA. It NEVER sends GET/POST or connects to the TV. No physical installation command is supplied here.

## 5. Owner review and stop conditions BEFORE any separate first-OTA go/no-go

1. Confirm the device is STILL stock Ultra-V9.0.44 with another owner-operated GET-only report and confirm the current LAN IP. Do not infer current version from the previous 26 Sept sample if it changed.
2. Ask whether preserving the manufacturer GIFs/photos and settings matters, and export what the stock UI permits BEFORE installation if desired; we have **no tested complete owner-specific backup method** over this chosen Wi-Fi-only path. Do not invent a readback feature or assert the official OTA ZIP restores data.
3. Freeze exact private *application* BIN + SHA-256, verified stock OEM ZIP/BIN, matching private policy/credentials, complete source SHA, official 4m3m linker config, physical device version and intended **direct** first transition. Do not mix binaries and secret files from distinct builds or use a CI log number as a local artifact.
4. Review independent esptool image checksums and the sanitized offline owner-packet and three-image models. An all-green GitHub Action is still a software-only check. Do **not** send an experimental dummy file to stock \`/update\` merely to provoke a size error.
5. Plan a stable power/network window, a clear stopped/failed response, and a private post-boot checklist: actual first-boot SSID appears, WPA2 private credentials function, Digest-protected status works, 240px four cards render, Windows RAM-only sender reports CPU/GPU/used+total RAM/temp, six-second stale state works, and no FS mount/update was requested by app. These cannot be ticked off before actual device operation. Stock files cannot be proven preserved by a SHINO FS-less mount because that mount is intentionally absent.
6. Separately document what happens on *any* critical failure: if neither application nor an independent resident rescue starts, **no Wi-Fi-only recovery can be promised**. Never describe the transient loader or original OEM application ZIP as brick-proof protection.
7. Request a **fresh, explicit owner decision** about the precise private image SHA-256 and *one named OTA action*. No instructions or automated button should perform a physical flash from this source PR, and owner saying “go” to offline work is not permission for an upload.

### Unresolved mandatory evidence

- Stock V9.0.44 updater's actual available bytes, proprietary validation, physical acceptance and boot of this exact SHINO image: **unknown**.
- Exact owner flash/FS layout (4m3m is inferred from report, not proven by owner-specific full read): **unknown**.
- True boot behavior, AP/Digest UX, Web metrics, LCD 240×240 operation, private OEM return, power-interruption safety: **untested on real hardware**.
- Full original stock filesystem/user configuration and independent serial rescue: **unavailable** under chosen constraints.
- Complete private owner-ready firmware+secrets pairing: **not produced in GitHub Actions and not yet archived on owner's PC**.

**Overall state: OFFLINE DECISION DOSSIER ONLY — NOT AUTHORIZED TO FLASH.**
