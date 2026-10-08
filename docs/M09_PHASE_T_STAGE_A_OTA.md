# Mission 9 Phase T — StageA single-owner signed OTA qualification

**Offline integration implemented; production NO-GO.** Starting commit
`b59964af43b555b75d415e6d063580945e6d99f7`, existing
`feature/shino-tv-m9-flash-layout-liberation`, Draft/open/unmerged PR42.
[Owner instruction](https://github.com/shinobione/SHINO-TV/pull/42#issuecomment-6067111422).
Interrupted work was recovered in place; no reset, clean, replacement branch,
new phase, installed-image build/refreeze or physical-writer rebind.
Final commit and exact-head run/job results are recorded in PR42's receipt.

| Gate | Verdict |
| --- | --- |
| PHASE_T_SINGLE_OWNER_HTTP | PASS_OFFLINE |
| PHASE_T_NATIVE_LINK | PASS_OFFLINE |
| PHASE_T_MEMORY | HOLD_PHYSICAL |
| RESOURCE_GATE | HOLD_PHYSICAL_MEASUREMENT_REQUIRED |
| SIGNED_OTA_PRODUCTION | HOLD |
| SIGNED_OTA_PHYSICAL | NOT_RUN |
| Safe physical integration | BLOCKED — pinned Core has no safe abort |

Device contact, serial I/O, device flash writes, RTC writes, reboots and device
FS writes: **all0**. These counters exclude simulated RAM SPI/RTC operations.
No physical command is supplied or authorized by this receipt.

## Existing physical evidence remains owner evidence

Installed StageA remains the frozen399264 B image, SHA-256
`78a8d2d50409974fc775dd3dc9f3dbec4ac8eda839f6d9b338cadf35aab2467c`.
4m2m LittleFS remains0x200000..0x3F9FFF,24 files/181402 B, preservation accepted.
Owner reports >=180 s telemetry/stale/recovery, later status HTTP200 and resource
floors PASS: setup stack2288, FS/config2368, runtime3248, heap30224,
largest block30008, fragmentation1%,445 samples/0 rejects. These minima are
not simultaneous OTA measurements. NORMAL_PROFILE_LITTLEFS_MOUNT_GATE=PASS;
NORMAL_PROFILE_RUNTIME_GATE=HOLD/PARTIAL; intermittent404 root cause UNRESOLVED.

## One HTTP owner, bounded handoff

The unchanged actual `M9NormalStageA.cpp` owns one `Webserver service` and one
`service.begin()` on port80. Its status/resources GET, telemetry POST/GET,
dashboard, TTL and real pinned Core Digest handlers execute in the host test.
Radio/interface, FS/config, display and SDK observations are explicit inert seams.
The listener binds only127.0.0.1 on a host-selected port; there is no SmallTV host.

Pinned Core3.1.2 supports `CLIENT_IS_GIVEN`: retain a refcounted WiFiClient copy,
return that value, and Core drops its reference without stopping the connection.
The isolated T overlay adds one callback **immediately after StageA's bounded
raw request-line reader**, before ordinary headers/body. It passes the exact line
and original request-start timestamp. Existing normal materialization is untouched.
Exact OTA method/target/version is checked from real bytes, not reconstructed
from parsed URI/version. Other requests continue through the actual normal parser.
There is no second listener, generic POST upload registration or large body String.

`Http::pump()` reads at most512 B per invocation. Headers are bounded2048 B,
with the reused S strict header contract (24 fields, duplicate/framing rejection).
Its two-second header and60-second total deadlines include request-line reading,
use unsigned subtraction and survive time wrap. Normal handlers continue on the
same server between steps. An existing slow normal request can occupy Core's
bounded two-second reader; this is tested as host starvation, not RF timing.

Before staging begins: exact route/method/version/Host/Origin, private AP interface
and actual peer, bounds/length, independently selected immutable release pins,
4m2m geometry, fresh privileged consent/intent and independent strict SHA256
Digest with actual target/qop=auth/one-use nonce all admit the request. Arm Digest
is checked before the16 B consent body and again by unchanged S `Transfer::arm`
using a second verifier view of the same fresh challenge. Upload uses its own
nonce. Public fixed challenges, interface mappings and credentials are **host
fixtures only**, not entropy, owner permission or provisioned production trust.
StageA read Digest and cookies never confer write authority.

The 2048 B header buffer and512 B chunk share a union after authorization;
this saves512 B without moving them onto continuation stack. Exact-offset chunks,
selected raw/package hashes, trailer and staged rehash remain S contracts.
Failure closes the borrowed client, poisons the transaction and forbids reuse.
No retry, automatic reboot, unsigned fallback or end(true) exists.

## Actual StageA native link and resource pair

`m9_stagea_build.py` copies only tracked public firmware into two disposable
research directories. It never copies owner policy, private files, frozen images
or backups. Both use the same inert policy/version, actual complete StageA source,
4m2m/DIO, PlatformIO6.1.18/platform4.2.1/Core3.30102.0/GCC10.3.0,
ArduinoJson7.4.3/GFX1.6.4/AnimatedGIF2.2.0. Dependency source-tree hashes match.

Opt-in OFF retains original StageA source and parser byte identities. All113
firmware pins, companion and physical-writer sources equal starting HEAD and the
previous S source gate. Default/profile0/profile2/normal options are unchanged.
The integrated copy appends an internal proof to the actual StageA translation
unit. It reserves the real native objects, connects the real parser hook/API and
links native DER decoding, SHA256/RSA2048, dedicated Updater, staged rehash and
end(false). StageA loop only reads volatile function addresses/type-cost words;
it **never invokes the proof or pump, installs the hook, supplies DER or reaches
a writer**. Internal proof symbols have local linkage; no embedded trust key.
NativePolicy observes real AP/client/heap/stack APIs, not fixture observations.
Global signing/unsigned OEM mutual exclusion and existing StageA static_asserts
remain effective. This graph is compile/link evidence, not a release image.

Local paired measurements (static RAM includes `.noinit`):

| Quantity | Public StageA baseline | Integrated public graph | Delta |
| --- | ---: | ---: | ---: |
| BIN | 399248 B | 446480 B | +47232 B |
| Linked flash sections | 395091 B | 442331 B | +47240 B |
| Static RAM | 39784 B | 43988 B | +4204 B |
| `.noinit` | 56 B | 56 B | 0 B |
| `.data` | 1616 B | 1628 B | +12 B |
| `.rodata` | 10776 B | 11688 B | +912 B |
| `.bss` | 27336 B | 30616 B | +3280 B |

Actual reserved native adapter400 B, HTTP/transfer workspace2832 B, policy16 B.
These are integrated ELF measurements; S standalone+920/+50160 is not added.
Both public BINs pass genuine Core image/segment/CRC checks. Their identities
and all composition hashes are in the CI JSON, not identities of installed bytes.

Significant compiler frames: native proof96 B, pump192, HeaderGate448,
strict Digest672, hash192, arm176, staged rehash464, Core end192,
normal metrics880, parser224 and handleClient64. A partial native arm call chain
is192+176+672+192=1232 B; deeper SDK/interrupt/allocator/crypto paths are unknown.
Sequential GET and OTA call frames are not falsely summed as one call stack.

Proven dynamic payloads: BearSSL secondary stack6200 B, Updater buffer4096,
signature256, SigningVerifier8, persistent RSA key structure/modulus/exponent279:
**10839 B**. DER decoder2092 B is transient before staging, measured from real
Xtensa type sizes. WString uses16 B rounding; a conservative simultaneous normal
parser/body/auth/response model reserves10504 B (including retained prior POST).
Known native plus this parser model totals21343 B, **excluding** allocator metadata,
fragmentation, JSON pool, lwIP/SDK/client contexts and callback allocations.
The host RAM hash/sink containers do not establish native heap usage.

Admission remains heap31544/block22584/stack4096/frag<=25. Physical floors stay
20480/16384/2048/25. Owner observations directly miss admission by1320 heap and
848 continuation. Static-delta projection gives26020 heap before OTA and15181
after known native payloads, below the20480 floor; with the conservative parser
model it gives4677. These projections are scenarios, not integrated high-water
measurements, and do not double as a physical pass. The reserve is rechecked on
every chunk: maintaining31544 after known initial native allocations already
requires at least41848 before begin, excluding further costs. Core continuation
is4096 total; observing4096 free inside a nonzero-frame callback is not established.
No lower admission or allocation bypass is introduced. **Memory is HOLD, no-go
for activation.** Offline data cannot establish safe simultaneous high-water.

## Qualification and recovery limits

Final T wire suite:38 cases,915 normal GETs and185 accepted LINK POSTs, no
unexpected404. Each good/time-wrap transaction includes400 GETs/53 LINK POSTs,
one100260 B RAM transfer, bounded chunks, stale/recovery and replay rejection.
Negatives cover route/version/method, Host/Origin, peer/interface/consent/budget,
Basic/cookie-only/Digest target and nonce reuse, duplicate/large headers, TE/Expect,
length/token, missing body, timeout/wrap, disconnect, duplicate active upload,
allocator/write failure, changed raw/trailer and corrupt staging. All negatives
have0 commits; pre-admission negatives have0 begins/writes. Watchdog feeds and
pump progress are counted; stream steps never exceed512. Declared normal-response
bound3000 ms; measured worst about2050 ms for the deliberate slow request.
This is host scheduling evidence, not ESP RF/flash/RSA/watchdog timing.

Retained S native lab:250 transactions/2118289 assertions,197 interrupted staging
boundaries,32 partial RTC command writes,0 failed precommit boot dispatches.
Real RSA/key, CRC/checksum/image/trailer/release/geometry, allocator/read/erase/write
failures and signing-versus-MD5 interlock remain covered.11 signed-release tests,
9 explicitly selected public StageA tests,13 Phase R tests and19 companion tests
pass locally; retained S mixed model392 GET/49 LINK passes. Previous Q/R/S and
default/profile0/profile2/normal public builds are also required at final CI head.

T additionally executes the **unchanged pinned `copy_raw` and read-byte function**
with RAM SPI seams:74 cases/2240 assertions,72 cuts after erase/partial write/full
write across application sectors. LittleFS/tail/staging stay unchanged in the RAM
model. GZIP is not admitted; GZIP stubs throw if reached. MSVC only strips the
alignment attribute; the copied function body hash is retained. Postcommit
corruption is copied successfully, proving no reauthentication in that path.
This does not simulate ROM, actual power loss or physical flash behavior.

Pinned Updater has no safe public abort. A poisoned fully staged instance must
not call end(false) to release memory: that can schedule the copy. It remains
nonreusable and can retain staging memory until a separately reviewed lifecycle
change. Eboot copy is not transactional rollback; partial copy or postcommit
corruption can brick the application. No OEM downgrade or recovery guarantee.

**Root production blocker:** the native transaction's resource/failure lifecycle
is not safe to activate in StageA; in particular Core cannot abort without risking
commit. **Next engineering decision:** keep native OTA disabled unless a reviewed
non-committing lifecycle and bounded resource contract can be established offline.
This receipt authorizes neither a follow-on phase nor physical measurement.

## Privacy deviation and final CI boundary

One inherited local Phase N freeze regression conditionally read the existing
frozen predecessor BIN. That violated the owner's public-input-only restriction;
it was disclosed immediately, not modified/rebuilt/uploaded, and excluded from
subsequent local selections. No credentials, signing key, installed StageA BIN
or backup was read. T execution/builds and CI use public inert inputs. This
deviation is not hidden by the all0 device-operation counters.

Dedicated `.github/workflows/m9-stagea-ota.yml` checks exact-head public source
closure,38 wire cases, real eboot RAM cuts, paired native graphs, unchanged floors
and HOLD verdicts. It uploads JSON only, no build image or private artifact.
Prior CI suites remain independent. Final head/run/job counts belong in PR42's
receipt after every applicable check passes. **STOP: no device operation or merge.**
