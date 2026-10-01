# P1 controlled installation attempt — HOLD

2 October 2026, Europe/Paris. Existing Draft PR #41, branch
`codex/shino-tv-p1-home-lan`, starting HEAD
`d63b58b2f5072452e2be847b7755e9a2b7d81ba1`.

**The single authorized M8→OEM upload attempt did not obtain a staged
acknowledgement. The chain stopped without retry. Mission 8 remains responsive
with its prior boot identity; P1 is NOT INSTALLED / DEVICE NOT RUN.**

## Authorization and immediate preflight

Jerry Quinet explicitly authorized both exact application writes and their
expected installation reboots, accepting Wi-Fi-only/no-UART recovery risk:

| Image | Bytes | Reverified SHA-256 |
| --- | ---: | --- |
| OEM Ultra-V9.0.44, Hop 1 | 494144 | `a6421f5bfee7860d97bed26620c346b8008f503e513702d4bfdf6e01010a7718` |
| Approved P1, Hop 2 | 464544 | `31e3f225744bd806df3302dbf3355770a313f8b71f65b33fd6e2f431449b0be5` |
| Retained current M8 | 446944 | `269fcf2be7e61b4f581f892f36c519cca5ebf1ef41759d9923d9df90aad682fa` |
| Retained V2.1 review-003 | 405712 | `3252ba5cd1f85683945d4d9a87ce49118568c0977605debc089267f54d7f3b0e` |

All four files and the P1 ELF hash matched the private preparation evidence.
Private policy/Digest credentials matched the exact compiled P1 image. No rebuild,
image substitution, key generation or private artifact publication occurred.
Starting HEAD matched the authorization and remote Draft PR; exact-head CI was
passing (13/13 in each offline push/PR suite, plus native baseline and Wi-Fi-path
checks). These are CI-PASS, not P1 DEVICE-PASS.

The owner confirmed correct current LCD orientation, four changing cards and no
corruption immediately before execution. Current LINK is Python sender PID
10228 with launcher PID 2272, running the existing checkout tray. The retired
historical diagnostic PID was reconciled read-only; no sender restart, duplicate
sender launch, configuration or autostart change occurred. Live authenticated
metrics GETs showed fresh, changing CPU/GPU/RAM/GPU TEMP, with TTL still six seconds.

Authenticated GET-only preflight at 01:04:53 CEST verified 446944-byte Mission 8,
boot `2962927510`, actual 4194304-byte flash, enabled exact pinned OEM return and
no native OTA writer/upload route. No pending transaction, body, staged media or
secondary-stack references; allocation, secondary-allocation, busy and canary
failure counters were zero.

| Native measurement | Immediate preflight | Just before Hop 1 | Post-attempt GET |
| --- | ---: | ---: | ---: |
| Free heap, B | 19424 | 19088 | 18584 |
| Largest block, B | 16672 | 16672 | 16672 |
| Fragmentation, % | 14 | 13 | 11 |
| Continuation margin, B | 1728 | 1728 | 1728 |

These point observations satisfy the documented operation-entry limits. Existing
phase-5 minima were inherited (heap 11568 B, block 10296 B, continuation 1728 B);
no counter reset was issued. They are not fresh P1 phase minima or complete peak
allocation bounds. Retained image remained 2048 B; historical secondary high-water
2708/6200 B and metadata peak 1984/2048 B are M8 evidence only.

## Single attempted Hop 1 and read-only investigation

At 01:05:36–01:05:39 CEST, the client submitted one multipart OEM-return POST with
the pinned field/image after immediate rehash and fresh identity/resource checks.
The write client has no Digest retry handler, redirect following or automatic
upload retry. An attempt receipt was saved before invoking the POST.

The client raised `HTTPError` and obtained no verified `status: staged`
acknowledgement. The helper did not preserve the HTTP error code or response
body; neither is reconstructed or guessed. The exact rejection cause and whether
any OTA staging-sector writes occurred are **UNKNOWN**. One upload attempt is
not evidence of one successful firmware installation or zero flash writes.

The chain stopped. No second Hop 1 attempt, Hop 2 upload, rollback, network
switch or additional reboot was performed. No OEM boot was verified, so OEM LAN
rediscovery, `/v.json`, physical OEM clock and `/update` verification were NOT RUN.

GET-only investigation at 01:06:52 CEST found the same 446944-byte running M8 and
boot `2962927510`, reset reason 4, fresh telemetry, retained 2048-byte image,
zero pending/body/staged media/secondary references and zero failure counters.
Exact 494144-byte OEM capability remained enabled; native OTA writer/upload
route remained absent. No installation reboot was observed. There is no fresh
on-device SHA endpoint; running-lineage evidence remains size/boot/history.

The first investigation omitted the required browser bootstrap for the telemetry
cookie and stopped on an HTTP error after reading status/native observations.
A separate read-only investigation obtained the dashboard session and completed
all five GETs. It did not repeat any write. Post-attempt native HTTP service maximum
was 3081974 us versus inherited 600932 us before the upload; no complete telemetry
continuity window or upload transient heap/stack trace was captured.

The owner subsequently confirmed that the LCD remains correctly oriented, all
four cards update and there is no corruption. This is OWNER-OBSERVED current M8
display evidence, not P1 LCD qualification. Recovery is DEVICE-READ-PASS for
capability presence; successful OEM return remains unproven in this attempt.

## Stop state

- Installation chain: **HOLD**, after one unacknowledged Hop 1 attempt.
- Current M8: responsive, same boot, fresh metrics and owner-confirmed normal LCD.
- P1 boot/AP/LCD/three-minute memory baseline: **NOT RUN**.
- P1 saved SDK station state: **NOT INSPECTED**; no P1 boot to expose that status.
- Physical P1 pre-provisioning gate: **HOLD**.
- Persistent Wi-Fi configuration writes: **zero**; Change/Forget/provisioning not run.
- Router interruption, additional reboot, power-loss and advanced media tests: **NOT RUN**.
- Native updater activation, production provisioning and branch merge: **none**.
- PR #39/#40 preserved; R3 **PARTIAL**, R10 **BLOCKED**.

The owner-required first persistent Wi-Fi confirmation is deferred until P1
actually boots and passes its pre-provisioning baseline. The instruction limiting
each upload to one attempt has been exhausted for Hop 1; this report does not
authorize another POST. Preserve the responsive application while diagnosing
the uncertain upload. Private session receipts remain outside tracked evidence;
only sanitized observations are published here and in the companion JSON.
