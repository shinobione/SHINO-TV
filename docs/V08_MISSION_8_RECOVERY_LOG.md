# Mission 8 rollback preflight and recovery log

30 September 2026, Europe/Paris. **No installation, device write, reset or recovery
attempt was performed.** Existing V2.1 review-003 remains the running baseline.

## Positively identified retained packages

Files below were read and SHA-256 hashed locally against the retained
`C:\Users\jerry\SHINO-PRIVATE\review-003\REVIEW-ONLY-MANIFEST.json` and the
repository's immutable OEM reference. No artifact, credential or policy was
modified. No binary/private policy was committed or uploaded.

| Priority / exact local file | Bytes | SHA-256 | Expected state / installation mechanism |
|---|---:|---|---|
| 1: `C:\Users\jerry\SHINO-PRIVATE\review-003\SHINO-TV-V21-HEAP-PRIVATE-NOT-A-FLASH-APPROVAL.bin` | 405,712 | `3252ba5cd1f85683945d4d9a87ce49118568c0977605debc089267f54d7f3b0e` | V2.1 review-003, source `8cef03012ae4a4864d69cbe20e02f141a36e2d54`; supported stock OEM `/update` after a successful OEM return |
| 2: `C:\Users\jerry\SHINO-PRIVATE\review-003\OEM-V9.0.44-APPLICATION-ONLY.bin` | 494,144 | `a6421f5bfee7860d97bed26620c346b8008f503e513702d4bfdf6e01010a7718` | GeekMagic Ultra-V9.0.44 application; existing authenticated OEM-only factory-return multipart path |
| Original `C:\Users\jerry\SHINO-PRIVATE\FW-Smalltv-Ultra-V9.0.44.zip` | 349,377 | `cfbef50754ec552f9791878931c5f3643734de15f3c81cebdecf7ce05b28230f` | Exact manufacturer archive; application member byte/hash matched pinned reference |

The current live factory-return **GET** reports the pinned OEM identity,
494,144-byte size and `write_enabled:true`. Review-003 source requires matching
Digest authentication, `factory_v9_0_44` multipart file field, `.bin` filename,
physical 4 MiB flash, sufficient staging, exact expected bytes and OEM digest.
It does not accept an arbitrary SHINO image. No multipart request was sent.

The supported Wi-Fi chain is SHINO → exact OEM application → SHINO via the OEM
update page. Its prior owner-tested history is retained in
[Wi-Fi return-chain audit](V21_WIFI_ONLY_RETURN_CHAIN_AUDIT.md); historical
review-002 wording there is not used to identify today's device. Today's
review-003 identity and OEM capability were checked live in Mission 8.
The exact V2.1 package cannot be uploaded directly to the OEM-only return route.

**Rollback artifact/hash availability and current OEM-return capability PASS.**
Future candidate OEM-return implementation, boot recovery window, post-candidate
rollback and OEM `/update` acceptance were not physically qualified here. No
claim is made of nonbooting rescue: there is no hardware recovery path, no
full-chip backup, and application-only OEM return cannot restore unknown stock
filesystem contents. Existing recovery availability depends on a booting Wi-Fi
application. This is why the stack failure stops installation.

## Timestamped log

| Time, 30 September 2026 | Action / result |
|---|---|
| Before contact | Clean exact Mission 7 parent verified; separate branch created; PRs #29–37 preserved |
| Preflight, before device diagnostics | Retained review-003/OEM binaries and original ZIP hashed; all exact pins matched |
| 19:57:12.459 Europe/Paris / 17:57:12.459 UTC | GET factory-return HTTP 200; exact OEM bytes/hash and `write_enabled:true` |
| 19:57:12.538 Europe/Paris / 17:57:12.538 UTC | GET OTA capabilities HTTP 200; generic native writer/upload route absent |
| After preflight | Owner confirmed normal four-card physical display and orientation |
| Static pre-installation inspection | Linked crypto/receiver stack exceeds 4,096-byte Core stack; escalation stopped |
| Installation start/end | NOT STARTED / NOT APPLICABLE |
| Upload HTTP/result | NO UPLOAD REQUEST |
| Candidate SHA/binary | NO activated/instrumented Mission 8 candidate built |
| Post-install version | NOT APPLICABLE; device was not changed |
| Recovery action | NONE; no blind reflash, power cycle or factory return |

## Resets and boot reasons

No reset, reboot or watchdog event was observed/reported during the short
GET preflight, and no reset was induced. The current endpoints expose no reset
reason or boot counter. **Actual boot/reset reason is UNKNOWN**; absence of a
reported event does not prove absence of historical resets. Candidate reset,
boot and watchdog evidence is NOT RUN. The stack finding is static evidence,
not a concealed or inferred physical watchdog event.

Stop retained: leave the known-good installed device and both rollback images
unchanged. Resume only after reviewed stack remediation, a real bounded
instrumentation candidate, its exact image/policy/geometry checks, and all
remaining Mission 8 gates. No destructive recovery experiment is authorized.
