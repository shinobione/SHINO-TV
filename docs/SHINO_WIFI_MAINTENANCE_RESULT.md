# Minimal Wi-Fi updater — bounded memory attempt, 9 October 2026

**NO_GO. Single principal reason: simultaneous native memory floors are still
not established. Stop; no physical candidate, new phase or automatic follow-on.**

Authority: [latest owner decision on PR42](https://github.com/shinobione/SHINO-TV/pull/42#issuecomment-6075259487),
[installation contract](SHINO_WIFI_INSTALL.md), urgent hardware priority in
roadmap/handoff. Start `66fc33807ef5c8eb173c95e0f46d48fa19f8eb5c`, existing branch
`feature/shino-tv-m9-flash-layout-liberation`, same Draft PR42. The previous
[issue43 result](SHINO_WIFI_INSTALL_RESULT.md) and S/T evidence remain historical.

## Implemented

A callable StageA maintenance integration in disposable public compile copies,
with direct calls from the actual StageA cooperative loop to HTTP cleanup,
Native begin and Native pump, checked in the linked Xtensa disassembly. This is
no longer solely retained function-address evidence. The weak trusted consent
supplier returns false; no private key, live entry route or activation is wired.
Default, existing StageA/profile0/profile2 firmware files remain byte-identical.

The loop queues a separately authorized request and switches only outside the
HTTP callback. It closes HTTP admission, aborts its active and queued clients,
deletes both request argument arrays (not freed by the pinned Core destructor),
then destroys headers, handlers, Strings and closures before constructing the
upload service. Normal HTTP/dashboard/telemetry/JSON work pauses. The radio,
private WPA2 AP, read-only mounted configuration and TTL state remain intact.
Dashboard and metrics arrays are static: **zero dynamic reclaim is credited**.

HTTP and Native use one aligned placement slot, with one constructed owner at a
time. The maintenance identity/key are copied into static owner storage; the
key is erased on abort/cancel. Native backlog is one; it closes admission and
drains queued clients immediately after accepting its single owner. Idle join
timeout is 15s, then the existing 3s inactivity/60s transaction bounds apply.
Fault tests found and fixed a real disconnect leak: disconnected clients must
not be mistaken for a not-yet-accepted owner. All failures terminate the upload
attempt, release the Core buffer and close/drain connections.

Abort reconstructs the same normal routes with a fresh Digest challenge and
an honest stale redraw only when the unchanged floors and private AP still pass.
Insufficient resources or lost AP leaves a terminal HOLD, without repeated
reconstruction or radio changes. Entry/restore require 25600 B heap (5120 B
above the floor); restore's known initial HTTP payload is 724 B. This extra
reserve is conservative, not a reduction of any gate or a malloc/OOM guarantee.
Native control/auth/commit are separate non-inlined methods to reduce concurrent
stack frames. U_FS remains rejected before Core begin. Global signing or OEM
recovery coexistence fails compilation; S/T actual signed-Core/OEM interlock
qualification remains in the existing CI jobs.

## Actual public Xtensa resources

Same inert policy/version, 4m2m/DIO, pinned Core3.1.2/platform4.2.1/compiler10.3.0,
and identical ArduinoJson7.4.3/GFX1.6.4/AnimatedGIF2.2.0 source trees. No private
policy/key/image/backup or frozen-candidate rebuild. Local paired results:

| Quantity | StageA baseline | Callable maintenance | Delta |
| --- | ---: | ---: | ---: |
| BIN | 399248 B | 408000 B | +8752 B |
| Linked flash | 395091 B | 403847 B | +8756 B |
| Static RAM including .noinit | 39784 B | 41044 B | +1260 B |
| .noinit | 56 B | 56 B | 0 B |

Native sizeof: HTTP292 B, Native1192 B, shared owner1328 B, String12 B,
FunctionRequestHandler60 B, Uri16 B. Compared with the original issue43 graph,
the static delta decreases from1404 B to1260 B. No static memory is freed by
switching modes. Known normal dynamic payload after registration is724 B:
120 B header records,300 B handlers,80 B URI objects,96 B header-name buffers,
128 B route-string buffers. Additional retained request/auth Strings and active
clients vary; allocator overhead/fragmentation is not included in this payload.

Maintenance still requires the actual4096 B Core staging buffer. No ordinary
HTTP owner, JSON pool, RSA verifier or6200 B secondary stack coexists. The32 B
key is already included in static RAM, so it is not subtracted twice. Floors
remain heap20480, largest16384, continuation stack2048, fragmentation<=25%.

Using the earlier owner30224 B heap observation and an **illustrative, unproven**
4096 B TCP allowance: `30224 -1260 -4096 -4096 =20772 B`, only292 B above the
heap floor before crediting HTTP release; adding724 B gives21496 B, **1016 B
margin**. These are scenarios, not simultaneous native measurements. SDK/AP,
tcp_pcb/ClientContext/pbuf/queued packets, allocator metadata and fragmentation,
consent-supplier and transient costs have no qualified upper bound. Known HTTP
release therefore does not establish safe headroom.

Compiler partial auth frames1376 B and staged-verification frames1120 B include
the80 B StageA loop frame. Commit helpers reduce the previous coarse path, but
libc/crypto/network/flash/interrupt callees and actual continuation watermark
remain unknown. Owner3248 B stack minimum is not a simultaneous update sample.

## Qualification and stop

Host real StageA/parser/Core destructor:156 lifecycle assertions across12
maintenance/abort/reconnect cycles, active+queued socket cleanup, fresh Digest,
TTL stale and one-shot recovery, pending/active cancel, listener-begin failure
and terminal low-memory HOLD. The same integrated normal handlers also pass
202 stock/cached urllib posts, stale/recovery and final GETs. Radio/SDK and the
upload pump are mocked in this lifecycle lab; host Strings use std::string.

Actual Native pump + receiver + pinned Core + real Python sender:230 RAM-only
cases including197 interruption boundaries, wrong identity/password/HMAC,
pre-begin U_FS rejection, wrong/corrupt images, timeout/disconnect, abort after
full staging, AP loss, overlong control line and15s idle-listener timeout.
Only valid/time-wrap cases schedule one mocked eboot command/reboot; negatives
schedule none and release owner/listener/queue/buffer. FS/tail RAM is preserved.
Two negative builds reject global signing/OEM coexistence. The original225
engine cases and7 installer tests still pass. Installer live gate stays false.
Host RAM/RTC/reboot seams are **not physical flash/recovery proof**.

Exact final SHA/CI receipt is on PR42 after checks; CI does not close the case.
The required real SHINO-to-SHINO Wi-Fi update plus normal/LittleFS verification
has not occurred. **Do not remove the clips or close the enclosure on this
evidence.** No physical authorization request or further sequence is proposed
because this bounded attempt remains NO_GO.

Device contact, serial I/O, physical flash/RTC/filesystem writes and reboot:
all0. Private-file reads0; no merge, device receiver activation or frozen image
replacement. The historical unattributed404 remains unresolved.
