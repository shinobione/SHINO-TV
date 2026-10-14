# B5.2 clock foundation — offline development, 14 October 2026

**Subsequent freshness/P2 closure: READY_FOR_OWNER_REVIEW, software only.**
[Final correction and evidence](B52_CLOCK_FRESHNESS_FIX.md) supersede the pre-fix
replay blocker below. The earlier implementation/review record remains intact;
physical qualification is still HOLD.

**Latest final offline review: HOLD.** Old/replayed clock samples are accepted
and renew the lease; four targeted HOST reproductions confirm the blocker.
ASan17 cases/1722 checks PASS. Earlier implementation results below are retained;
the [final review](B52_FINAL_OFFLINE_REVIEW_2026-10-14.md) controls readiness.

## Authority and frozen base

Owner authorizes a first native IDLE clock integration, public inert compilation,
targeted HOST tests and 240x240 software captures. Work starts from
`244334edac07701dc25b5ffc494715152ae1bfa5` in a separate local worktree/branch.
No push before review; no device contact, private build, installation, secret
read, Wi-Fi change, reboot or merge. The B5.1 checkpoint and owner artifacts
remain unchanged. B5.1 physical first boot/LAN PASS is owner-reported, not B5.2
evidence.

## Design decision

Use the paired Windows PC's real system UTC clock and OS local UTC offset,
authenticated with the existing Digest realm, listener and LAN admission. Add
only a versioned bounded clock-sync route; do not add fields to the existing
metrics payload or change its cadence, TTL, authentication or response.
The provider is explicitly opt-in and disabled by default. HOST fixtures cannot
enable a real transport. No active SHINO LINK process is inspected or changed.

Core 3.1.2 SNTP was examined: `time.cpp` uses a scheduled `settimeofday_cb`,
`configTime()` starts lwIP SNTP, and the pinned default `SNTP_CHECK_RESPONSE` is
0. It would add asynchronous DNS/UDP, scheduler allocations and unauthenticated
system-time changes to a graph whose whole-native OTA memory is unmeasured.
The PC route instead reuses the existing scratch/lease and has fixed state.
It adds one explicitly separate authenticated protocol, rather than weakening
or overloading telemetry. No old NTPClient, Webserver, SceneManager,
FirstBootBridge, MediaReceiver or Mission 8 ingress is activated.

Clock authority is the paired PC's configured clock/timezone. Digest authenticates
that source; it does not prove Windows time-service accuracy. Offset and UTC
are sampled together. The publisher shortens the lease before an OS timezone
offset transition. No device timezone setting, credentials or filesystem write
is needed. Transport latency and oscillator drift are not physically measured;
this clock is for display, never authentication or OTA deadlines.

## Bounded clock contract

- Authenticated `POST /api/v1/clock/sync`, binary, exactly 16 bytes, the same total
  2-second parser/body deadline and existing LAN/Digest/config gates.
- Exact frame: eight ASCII bytes `SHINOCLK` (protocol v1), little-endian
  uint32 `utc_s` (2020 through 2099), signed int16 `offset_min` (-720 through
  +840), uint16 `lease_s` (1 through 120). Reject wrong size/marker, extra bytes,
  invalid epoch/offset/lease and malformed framing. No inbound JSON allocation.
  The PC encoder also rejects unknown fields, booleans, floats and overflow.
  Before an OS offset transition, subtract eight seconds of conservative
  transit slack from the lease; do not publish in that final transition window.
- Read-only authenticated `GET /api/v1/clock/status`; source, validity, age,
  offset and remaining lease. No addition to existing status serializers.
- Lease starts at admitted request start; reading/rendering never renews it.
  Expiration latches until a new valid authenticated sample. No uptime-derived
  wall clock and no clock retained across boot.
- PC producer uses actual UTC and OS offset; it does not invent unavailable
  time. Publish is a separate explicitly authorized library operation, uses
  the existing Digest coordinator, never retries an uncertain POST.
- Four metric cards retain existing values, GPU availability, RAM denominator,
  dynamic percentage bands/hysteresis and neutral GPU temperature bar. Metrics
  expire after 6000 ms independently of the clock's maximum 120-second lease.
- Renderer owns no heap or full framebuffer. One cooperative task after the
  serialized HTTP owner; fixed 448-byte scanline belongs only to the renderer.
  Source/offset and sync age are visible; invalid/expired time is explicit.
- Public compile keeps clock write authority false, OTA authority false and
  the existing 4m2m/LittleFS/RTC footprint and safety floors unchanged.

## Evidence and limits

Implementation, tests, resource tables and independently rendered 240x240
captures are recorded below. Synthetic HOST clock/metric
fixtures are labelled, and are not physical LCD, synchronization or Freebox
evidence. Existing B5.1 public ELF is reused as the resource baseline; no old
firmware is rebuilt. New B5.2 remains PHYSICAL HOLD.

## Later music/cover connection

Retain `SceneEngine.h`'s `View` ownership seam and exclusive scene policy. A later
bounded mission must adapt authenticated Begin/Commit/Abort metadata and image
ownership to B5's one-owner parser/dispatch. Only commit exposes complete RGB565
RAM artwork; invalid input preserves the prior committed view, abort/expiry
releases ownership. Keep metrics ingestion running while music hides cards.
Do not copy the old Mission 8 HTTP/FirstBootBridge graph or enable its receiver
merely to draw the clock. Requalify its heap/stack, 8-second deadline and image
ownership on the B5.2 graph before any private candidate or owner installation.

## Result — READY_FOR_OWNER_REVIEW / PHYSICAL HOLD

Frozen branch/workspace remain clean at
`244334edac07701dc25b5ffc494715152ae1bfa5`. PR47 is Draft/open/unmerged;
18 exact-base CI checks succeeded, 23 were skipped. B5.2 is an uncommitted local
diff in `codex/b52-clock-foundation`; no push or new-branch CI was run.
The installed B5.1 and its private artifacts were neither rebuilt nor changed.

The retained public B5.1 generated Normal source matches the frozen generator;
its LAN controller, FslessMetrics and HTTP updater match the new graph. Public
BIN manifests and ELF layout were rechecked. New public BIN: **420224 B**,
SHA-256 `80fd47a874b5671536936739359e0c4c5ac01249ed491161a6a39b930b08f0d4`.
Public fixture identity, clock/OTA write authority false; this is not an owner
installation candidate. The tool has no private mode.

| Evidence | Actually executed, PASS |
| --- | --- |
| Clock/calendar/render | 16 C++ HOST cases / 1717 checks; 240x240 bounds |
| PC provider | 18 Python tests, including headers/body trickles, socket closure, lock release |
| Generated graph | 3 guards; unchanged old contracts, exact anchors, public authority |
| Actual parser/Digest/client | 23 loopback cases; real PC publisher to native clock state |
| Prior SceneEngine regression | 33 cases / 268999 checks; music exclusivity and image ownership |
| ESP8266 public link | One new compile; Core3.1.2, ArduinoJson7.4.3, GFX1.6.4, AnimatedGIF2.2.0 |
| Native resources | ELF sections/symbols; compiler .su crosschecked with Xtensa prologues |

Only public fixtures, RAM SDK/flash/RTC seams and loopback sockets were used.
Local PC `inspect` sampled real system UTC/offset with sockets forbidden.
No SmallTV contact or hardware write. MSVC sanitizers **NOT_RUN**; new-diff CI,
physical LCD/load/memory minima **NOT_RUN**. Unchanged massive OTA matrices
were not rerun. The existing B5.1 baseline was not rebuilt.

| Resource | B5.1 public | B5.2 public | Delta |
| --- | ---: | ---: | ---: |
| BIN bytes | 414112 | 420224 | +6112 |
| Static DRAM (.data+.rodata+.bss+.noinit) | 44904 | 46492 | +1588 |
| .data | 1648 | 2516 | +868 |
| .rodata | 12848 | 13592 | +744 |
| .bss | 30352 | 30328 | -24 |
| .noinit | 56 | 56 | 0 |
| Maximum resolved compiled OTA path | 1616 | 1616 | 0 |

Installed **private** B5.1 is a different artifact (414176 B / 44968 static DRAM
in retained owner evidence). Do not derive private/native free heap from this
public +1588 static increment. Clock state20 B; renderer868 B includes the
448-byte scanline. HOST renderer observed zero allocations, no native framebuffer.
Sync/status compiler frames48/64 B; step144 B, header144 B, calendar48 B.
Known clock-sync/draw prefixes272/432 B exclude printf, remaining GFX/SPI,
SDK/ROM/IRQ and allocator behavior: they are not full or physical stack bounds.

Static increment1588 B fits the explicit2048 B **offline engineering budget**
with460 B remaining; that is not a native heap margin. Unchanged OTA floors:
admission heap25600 B, execution20480 B, largest16384 B, continuation2048 B,
fragmentation<=25%. Native B5.2 heap/block/fragmentation/stack **NOT_MEASURED**.
Historical B5 stack2128 B/80 B margin does not qualify B5.2. No floor was lowered.

ELF4m2m remains `_FS_start=0x40400000`, `_FS_end=0x405fa000`,
`_EEPROM_start=0x405fb000` (physical offsets0x200000/0x3fa000/0x3fb000).
No new rollback or absence-of-pending-RTC-command guarantee is claimed.

## Review correction and limits

Independent read-only review found one Important issue: inactivity timeout could
let a trickled response hold the Digest lock. Fixed with a **one-second
monotonic deadline for the entire locked status/challenge/POST exchange**, socket
tracking/shutdown during headers or body, maximum three requests and one POST
reserved before sending. Two loopback trickle phases now prove bounded return,
socket closure, lock release and no retry; regression observed RED then GREEN.
HTTPError responses also close explicitly, with a RED/GREEN regression.
The review found no additional actionable firmware defect.

**No automatic clock publication is added to active SHINO LINK in this mission.**
The provider is an explicitly disabled callable library, with inspect-only CLI.
Future scheduling must preserve metrics cadence and shared Digest coordination.
Unknown results stop without a replayed POST. Windows configured time/offset is
the stated authority; time-service accuracy, real transit/drift, timezone changes
between samples and hardware clock precision remain unverified. Weather remains
unavailable. No private build, installation, OTA, reboot or merge is authorized.

The reviewer deferred physical LCD/load/watchdog/memory/OTA recovery, future
LINK/weather/music scheduling, OS clock authority races, the recorded font
backlog and inherited Digest integrity/replay redesign. These remain explicit
boundaries; time controls display only, never security or OTA deadlines.

[HOST report](b52-clock/HOST_REPORT.json) ·
[Parser/client report](b52-clock/NETWORK_REPORT.json) ·
[ELF/resources](b52-clock/NATIVE_RESOURCES.json) ·
[240x240 captures](b52-clock/README.md).

**Next action:** owner reviews the local clock protocol, PC source/lease,
captures and +1588 B static cost entirely offline before approving any subsequent
publication or private candidate. No physical authorization is sought.
