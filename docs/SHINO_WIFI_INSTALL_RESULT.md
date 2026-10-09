# SHINO // INSTALL — issue43 bounded offline result

Historical issue43 receipt. The later owner-requested memory attempt is in
[the maintenance result](SHINO_WIFI_MAINTENANCE_RESULT.md); it remains NO_GO.
The numbers and link-only description below are preserved as prior evidence.

**NO_GO. One principal blocker: simultaneous native memory floors are not
established.** This is a smaller working offline prototype, not an approved
physical image. Stop here; no new OTA phase or automatic follow-on work.

Owner authority: [issue43](https://github.com/shinobione/SHINO-TV/issues/43),
[installation decision](SHINO_WIFI_INSTALL.md), current roadmap. Starting SHA
`2b9ef75b4cf650277baae8da871ebe41f3227ddf`, existing branch
`feature/shino-tv-m9-flash-layout-liberation`, Draft/open/unmerged PR42. The three
owner documentation commits were fast-forwarded without discarding earlier work.
Final SHA and exact-head CI jobs are in the PR42 receipt after checks finish.

## Delivered

- Small application-only receiver derived from ArduinoOTA's Core begin/write/end
  mechanism, using a dedicated bounded TCP maintenance listener instead of HTTP.
  It is **not stock espota wire-compatible**. It needs no second HTTP server,
  filesystem writer, MDNS, RSA verifier or BearSSL6200B secondary stack.
- Fresh client/server nonces and HMAC-SHA256 bind private maintenance authority,
  expected device, command, exact bytes/SHA256 and build identity. Native nonce
  uses Core `os_random`; tests fix only the nonce seam and generate an ephemeral
  strong password. No public fixture key/password is supplied to the native graph.
  Capability is authenticated before upload; HTTP Digest/cookies grant no rights.
- U_FS/all other commands fail before Core begin. Only U_FLASH, exact DIO4MiB,
  reviewed4m2m staging before0x200000, current-app guard,64KiB..0xFEFF0 and a
  private StageA AP peer can admit.512B chunks,3s inactivity/60s transaction,
  exact length, SHA256, real staged rehash, Arduino CRC, both image segment ranges,
  overlapping segments and XOR checksums fail closed. No GZIP/end(true)/retry.
- An isolated Core header adaptation adds **only**
  `void shinoAbort() { _error = UPDATE_ERROR_STREAM; _reset(false); }`.
  It frees the buffer even after full staging, invokes no callbacks, and never
  calls end/flash/RTC/reboot. The pinned Updater.cpp body is unchanged. The adapted
  header is force-included consistently in all C++ TUs in the disposable graph;
  installed Core cache is never patched. Prior S/T adapter/evidence are unchanged.
- Windows Tkinter GUI + `SHINO-INSTALL.cmd`, CLI verification, exact local manifest,
  hash/image checks, expected identity, explicit confirmation and progress/results.
  An upload ACK means STAGED_PENDING_BOOT_CONFIRMATION, not success. Future boot
  verification requires a fresh authenticated expected build identity, with no
  upload retry. **QUALIFIED_LIVE=false**: GUI install/consent disabled, even CLI
  `--live` fails before credentials or sockets. There is no override switch.

The public native graph reserves the real receiver/network objects and retains
only internal function addresses. It does not construct a receiver, provide a
key, start maintenance, execute flash/RTC/reboot or alter existing HTTP routes.
Native network/LCD update activation and physical high-water are **not qualified**.
The four cards/TTL/StageA/LINK are preserved as existing source and regression
evidence; these tests do not establish LINK during a physical update or after an
actual reboot. GUI source is delivered; no native GUI screenshot or visual
acceptance is claimed in this session. CLI and install-disable controls are tested.

## Actual paired public Xtensa builds

Both actual full StageA copies use identical public inert policy/version,
Core3.1.2/platform4.2.1/compiler10.3.0,4m2m/DIO and exact dependency source trees
(ArduinoJson7.4.3/GFX1.6.4/AnimatedGIF2.2.0). No private image/policy/backup input.
The images are compile evidence; not replacements for the installed freeze.

| Local quantity | StageA | StageA + small receiver | Delta |
| --- | ---: | ---: | ---: |
| BIN | 399248 B | 406448 B | +7200 B |
| Linked flash | 395091 B | 402295 B | +7204 B |
| Static RAM including.noinit | 39784 B | 41188 B | +1404 B |
| .noinit | 56 B | 56 B | 0 B |

Reserved native receiver/network object1192B includes the persistent512B I/O
buffer, SHA256/session fields and Core updater object. No large body String or
RSA dynamic allocations. Known Core staging allocation4096B; key payload32B.
Temporary HMAC contexts use stack. Compiler frames: pump112B, line720B, MAC464B,
staged verification400B, segment parser352B, Core end192B. Partial auth path1296B,
partial staged-verify path1584B. Deeper libc/crypto/network/flash/SDK/interrupt
frames remain unknown; these are not stack high-water measurements. Owner3248B
watermark is not blindly subtracted from a sequential call path.

Floors remain **heap20480, largest16384, stack2048, fragmentation<=25%**. Owner
minima30224/30008/3248 are baseline observations, not simultaneous OTA evidence.
The receiver requires at least25600 heap before allocating4096B, then checks
the unchanged floors before each chunk and commit. Guards do not bound transient
socket/SDK/allocator allocations. In one explicitly conservative scenario:
`30224 -1404 static -4096 Updater -4096 TCP allowance -32 key =20596 B`, only
**116 B above the heap floor before further costs**. The4096 TCP allowance is an
illustrative reserve, not a measured upper bound; HTTP/client/pbuf/SDK ownership,
allocator metadata and fragmentation are unbounded here. A plausible small ELF
alone therefore does not prove the requested simultaneous budget. This single
memory blocker closes the physical candidate and live-installer gates.

## Offline validation

Real Python sender -> C++ receiver -> actual pinned unsigned Updater/BearSSL
HMAC/SHA256/MD5/eboot command with RAM flash/RTC seams, no sockets: **225 cases,
197 interruption boundaries**. Good and uint32-wrap uploads stage exactly one
copy; wrong password/HMAC, U_FS/unknown command, size, format, matching-hash bad
CRC, corruption, timeout/truncation/disconnect, duplicate transfer, low budget,
erase/write/read failures and every512B interrupted prefix (including full staging)
schedule no copy. Abort leaves no running updater and FS/tail RAM bytes unchanged.
This proves the new abort behavior for this adaptation, not ROM/power-loss safety.

7 installer tests cover exact manifest/image and closed no-contact delivery;
19 Digest sender +28 LINK continuity tests pass with existing synthetic inputs.
Existing exact-head StageA/Q/R/S/T/default/profile0/profile2 suites are retained.
Two source gates exempt only the four **new** issue43 installer files; every
preexisting firmware, companion and physical-writer path retains exact identity.
Dedicated CI executes host/manifest tests, the paired native builds and the NO_GO
gate, and uploads JSON evidence only. Final job counts belong in PR42's receipt.

No atomic rollback: commit schedules eboot application copy. Corruption/power
loss after commit may make Wi-Fi recovery unavailable; no promise of restoration.
The public proof includes the eventual explicit-install reboot implementation but
it is unreachable; no device operation executes in this task.

## Stop / first transition

NO_GO: do not download/install a physical candidate. Keep StageA intact and the
installer offline. There is no automatic next engineering phase. Current StageA
has no update receiver; any first receiver installation would separately require
an exact-image authorization and a proven method, potentially once via UART.
Nothing here authorizes that transition. Preserve prior owner mount PASS/runtime
HOLD/PARTIAL, >=180s LINK evidence, frozen399264B identity and unattributed404.

Device contact, serial I/O, physical flash writes, RTC writes, filesystem writes
and reboots: **all0**. No private credentials/key/BIN/backup read, frozen candidate
rebuild/refreeze/rebind, merge or deployment. S/T historical privacy deviation is
retained in its prior receipt; it did not recur in this issue43 task.
