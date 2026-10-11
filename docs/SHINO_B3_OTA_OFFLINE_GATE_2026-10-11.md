# B3 / Mission 9 — OTA offline safety gate, 11 October 2026

**`OTA_OFFLINE_GATE=HOLD`; simulation assertions PASS. Physical OTA NOT RUN.**
The owner authorized offline qualification on existing Draft [PR #47](https://github.com/shinobione/SHINO-TV/pull/47),
starting at verified `f2a831d15d01efa33277a7fd08428498c0e6c912`. The
[owner's B3 read-only PASS](SHINO_B3_PHYSICAL_PASS_OTA_READINESS_2026-10-11.md)
remains unchanged. Installed B3, production firmware/companion sources, private
images, flash backups, physical receipts and attempt markers were not edited.
No SmallTV contact, private B4 compilation, OTA, serial, flash, reboot, LINK
production change, PC Wi-Fi change or PR merge was performed.

## Exact source and model

The existing HTTP lab, eboot extraction and test runner were extended. No new
receiver or recovery implementation was introduced. ESP8266 Arduino **3.1.2**
(PlatformIO package `3.30102.0`) source SHA-256 pins remain unchanged in
`tools/m9_signed_core_sources.json`, including Updater, eboot, RTC command and
`eagle.flash.4m2m.ld`. The installed B3 firmware source at `26e1ace` is unchanged.

The disposable host copies replace only allocation/free, flash/RTC stores and
resource observations; actual Updater buffer selection, receiver predicates,
SHA/HMAC/CRC, segment validation, RTC CRC and eboot copy control flow execute.
Native MSVC code uses RAM instead of hardware. The extracted loader captures
an application entry; it does **not** execute Xtensa or boot a SmallTV. Python
socket/DNS/HTTP constructors are blocked and asserted unused. Local native
executables contain file/stdin/RAM seams only.

The modeled heap/block cost is requested buffer size plus an explicit **16 B
synthetic allocator overhead**, not a measurement of ESP8266 umm_malloc. Phase
pressure is injected; it establishes rejection/detection semantics, not the
likelihood or size of a real OTA peak. Continuation stack minima are historical
and cannot recover when a frame returns. Bootloader stack is a separate context;
eboot's 4096 B automatic copy buffer is not a continuation-stack measurement.

## What passed locally on Windows

| Validation | Result and scope |
| --- | --- |
| Windows companion + focused tools | **224 tests, 0 failures/errors/skips**; actual OS Digest lock plus fake HTTP; two sandbox restrictions (hardlink and objdump DLL launch) resolved by rerunning the affected suites outside confinement, unchanged tests |
| New inert 100,000 B safety matrix | **609 cases**; 200 staging, 64 RTC-word + 4 clear cuts, 278 eboot and 5 begin/end interruption/failure boundaries |
| New compiled public 407,488 B matrix | **2,034 cases**; 800 staging, 64 RTC-word + 4 clear cuts, 1,103 eboot and 5 begin/end boundaries; all 100 sectors |
| Memory pressure | 32 cases across HMAC, stage setup, allocation, receiving, SHA/CRC, both segment scans and commit; 22 rejected, 10 expected risk detections, never promoted to OTA safety |
| One-shot Windows/Core integration | 7 synthetic cases: response lost before body/after RTC/during copy, validation failure, ACK without boot, lost reply with simulated new boot, new boot with stale metrics; exactly one POST, repeat refused before I/O, marker unchanged |
| Retained HTTP/Core matrix | 227 cases / 197 interruption boundaries; real Windows HMAC |
| Exact compiled image replay | 137 negative cases / 122 interruption boundaries; old unaligned footer reader still rejected |
| Core flash-read contract | 20,034 assertions, 320 valid byte reads; alignment, tails and staging bounds |
| Retained eboot/Wi-Fi labs | 74 eboot cases / 72 cuts; 225 Wi-Fi receiver cases / 197 cuts, RAM only |
| Source freezes | StageA and predecessor signed source gates PASS; 113 historical firmware pins plus exact production client pins retained |

Each new matrix case compares every byte in LittleFS and the reserved tail.
The public LittleFS fixture has the reviewed **24 files / 181,402 content bytes**,
8 KiB blocks, 256 B pages and disk version `0x00020000`. Its inventory is parsed
before and after a complete modeled OTA with the existing pinned read-only
`littlefs-python==0.15.0` inspector: zero parser writes, autoformat disabled.
These are public fixture bytes, never the owner's flash or credentials.

Metadata-only custody check: 63,134 existing ignored/private files, none missing;
63,133 retain size/mtime. One existing LINK QA diagnostic changed concurrently
outside this test's output path; no test writes that path. Its contents were not
read or restored. Historical receipts/backups/attempt markers were preserved.

The public build has **43,572 B static RAM, 56 B noinit, 407,488 B BIN**.
Known compiled paths: HMAC 1,616 B; staged SHA/CRC 1,072 B; segment read 784 B;
Core end verification 720 B; RTC commit 672 B. `.su`, linked prologues and SHA
vtable targets are cross-checked. ROM/SPI/lwIP/allocator/IRQ/response/restart
costs remain unresolved; these numbers do not establish a whole native bound.
The public build was made from unchanged firmware with only offline tools/docs
dirty; final exact-head CI independently rebuilds the public graph.

## Geometry and source-proven risks

The linked public ELF and exact Core linker script agree:

| Region/symbol | Value (end exclusive) |
| --- | --- |
| `_FS_start`, physical LittleFS start | `0x40400000`, `0x200000` |
| `_FS_end`, physical LittleFS end | `0x405fa000`, `0x3fa000` |
| `_EEPROM_start` | `0x405fb000` |
| Reserved end of flash | `[0x3fa000, 0x400000)` — 24,576 B |
| Public 407,488 B target staging | `[0x19c000, 0x200000)` — 100 rounded sectors |
| Maximum target `0xfeff0` | Rounded `0xff000`, staging start `0x101000`; max-to-max gap `0x2000` |

Core and SHINO staging addresses are compared, including 64,000, 65,536,
65,537, 407,552 and maximum sizes. A deliberately wrong linked FS boundary
produces different addresses: the external offline geometry gate rejects it;
Transfer alone does not independently assert that equality. The actual installed
owner ELF was not read during this task, so its linked symbols are not a new
agent-verified physical fact.

**Proven by pinned source and exercised in RAM:**

- Core chooses **4096 B at heap >8192**, otherwise **256 B**. The natural 256 B
  branch and allocation failure are exercised. SHINO refuses the low-memory
  admission; the test never forces that branch into a false SHINO PASS.
- Thresholds remain admission heap **25,600 B**, running heap **20,480 B**,
  block **16,384 B**, stack **2,048 B**, fragmentation **25%**. With the model's
  overhead, 29,560 B becomes 25,448 B during allocation; admission exactly
  25,600 B leaves 21,488 B. Neither calculation predicts a real native minimum.
- Allocation/receiving/verifier sampled breaches abort without RTC commit;
  historical stack breaches during HMAC/setup also remain visible and abort.
  Transient heap/block/fragmentation breaches inside HMAC/setup can disappear
  before the callback. Commit has a pre-check, without an inner resource check.
  Injected peaks in those windows can reach STAGED: these are recorded risks,
  not assertions that installed B3 actually experiences those peaks.
- Core rewrites the first-sector flash-mode byte when it differs from hardware,
  then restores its RAM buffer. A DIO image against QIO/QOUT/DOUT hardware is
  rejected by staged SHA/CRC before commit. No bytes/digest checks are weakened.
- `end(false)` arms a 32-word RTC COPY_RAW command. Cuts before/after each word
  retain the real CRC check. After the final word the command can be valid even
  with no returned success response. A dropped RTC store can go undetected by
  Core's void write interface: an ACK cannot prove a future boot.
  Cuts at both command-clear stores also remain UNKNOWN; before clearing magic,
  a valid RTC command can remain after a completed copy. A later warm reset
  might replay it. The test driver stops at each cut, never simulates an
  automatic retry or invents RTC retention across cold power loss.
- eboot skips sector zero only when all 4096 bytes match; a different sector zero
  is erased/written. Both branches and the destination-read failure are tested.
  Each sector source read, erase and write is interrupted before/after, with
  explicit failures and arbitrary torn erase/write patterns. Destructive copies
  do **not** restore the previous application. Unknown snapshots stay unknown.
- Post-copy verification in eboot main is disabled. A postcommit bit flip is
  copied with `copy_raw` return 0; the independent **host** destination SHA fails.
  That host SHA is an oracle, not a protection supplied by the physical eboot.
- Actual client marker reservation precedes the POST. Lost/invalid responses
  produce `UNKNOWN_NO_RETRY` or `POSTBOOT_ACCEPTANCE_UNCONFIRMED`; a simulated
  fresh boot can resolve a lost reply, and `metrics_fresh=false` never passes
  postboot acceptance. There is no automatic second upload.

## Verdict and missing physical measurements

`OTA_OFFLINE_GATE=HOLD` because native OTA high-water/heap/block/fragmentation
remain unmeasured, transient observation windows remain, and the destructive
eboot path has no atomic swap or rollback. Source/model guarantees are qualified
above; no root cause of a historical physical failure is inferred.

The owner-observed B3 stack minimum **2,272 B** leaves only **224 B** above the
unchanged floor, during a different read-only workload. Still missing: actual
installed-image allocation and HMAC/receive/SHA/CRC/end watermarks under OTA,
radio/SDK/IRQ behaviour, response/restart path, separately verified exact
successor header/ELF/staging geometry and physical post-copy/LittleFS integrity.
No B4 image was created. Any successor creation or physical test needs its own
owner mandate and exact identities/recovery decision; offline PASS assertions
do not provide that authorization.

## Reproduce the inert gate only

Run from the repository on Windows with MSVC, exact Core cache and pinned
`littlefs-python==0.15.0`. This creates only a new local report and temporary
inert fixtures, then prints HOLD with simulation PASS. It has no device command.

```powershell
$gateDir = Join-Path $PWD ('research-local/ota-offline-' + [guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path (Join-Path $gateDir 'tmp') | Out-Null
$env:TEMP = Join-Path $gateDir 'tmp'; $env:TMP = $env:TEMP
python tools/test_shino_http_ota.py --safety | Set-Content -Encoding utf8 (Join-Path $gateDir 'safety.json')
if ($LASTEXITCODE -ne 0) { throw 'Offline assertions failed' }
```

Ignored local evidence: `research-local/b3-ota-offline-gate-20261011/`.
Exact delivery SHA/CI status are attached to existing PR #47 and the final
delivery message, avoiding a self-referential commit or a stale CI claim here.
