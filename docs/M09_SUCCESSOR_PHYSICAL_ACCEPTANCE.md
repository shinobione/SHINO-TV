# Mission 9 — owner-supplied successor physical acceptance

Source: [owner comment, 7 October 2026, 17:14:28 UTC](https://github.com/shinobione/SHINO-TV/pull/42#issuecomment-6042956937),
recorded from PR #42 head `1b696e530d6d2b0d1bfa6503b5fe320214ac621f`.
These are owner-performed observations, not agent device actions or independent
agent verification. Private captures, digests, paths, identifiers and credentials
are not published. Historical predecessor receipts remain unchanged.

## Exact installation and preservation reported by owner

- Candidate **411152 B**, SHA-256
  `e1852e56d99801b694f37d235b08a201188cf36d5a25f3f6f59d059a129bc27e`.
- Independent full PRE/POST before first boot: candidate exact at zero;
  **0x065000..0x3FFFFF** byte-for-byte PRE-equal, including LittleFS and tail.
- RTC magic/CRC nonzero after powered stub work; owner executed the already
  reviewed two-word neutralization and verified both **0x00000000** before
  GPIO0 release and EXT_RST. No agent RTC action.
- First normal application boot: `rst cause:2`, `boot mode:(3,7)`, `v00064610`,
  `~ld`; no observed `cp:`, crash loop or display corruption. This boot wording
  describes boot mode, **not firmware profile 1**; installed firmware is profile 2.
- Autoformat disabled, mounted, inventory/config exact, **24 files / 181402 B**;
  blocked filesystem writes **0**.
- One-shot LINK accepted; **180 s** continuous LINK kept all four values visible
  and evolving, CONNECTED, no reboot/display corruption. Stopping LINK showed
  stale state; subsequent one-shot restored CONNECTED and all four values.

## Resource observations and scoped acceptance

| Owner observation | Initial | Final | Phase-K criterion |
| --- | ---: | ---: | --- |
| Mount continuation minimum | 2336 B | 2336 B | >=2048 B; margin **288 B** |
| Runtime continuation minimum | 3424 B | 3304 B | >=2048 B; final margin **1256 B** |
| Minimum observed free heap | 30232 B | 27640 B | >=20480 B; final margin **7160 B** |
| Lowest sampled free heap | Not supplied | 29560 B | >=20480 B |
| Lowest largest free block | 30328 B | 27552 B | >=16384 B; final margin **11168 B** |
| Maximum fragmentation | 6% | 7% | <=25%; final margin **18 percentage points** |
| Rejected resource samples | 0 | 0 | Exactly 0 |
| Blocked filesystem writes | 0 | 0 | Exactly 0 |
| Sample count | Not supplied | 583, advancing | Owner confirms advancement |

The comment is a summarized owner receipt, not two complete status JSON captures;
missing fields remain unknown. No synthetic values are passed off as raw data,
and the strict Phase-K full-JSON evaluator is not claimed to have validated
unsupplied fields. Numeric comparisons above and the owner decision establish
the stated scoped acceptance. Dense heap minimum and sampled free-heap minimum
have different sampling windows and are recorded separately.

| Gate | Current owner decision |
| --- | --- |
| MOUNT_PROBE_RESOURCE_PHYSICAL_GATE | **PASS**, exact dedicated profile-2 successor/run |
| MOUNT_PROBE_PHYSICAL_GATE | **PASS**, exact dedicated profile-2 successor/run |
| NORMAL_PROFILE_LITTLEFS_MOUNT_GATE | **NOT_RUN** |
| NORMAL_PROFILE_RUNTIME_GATE | **NOT_RUN** |
| Native signed OTA / full product / home-LAN promotion | **Not qualified by this receipt** |

Installed J predecessor's1776 B mount continuation remains its historical
**FAIL/HOLD** at2048 B; it is not retroactively corrected. Earlier successor
NOT_RUN wording was correct before this new owner evidence.

Agent counters for recording this receipt: **DEVICE CONTACTS=0; SERIAL I/O=0;
FLASH WRITES=0; RTC WRITES=0; REBOOTS=0; DEVICE FILESYSTEM WRITES=0**.
No physical authorization is conveyed. Continue only the offline readiness
pass in [the focused design receipt](M09_NORMAL_PROFILE_READINESS.md).
