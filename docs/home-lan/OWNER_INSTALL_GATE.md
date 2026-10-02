# P1 private owner candidate — controlled installation HOLD

**Bounded client correction completed, still no upload authority:** the actual
private uploader now uses tested one-attempt HTTP diagnostics; original error
code/body remain unrecoverable. Exact installed-M8 Digest/multipart checks pass
offline; no P1 rebuild or device contact. [Evidence and corrected owner-review
plan](OEM_UPLOAD_CLIENT_INVESTIGATION.md). Another actual Hop 1 needs new explicit
owner authorization; earlier single-attempt consent must not be reused.

**Current 2 October state:** the owner authorized both exact installation hops
below, including expected installation reboots, and confirmed current normal LCD.
Immediate preflight passed. One M8→OEM upload attempt raised an HTTP error without
staged acknowledgement. STOP without retry or Hop 2; same M8 boot remains
responsive, telemetry fresh and recovery capability enabled. P1 NOT INSTALLED /
DEVICE NOT RUN; zero persistent household credential writes. The cause and any
OTA staging-sector writes remain unknown. [Actual attempt/evidence](DEVICE_INSTALLATION_2026-10-02.md).
The preparation record and unexecuted future sequence below are preserved as
dated provenance; their earlier authorization-pending language is superseded by
the explicit owner authorization and the single-attempt stop above.

2 October 2026, Europe/Paris. Continue Draft PR #41 from accepted `ce718f0c47398ff70043b012cd3fb5d94c25aa74`; prior 13/13 push/PR CI is historical OFFLINE PASS. **STOP: no firmware upload, OEM return, reboot, network switch or persistent credential write has been performed in this preparation.** P1 DEVICE qualification is NOT RUN. The only current-unit contact was bounded authenticated GET-only preflight.

## Exact candidate and retained rollback

| Artifact | Bytes | SHA-256, locally reverified |
| --- | ---: | --- |
| New private P1 owner candidate | 464544 | `31e3f225744bd806df3302dbf3355770a313f8b71f65b33fd6e2f431449b0be5` |
| Current Mission 8 retained image | 446944 | `269fcf2be7e61b4f581f892f36c519cca5ebf1ef41759d9923d9df90aad682fa` |
| OEM Ultra-V9.0.44 application | 494144 | `a6421f5bfee7860d97bed26620c346b8008f503e513702d4bfdf6e01010a7718` |
| V2.1 review-003 rollback | 405712 | `3252ba5cd1f85683945d4d9a87ce49118568c0977605debc089267f54d7f3b0e` |

The exact source/ELF and pairing metadata are recorded in the private packet and sanitized report; recheck final PR HEAD and exact-head CI at delivery. The initial preparation image is retained privately as provenance; only the final image in this table may be proposed for installation. Private images, ELF, compiler log, retained policy and matching credentials remain outside Git in the local owner kit. No household password or signing private key is read/generated/copied by the preparer. AP and Digest credentials match retained review-003 and the compiled P1 image; the media public point matches the exact retained Mission 8 image. LINK configuration, sender and autostart remain untouched.

Private `owner_compile` is active, without the public volatile zero startup guard. Public P0/P1 CI profiles remain inactive and refuse owner preparation in CI. OEM-only return is enabled with the actual manufacturer MD5 pin; native signed OTA remains zero, no global signature installation is added. Receiver, 6200-byte StackThunk, 2048-byte metadata arena, six-second metrics TTL and eight-second media deadline remain unchanged. V2.2 exclusive scenes use the existing 448-byte row; no clock/weather provider or 48px qualification is added.

The final firmware was compiled at `32814f661975046d287d8ecc1f8fbc17934448a8`. Individual compiler frames are owner observation 96 B, provisioning apply 432 B, parser 240 B and HTTP owner 128 B; these are not cumulative/native high-water.

Image validation: both DIO/4 MiB/40 MHz ESP8266 image headers; pinned Core whole-image CRC and both original segment XOR checks after zeroing Core-reserved CRC fields; actual ELF `_FS_start=0x40300000`, `_FS_end=0x405FA000`, `_EEPROM_start=0x405FB000`; pinned storage source/archive hashes. Relative flash offsets are FS `0x100000–0x3FA000`, unused EEPROM `0x3FB000`, RF `0x3FC000`, SDK parameters `0x3FD000–0x400000`. No filesystem image/mount or EEPROM initialization is introduced.

Private candidate static DRAM is **55,504 bytes**, +1,488 versus public paired P0 (54,016). This includes private OEM/credentials and read-only qualification observations; the accepted public P1 delta remains +1,180. BIN is 29,600 bytes smaller than the pinned OEM application. OTA arithmetic gives 86,016 bytes of gap in both OEM→P1 and P1→OEM staging, below the 1 MiB ceiling and outside inferred stock FS/SDK sectors. These are linked/image/model results, not live P1 heap, OEM upload acceptance or power-interruption proof. [Sanitized numeric evidence](owner-preflight.json).

## Current installed unit — refreshed read-only evidence

At **00:30:18 CEST on 2 October**, GET status reports 446944-byte FirstBoot Mission 8 lineage, actual flash 4194304 bytes and declared free sketch space 598016 bytes. Native diagnostic boot is **2962927510**, reset reason 4, image 2048 bytes retained, no pending/body/staging, secondary refs zero, zero recorded allocation/canary failures. Sampled free heap/block/continuation at that GET are **19592 / 16672 / 1728**. The separate one-second heap summary is SATURATED at 1024 samples; its older extrema are not current phase minima. No runtime flash SHA endpoint exists: identity is the observed size/boot/capability plus retained exact-image installation history, not a fresh flash rehash.

OEM capability GET reports `write_enabled=true`, exact 494144-byte pinned hash, `full_flash_backup=false`; native OTA reports no writer or upload route. This refresh proves capability presence in the running M8, not a future successful P1 rollback. LCD observations must be obtained from the owner immediately before and after any separately approved installation. Current source and historical physical receiver PASS remain distinct from new P1 DEVICE PASS.

## Allocation lifetimes and measurement limits

| Path | Actual source lifetime / coexistence | Physical uncertainty |
| --- | --- | --- |
| STA association / DHCP / retry | SDK default is copied to local 112-byte station structs; RAM-only current setter/connect/DHCP calls. No retained application password buffer and no boot/retry credential writes. | SDK station, DHCP, packet/scan allocations and fragmentation are opaque; binary/source call-site inspection does not bound their peak. |
| Temporary protected AP+STA | AP begins with STA, stops after 15 s stable DHCP with no AP client/intent/recovery window; one radio. SDK AP config/mode calls use current RAM settings. | AP station state and SDK/LwIP resources may overlap scans, association, HTTP and retained art; AP shutdown is not proof that all heap coalesces. |
| Local provisioning | Header Strings / collected fields / bounded 99-byte binary body and parser copy; stack Credentials and SDK structs are transient and wiped. SDK protected save/readback only on explicit Change/Forget. Deferred radio transition occurs after response. Media/OEM busy rejects provisioning before body handling. | Request/Digest/String copies and SDK protected writer internal lifetimes have no complete allocator bound. No claimed flash power-loss qualification. |
| Scenes / row | Renderer and 448-byte owned row are static; no renderer malloc or fullscreen buffer. One loop-side image borrow ends before ingress can replace it. | Actual LCD SPI/yield latency, render slice duration and coexistence with SDK callbacks remain unmeasured. |
| Signed 32px transfer / replacement | Gate1 ECDSA completes and secondary stack is freed **before** body allocation (max 552 B). Begin metadata arena 2048 B is freed before staging; old committed 2048 B image remains during metadata validation, then releases on accepted Begin. One new 2048 B staging allocation moves to sink on Commit; no Commit copy. Tile ECDSA can coexist with retained staging. Terminal body/staging release is preserved. | Different allocator histories may fragment the 6200 B block even with ample total heap. Keep historical failures and same-ownership phase comparisons. |
| ECDSA StackThunk | Checked lazy 6200 B contiguous heap allocation per key/proof call; stock repaint/switch/canary/usage scan; release sets refs/pointers back to zero. Existing eligibility only checks allocation size, not the qualification reserve below. | SYS/continuation callbacks and SDK stack coexistence require actual high-water. Prior M8 maximum 2708/6200 is not P1 proof. |
| Telemetry / status | Four-value state remains RAM; Digest POST and six-second TTL. JsonDocument, response String, collected headers/cookies are dynamic per HTTP transaction. Native/LCD counters are serialized read-only on existing authenticated status for STA-only measurements. | Status itself allocates; cooperative prior samples can miss short SDK/JSON peaks. Never reset telemetry TTL, increase body/deadline or call sampled minima a complete runtime bound. |
| OEM recovery | Compiled retained writer stays AP-only, mutually exclusive with media/provisioning. Core Updater would allocate a flash-sector buffer and MD5 state only during separately authorized OEM upload; P1 adds no global signing verifier. | Read-only capability GET does not exercise writer, staging or boot. No firmware POST/dummy upload to test recovery. |

Read-only P1 status observation contains boot/reset, sampled heap/block/continuation minima, allocation/canary failures, secondary usage/refs, arena peak, image/pending and renderer timing. It does not enroll, issue challenges, reset counters or write storage. Existing `/m8` enrollment/challenge/phase-reset controls remain AP-only and are qualification-only; the production trust gate remains R10 BLOCKED. Native OTA stays inactive and R3 PARTIAL.

## Explicit physical abort gates

These are conservative **qualification stop rules**, not runtime predictions or new firmware retry behavior. No static-RAM subtraction is used to predict free heap or largest block.

- Before enrollment, starting any initial/replacement 32px cycle, or the first credential write: require **measured free heap ≥12,344 B and largest block ≥10,296 B**, continuation free/high-water margin ≥1,024 B, no active secondary stack/body/pending transfer and zero new failure counters. Heap reserve = 6200 stack + 2048 image + 4096 reserve; block reserve = 6200 + 4096. Applying both to already-retained-image state is deliberately conservative. SDK costs remain additional uncertainty.
- During every boot/network/provision/media phase: stop if sampled free heap or largest block drops below **4096 B**, continuation margin below **1024 B**, secondary used maximum exceeds **5176/6200 B**, or any canary/allocation/busy failure, corruption, watchdog/reset/boot change not explicitly requested, frozen LCD, or lost protected recovery occurs. A missing/invalid resource observation prevents starting the next demanding operation.
- After settling in the same ownership/network/client state, stop on a **>1024 B heap or block regression** from that phase's established P1 baseline, or a repeated declining trend across three comparable cycles. Compare STA-only to STA-only and AP+STA to AP+STA; do not compare an empty receiver to retained art.
- A six-second stale telemetry event or signed transfer unable to retain the 8-second deadline stops that test and leaves its gate HOLD. Do not retry uncertain firmware/credential/media writes or weaken deadlines. Stop before further tests on reset, unsafe memory, corruption or unavailable recovery; leave the currently responsive application running for diagnosis. Any actual OEM recovery needs separate approval.

## Wi-Fi-only installation chain — approval still required

There is no active SHINO→SHINO updater. Proposed chain: current responsive M8 → exact OEM application through its Digest-protected pinned OEM-only receiver; rediscover the actual OEM LAN address and verify SmallTV-Ultra / Ultra-V9.0.44 `/v.json`, physical OEM display and current `/update` form; OEM `/update` → **only the exact P1 BIN above**, once. The historical OEM IP is not assumed. USB-C supplies power only; no serial/UART/JTAG/PCB access.

Each hop is a real application write/reboot. The installation approval must explicitly name **both operations and both hashes**; approval of P1 alone cannot silently authorize the OEM first hop. A lost upload acknowledgement stops the chain without retry; boot/recovery failure stops before the second hop. Stable power and exact pre-upload file rehash are mandatory. No routine extra flash is planned for visual adjustments.

Rollback files are application-only. They cannot restore a damaged OEM filesystem, all original settings, SDK credentials, or a nonbooting chip. P1 station credentials reside in OEM-shared SDK sectors; an OEM return may alter/reuse those settings. No independent Wi-Fi/no-boot rescue or arbitrary power-failure safety exists. A new application, AP+STA runtime load and the OEM detour on the sole unit remain material risks despite offline PASS.

## Exact sequential physical plan — not executed

1. After explicit exact-chain installation approval only: rehash all images, refresh current M8 read-only identity/geometry/OEM capability, confirm owner LCD and existing LINK; perform the two individually named hops once with live identity/form checks between them. Verify P1 boot/reset identity, private AP, sane display, exact runtime 4m3m/storage gate, OEM-only capability and no native updater. Stop at every abort condition.
2. Keep Windows on the protected AP and verify the existing single LINK sender delivers all four fresh values for three minutes; observe idle and HTTP heap/block/stack. No media/provisioning yet. Existing valid WPA2 SDK credentials may already reconnect at boot (read-only reuse, no new flash write); inspect `wifi_saved/state` and disclose it. Do not silently Change/Forget such state or claim first-write testing occurred.
3. Present those actual boot/display/AP/telemetry/resource observations and request **separate owner confirmation for the FIRST persistent credential write**. Installation approval is not that confirmation. Only then use the [hidden interactive procedure](README.md#exact-future-owner-local-password-procedure--do-not-run-yet) with the matching private Digest file, household SSID entered locally and hidden password twice. No household secret in arguments, files, logs, Git or chat.
4. Verify saved-state readback acknowledgement once; no uncertain-write retry. Verify actual 2.4 GHz WPA2 household association and nonzero DHCP IP from authenticated AP status/router lease. Record address/MAC only in private local evidence if needed.
5. Move Windows manually to normal LAN and retarget the **existing** LINK engine to the actual private DHCP address; fresh Digest and all four samples, three-minute continuity. No duplicate sender, autostart change or credential rewrite.
6. With AP clients disconnected and no intent/window, verify automatic AP shutdown after ≥15 seconds stable online operation; resource observations via LAN status. OEM compilation and native-OTA absence remain visible through authenticated status/capabilities; exact OEM hash/size/enabled metadata must be checked through its AP-only detailed GET after explicit recovery reopening, without upload.
7. Owner-controlled router interruption: measure protected AP fallback and continued saved state; restore router, wait bounded 20 s attempt / 60 s retry, verify DHCP/LAN telemetry and automatic AP shutdown. No Forget or persistent retry writes.
8. Owner-controlled SmallTV reboot: verify saved state, automatic household reconnect, same normal LINK sender and fresh telemetry. Reboot approval must be explicit; no unrequested restart.
9. Owner-controlled power removal/restoration while **idle, with no storage/OEM/media write in progress**: same saved-state/reconnect checks. This validates retention across ordinary loss, not interruption during an SDK flash write. No deliberately interrupted credential write on the only unit.
10. Verify protected AP fallback/reopening and return to ordinary LAN. Measure both network states and preserve exact OEM read-only metadata. Qualification `/m8` controls remain AP-only: for signed 32px initial/replacement plus exclusive LCD scenes, temporarily reopen/join recovery AP and retarget the same LINK sender; serialize challenge controls in quiet slots, preserve the finite no-body-retry plan and 8 s deadline. Verify secondary/body/staging cleanup, image 2048 B, arena ≤2048 B, title/artist clipping, zero music metric cards, observed render slices/resources and receiver Commit/replacement outcomes. Test return to STA-only and normal-LAN telemetry afterwards. This AP-based physical media pass does **not** claim LAN challenge/enrollment or production music integration; AP/LAN signed Host acceptance remains separate host evidence unless a reviewed LAN qualification mechanism is separately supplied.
11. Record actual phase evidence, timings and counter/ownership comparisons in PR #41 and active roadmap; distinguish OFFLINE PASS, current-M8 read-only PASS and new P1 DEVICE PASS/HOLD. No destructive OEM return to prove capability, merge, production provisioning, native OTA or Mission 9.

**Current decision: PRIVATE OFFLINE READY / P1 DEVICE HOLD / INSTALLATION AUTHORIZATION PENDING.** No installation or first persistent Wi-Fi write is authorized by this document.
