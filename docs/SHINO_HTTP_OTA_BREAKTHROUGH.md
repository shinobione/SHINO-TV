# SHINO // TV — OTA Breakthrough, 10 October 2026

The existing persistent HTTP/HMAC/Core3.1.2 receiver now validates complete
compiled images under the real typed flash-read contract and reaches the native
Updater RTC commit in a RAM model. This is an offline software result. The owner
reports the historical A→B attempt ended FAILED_NO_COMMIT with A still running;
it remains terminal. No new physical operation has been performed or authorized.

## Demonstrated defects and correction

Core3.1.2 `EspClass::flashRead(uint32_t,uint32_t*,size_t)` rejects a destination
or size not divisible by four; the SDK seam also requires a word-aligned flash
address. The former direct reader passed the segment checksum footer's one-byte
read unchanged. The same complete valid compiled image fails with that reader
and passes with the corrected reader. This demonstrates a deterministic software
defect compatible with the owner-observed failure, without inventing a device
error trace. Sources: pinned local `Esp.cpp` and
[Core3.1.2 Esp.cpp](https://github.com/esp8266/Arduino/blob/3.1.2/cores/esp8266/Esp.cpp).

`ota/firmware/ShinoHttpOta.h` retains the previously corrected word reader and
adds explicit physical staging containment. Head/tail reads use one aligned
word; an aligned bulk destination goes directly to Core, while an unaligned
destination copies aligned words. No read crosses the sector-rounded staging
extent or reaches LittleFS. Null input is rejected and a Transfer cannot be
copied. Streaming SHA, staging SHA/CRC/release tag and both eboot segment tables
must all pass before the single `end(false)` call. Every earlier failure uses
the isolated noncommitting `shinoAbort()`; the global signer/MD5 interlock stays
unchanged.

The verification buffer and SHA context now belong to the single Transfer and
are reused. SHA/CRC verification returns before either segment verifier starts.
The former staging416/segments352 frames become176/224; reader64, finish144 and
Core end192 remain bounded. `Normal.cpp` holds an upload lease across the entire
synchronous transaction and checks the peer and absence of excess bytes during
reverification, closing a disconnect-before-commit gap. A fault injected on the
first staging re-read produces FAILED_NO_COMMIT and the same server remains
routable. Nested use returns UPDATE_BUSY before touching transfer storage.

No alternate protocol, server, cloud service, authentication layer, UI change,
telemetry cadence change or resource-floor reduction is introduced.

## Offline evidence and limits

- Flash matrix: 320 valid reads across offsets0..3, lengths1/2/3/4/5/15/16/127/128/129,
  destination alignments0..3 and image/FS tails; 20034 assertions. The reference
  typed reader is extracted from pinned Core source. Overflow, forbidden range,
  fault and legacy footer rejection are covered.
- Historical security matrix retained: 227 receiver/Core cases and197 interruption
  boundaries. All failures keep RTC uncommitted and the current application,
  LittleFS and final24KiB intact.
- Exact compiled public BIN: full streaming/staging/readback, SHA/CRC/tag and both
  segment tables, real Core `end(false)`, then pinned eboot `copy_raw` and loader
  prefix. Negative cases cover authenticated corrupt CRC/metadata/checksum/entry,
  stream/staging corruption, read/erase/write faults, full abort and resource
  loss before/during verification; every sector flush and segment tail is cut.
  The former reader rejects these same valid complete bytes.
- Actual `Normal.cpp`, WebServer parser/Digest and Updater on127.0.0.1:150
  authenticated telemetry/status requests, TTL stale/recovery, shared-response
  and upload ownership refusals, partial disconnect, bad hash, forbidden transfer
  encoding and disconnect during readback; one valid complete BIN commits once.
- Windows consent/LINK/sender tests:76 cases; private UART binding4, packet
  control10 and CI-OPT scope13. Their serial transports are inert.
- Final public compile:407648-byte BIN, static RAM43496 including56 noinit,
  linked403495. Matched baseline:407536/43336/403391; delta+112/+160/+104.
  ELF linker symbols are checked for4m2m. Core buffer4096 and all original floors
  remain: heap20480, block16384, historical free continuation2048, frag≤25;
  admission heap25600.

`tools/shino_http_ota_stack.py` cross-checks `.su` against linked Xtensa prologues,
resolves SHA256 vtable targets from the ELF and verifies the two segment calls
and actual Core commit edge. Reported compiled paths include HMAC, staging SHA,
segment flash reads, last-chunk flush, verification and RTC commit. The largest
known compiled path is1840 bytes within the unchanged2048 reserve. It is **not a
whole native upper bound**: ROM MD5/SPI, SDK/lwIP/allocator, callbacks/interrupts
and response/restart remain explicitly unbounded. RAM budgets are MOCKED. The
captured eboot jump does not execute Xtensa code or prove physical timing,
power-loss recovery, native memory floors or LCD rendering. `copy_raw` has no
automatic rollback or postcommit cryptographic revalidation.

Public evidence is under `research-local/ota-breakthrough-20261010/`; only inert
public evidence is uploaded by CI. BINs, private build/device IDs, credentials,
full dumps and private replay receipts remain ignored and exclusively local.

## New private pair and operator route

Prepared A2/B2 from clean implementation commit
`6bb6e7479faee0a5169e2bc74f96d08f890cfb51` into the fresh directory
`research-local/m9-owner/http-ota-breakthrough-20261010-a2-b2/`. Both images use
the same receiver/source/layout and owner credentials, with distinct build IDs
and hashes. Each BIN is407728 bytes; static RAM43548 includes56 noinit, linked
flash403571; the same frame caps and compiled1840-byte maximum pass for both.
The private manifests and `README-OPERATEUR.md` contain the exact paths/bytes/
hashes/build IDs; they are not uploaded. Historical packets and all4MiB backups
are retained:229 pre-inventoried artifacts rehashed unchanged.

Each exact private BIN passes135 negative cases/122 cuts, plus positive Core
commit and pinned eboot copy/load, using the other exact BIN as the current RAM
application. Thus B2 can also receive a distinct valid image in the model.
The actual HTTP A2→B2 model sends407728 bytes and commits/restarts once, with
150 authenticated POST/GET requests and all disconnect/reentrancy regressions.
The exact A2 UART inert transaction has one Begin,100 unique DATA, one Finish,
one MD5 and no retry; a second invocation is refused. Independent model PRE/POST
checks3784704 protected bytes unchanged. Generated UART AUDIT and Windows offline
inspection pass without opening a port or creating a physical attempt marker.
Actual PRE/POST output names remain unused; model files are explicitly labelled.

Local `qualification-summary.json`, `evidence/`, `network-exact-A2-B2.json`,
`uart-audit.json` and `offline-packet-audit.json` retain the detailed private
results. The software packet is **READY_FOR_OWNER_AUTHORIZATION**. All new
device/COM8/readback/flash/OTA/reboot operations are NOT_RUN; native simultaneous
memory and physical A2→B2 acceptance remain HOLD pending exact-operation approval.

The bound UART wrapper checks its command-book/helper/candidate hashes and the
fresh PRE's installed-A/private FS/SDK fingerprint before write. Each PRE/write/
POST has a durable one-attempt latch; existing outputs cannot be overwritten.
Unknown results block the entire sequence. The old failed staging bytes may
differ; they are not a reason to rewrite an archived backup. Independent POST
verification checks the new application/padding and every byte above its write
extent. The Windows updater is bound to exact B2 and requires exact running A2;
it reserves its durable attempt marker before the single POST. It never resends.

After separate exact-operation owner approvals:

1. Manual ROM mode → fresh PRE4MiB → single UART A2 write → fresh POST4MiB →
   independent local verification. No recovery write or automatic reset.
   Re-establish ROM manually after PRE: its read-flash stub remains active and
   the qualified writer requires a fresh ROM session, not an existing stub.
2. Authorized normal boot → LINK/four cards → bounded read-only A2 qualification
   with exact SHA/build, stable boot, filesystem hashes and resource floors.
3. One authorized Wi-Fi B2 POST → distinct boot ID/executed SHA/build, LittleFS,
   fresh metrics and future OTA admission → bounded B2 qualification.

Stop on missing acknowledgement, unknown result, reset, corruption, any memory
floor/identity/filesystem failure or unavailable recovery. Physical acceptance
and enclosure closure stay HOLD until the owner performs and accepts this route.
The existing branch/Draft PR42 remains unmerged; exact-head CI is required.
