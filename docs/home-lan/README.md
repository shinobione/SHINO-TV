# P1 persistent household Wi-Fi — offline implementation

**2 October owner preparation:** the guarded CI images below remain offline evidence. An actual private active candidate and its exact-image approval gate are now documented in [OWNER_INSTALL_GATE.md](OWNER_INSTALL_GATE.md). No installation or first credential write is authorized; do not use the procedure below against today's Mission 8.

Implementation continues from PR #40 head `a3d9fdb4fc1fe1eb1b49837551e0610c9ca88e5d` on `codex/shino-tv-p1-home-lan`. PR #39, PR #40 and the installed Mission 8 image are unchanged. **Offline implementation PASS; P1 device/release gate HOLD. No device contact, installation, network migration, merge or production provisioning has been performed or authorized.** R3 PARTIAL / R10 BLOCKED remain unchanged.

## Configure once, reconnect independently

The opt-in active FirstBoot implementation uses the SDK's saved station configuration. It loads that configuration on boot, enables DHCP and connects without Windows. There is no credential file, password constant, filesystem mount, EEPROM initialization or custom raw-flash writer on the TV. Arduino global Wi-Fi persistence remains disabled for mode/AP/retry operations. The sole persistent station setter is reached by explicit authenticated Change or Forget, after layout validation; saved readback must match before acknowledging success. An identical Change and an already-empty Forget perform zero persistent writes. Association, password, DHCP and router failures never erase the saved configuration.

The protected AP starts at boot; when credentials are valid, it temporarily coexists with STA during connection/recovery. Association plus a nonzero DHCP address selects ONLINE. After 15 seconds online, with no AP client or live provisioning intent/window, the AP stops and normal operation is STA only. The initial attempt is bounded at 20 seconds; recovery retries every 60 seconds without rewriting flash. Router loss starts protected AP recovery and a new attempt. An AP client keeps configuration reachable. AP+STA uses the ESP8266's one radio/channel; its resource cost and AP behavior during scans remain **physical HOLD**. No open AP fallback is permitted; AP startup failure stops networking.

`POST /api/v1/bridge/wifi/recovery` reopens the protected AP for five minutes from an authenticated LAN connection. Change/Forget are then performed on that AP. Intent GET and the write POST require fresh Digest, not a dashboard cookie. A 128-bit random, peer/interface-bound, one-use intent expires after 60 seconds. Wi-Fi credentials travel in a maximum 99-byte binary body, never in a URL, query, JSON response or log. The local client sends Digest before that body. Plaintext is protected in transit by the private WPA2 AP; SDK flash storage is conventional ESP8266 plaintext storage, not encryption at rest. Do not publish future flash dumps.

## Reviewed non-volatile storage

Pinned platform: espressif8266 4.2.1, Arduino Core 3.1.2, **NONOSDK22x_190703 / NONOSDK=0x22100**, same as P0. The SDK2 `station_config` is 112 bytes; SDK3 structure fields are conditional and are not assumed in this build.

| 4 MiB flash offsets, end exclusive | Owner / use |
| --- | --- |
| `0x000000–0x100000` | Application and bounded application OTA staging ceiling |
| `0x100000–0x3FA000` | Linked filesystem, remains unmounted |
| `0x3FB000–0x3FC000` | EEPROM, unused by P1 |
| `0x3FC000–0x3FD000` | RF calibration, outside credential writes |
| **`0x3FD000–0x400000`** | SDK system parameters: redundant data slots + control sector |

The actual linked SDK disassembly shows the shared station helper loading/saving system parameters at **chip sector count minus three**. The persistent and current setters select that helper with 1 and 0 respectively. The protected SDK writer uses its own slot/checksum/control management. This is source/link evidence, not a proof of behavior under arbitrary power interruption. `home_lan_resources.py` verifies the pinned source/archive hashes, linker offsets, SDK helper disassembly and paired ELF resources. Runtime writes require actual and header flash sizes of exactly 4 MiB and the exact `4m3m` FS/EEPROM offsets. Mismatch, SDK error or failed readback returns HOLD; there is no autoformat or automatic write retry.

SDK parameters are shared with OEM software. P1 changes the SDK station configuration deliberately; it does not claim preservation of every OEM setting. A previously saved configuration is only reused when it passes the bounded credential and WPA2-threshold checks; other existing data remain untouched until explicit Change/Forget. The pinned OEM application-return implementation and global-signing prohibition remain intact. Its writer is compile-tested and restricted to AP; **a physical OEM return after a P1 credential write is NOT RUN**. The application image is not a full-chip backup or no-boot recovery.

ESP8266 uses 2.4 GHz and supports WPA2; P1 sets the SDK authentication threshold to WPA2-PSK. Select the household router's **2.4 GHz WPA2/AES-compatible** service; a shared dual-band SSID is acceptable because this radio cannot associate to 5 GHz. Actual association with the owner's router is NOT RUN. Primary references: [Espressif ESP8266EX specifications](https://documentation.espressif.com/0a-esp8266ex_datasheet_en.html), [pinned Core persistence documentation](https://arduino-esp8266.readthedocs.io/en/3.1.2/esp8266wifi/generic-class.html).

## LAN HTTP and LINK address configuration

One port-80 owner serves both interfaces. The P1 overlay bounds ordinary headers to 512 bytes per line / 2,048 bytes aggregate / 32 fields and the existing 2,000 ms owner deadline. Critical duplicate headers fail closed. Provisioning and metrics body reads use the remaining 2,000 ms owner budget; metrics additionally require canonical 16–384-byte JSON framing. Historical OEM multipart behavior is unchanged. Before the provisioning body is allocated/read, the callback checks numeric Host, same-origin when supplied, local socket/interface, peer subnet, method, fresh Digest, MIME, canonical length and transfer-busy state. No proxy, redirect, CORS or credential-read endpoint is added. Cookies bind to peer **and local interface address**; address changes invalidate them. LAN exposes dashboard/assets, metrics, sanitized status and read-only OTA capabilities, plus the explicit AP-reopening action. OEM upload and qualification/enrollment controls are denied on LAN before body handling. Signed media retains its separate bounded owner, signature/nonce/CRC/SHA checks, 8-second transaction deadline and 6,200-byte crypto stack; the expected signed authority comes from the accepted local socket, never a supplied Host.

mDNS is deliberately omitted from this bounded slice: no additional responder, UDP socket or unmeasured heap cost. Discover/configure the address through the household router's DHCP lease list; authenticated AP status exposes `sta_address` and `sta_mac` to identify the correct lease. Use the actual private IPv4, not an assumed domestic IP. A router-side DHCP reservation can keep that address stable. When DHCP changes it, update LINK's local target; there is no LAN scan or duplicate sender.

From the repository directory, after a future authorized migration:

```powershell
py -3 companion/shino_link.py --set-target --host <ACTUAL_PRIVATE_DHCP_IP>
```

This updates the existing local configuration and running sender (on its next scheduled attempt, at most its 30-second retry interval). It refreshes Digest state without creating another sender or changing autostart. To use recovery, manually join the private SHINO AP, then run:

```powershell
py -3 companion/shino_link.py --recovery-target
```

Four-value schema, tray, autostart, Digest continuity correction, two-second normal cadence and six-second device TTL are retained. No permanent music sender is introduced.

## Exact future owner-local password procedure — do not run yet

This procedure becomes usable **only after separate approval and installation of an exact reviewed private P1 image/hash**, recovery verification, and authorization of the first local credential write. Today's installed Mission 8 firmware has no P1 provisioning interface. Offline CI binaries have a volatile zero startup guard and are not installable owner builds.

1. Confirm on the Freebox locally that the household service has 2.4 GHz enabled with WPA2/AES compatibility. Read the password from its display/QR privately. Do not paste it in chat, a shell argument, source file or credential file. Use an interactive local console without terminal recording/transcription; no redirected/piped input.
2. Stop any other tool using the shared Digest challenge during provisioning. Manually join the existing private SHINO AP with its separate private AP key. Keep the future matching-build **HTTP Digest** `credentials.txt` outside the repository; that file must never contain the household Wi-Fi password.
3. Run this command in the repository directory, substituting only the private Digest-file path:

   ```powershell
   py -3 companion/provision_home_wifi.py --change --credentials-file 'C:\PRIVATE\matching-build\credentials.txt'
   ```

4. Enter the household SSID at the local prompt. Enter the Wi-Fi password twice at the hidden prompts. The command has no Wi-Fi-password flag, refuses piped input and refuses an echoing `getpass` fallback. It uses memory only, no configuration/password file, output body or debug HTTP log. Mutable payload buffers are cleared when finished; Python/SDK internal copies are not claimed to be a formally zeroized memory system.
5. Require the **saved-state readback verified** acknowledgement. The TV retries the saved network independently. If the acknowledgement is lost, the command stops without an automatic write retry; inspect protected-AP sanitized status first. A repeated identical explicit Change is wear-free. An association failure keeps the saved key and AP recovery.
6. Obtain the actual DHCP address from authenticated AP status / the Freebox lease list. Return Windows to its usual LAN and update the existing LINK target with `--set-target`. Normal reboot/power restoration/router restart needs neither Windows nor another password entry.

To change/forget while normal STA operation has turned the AP off, first run the following with the actual private LAN IP, then manually join the protected AP:

```powershell
py -3 companion/provision_home_wifi.py --open-recovery --host <ACTUAL_PRIVATE_DHCP_IP> --credentials-file 'C:\PRIVATE\matching-build\credentials.txt'
```

Run the same `--change` command for a replacement network, or explicitly remove saved station credentials:

```powershell
py -3 companion/provision_home_wifi.py --forget --credentials-file 'C:\PRIVATE\matching-build\credentials.txt'
```

Forget additionally requires typing `FORGET` locally. It clears SDK station credentials only and retains the protected AP. If the router is unavailable, automatic AP recovery provides the same configuration path without the LAN reopening command.

## Offline evidence and remaining gate

Public guarded P0/P1 graphs, same compiler/Core/SDK/linker and real M8/V2.2 sources:

| Profile | BIN bytes | Static DRAM bytes |
| --- | ---: | ---: |
| P0 paired baseline | 449,072 | 54,016 |
| P1, OEM writer disabled | 460,208 | 55,196 |
| P1, exact OEM writer compiled with inert public pins | 463,440 | 55,244 |

P1 delta versus P0: **+11,136 BIN / +1,180 static DRAM**. SDK configuration/read/write compiler frames: 128–160 bytes; provisioning apply 432 bytes; parser 240 bytes; owner 128 bytes. These are individual compiler frames, not cumulative stack high-water. P1 adds no persistent application credential heap allocation or framebuffer. Header/String/route allocations and SDK AP+STA heap/block costs still require native measurement. See [numeric linked evidence](resources.json).

- HOST-PASS: 183 shared controller/storage/protocol assertions, including 100 simulated boots with zero writes, wrong credentials/router/DHCP failure retaining saved state, loss/retry/recovery, wraparound, unsafe layout, SDK/readback failure, explicit Change/Forget.
- HOST-PASS: 34 actual target-handler/pinned-parser/Digest loopback checks with mocked radio/SDK and three host-only linker-offset substitutions; two simulated persistent writes total (Change and Forget), zero owner-device writes. Authentication/framing refusal occurs before provisioning-body reads.
- HOST-PASS: actual BearSSL/native signed 32px receiver + exclusive scene renderer, 33 scenarios / 268,999 checks at each of AP and LAN authorities; Windows MSVC locally. Linux exact-head CI additionally requires ASan/UBSan.
- HOST-PASS: six local provisioning/Digest/retarget tests; retained LINK 18, telemetry Digest nine, FirstBoot source nine, and browser-session source four tests. Full CI is separate exact-head evidence.

**HOLD:** STA/AP radio and DHCP behavior on the owner unit, password/router/reboot/power-loss reconnection, saved-sector survival/corruption behavior, LCD and telemetry timing during scans, heap/largest-block/stack high-water, and OEM return after persistence. Historical M8 settled heap/block were 16,384 / 12,496 bytes; subtracting P0+P1 static increments alone gives 13,604 / 9,716 bytes, before unknown SDK costs. That arithmetic is not a new runtime estimate and offers no safe native memory margin. No candidate installation is approved from these numbers.

Next physical gate must name an exact private image/hash and separately approve installation and local provisioning. Measure idle STA, transient AP+STA, fallback/retry, signed 32px transfer/replacement and OEM return readiness; stop on reset, corruption, allocation failure, unsafe heap/stack or loss of recovery. No 48px experiment, native updater or merger is part of this milestone.
