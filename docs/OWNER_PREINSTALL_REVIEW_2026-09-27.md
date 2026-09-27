# SHINO // TV — owner-specific preinstallation review (2026-09-27)

**Disposition: offline/read-only preparation recorded. Physical installation gate CLOSED. This record is not flash authorization.**

This is a sanitized owner-specific addendum to [FIRST_INSTALL_DECISION_PACKET.md](FIRST_INSTALL_DECISION_PACKET.md). It is based solely on two owner-supplied local JSON outputs; the reviewer did **not** receive or independently hash the private BIN, private policy or credentials. No device write or test upload was carried out. No device IP or private credentials are included here.

## 1. Owner-private Windows packet — supplied manifest

Source: owner-generated `REVIEW-ONLY-MANIFEST.json`, shared for review on 2026-09-27. The manifest has no creation timestamp; this section does not assert an independent local re-build.

| Item | Manifest value |
|---|---|
| Report status | `PRIVATE_KIT_READY_FOR_REVIEW__OWNER_FLASH_NOT_AUTHORIZED` |
| Exact source commit | `fb8fc619c8f00c132466a7b2e94e8fc3d506ddc5` (PR #18 source) |
| SHINO experimental V2 private application | **398,864 bytes** |
| SHINO candidate SHA-256 | `bd8c9b1ea86caace5fd088f889071b8091b083887383cdc0123e5d950b2b5738` |
| Candidate ESP8266 image header | DIO / 4 MB / 40 MHz / 2 segments |
| Candidate linker and first-boot marker | `eagle.flash.4m3m.ld` / `FSLESS_NATIVE_UI_V2` |
| Official manufacturer ZIP SHA-256 | `cfbef50754ec552f9791878931c5f3643734de15f3c81cebdecf7ce05b28230f` |
| OEM V9.0.44 application size | **494,144 bytes** |
| OEM application SHA-256 | `a6421f5bfee7860d97bed26620c346b8008f503e513702d4bfdf6e01010a7718` |

The owner's manifest reports `true` for pinned OEM/policy matching, private policy/credentials matching, active AP/Digest secrets found in compiled app and experimental OEM application-only return included; it reports FS migration not compiled and no credential values in the public report. The builder produced locally retained private files, **not** GitHub artifacts. Keep `credentials.txt`, `shino_private_policy.h`, private application and OEM BINs on the owner's controlled local storage; do not commit/share them.

The **398,864-B private application** is the owner-reported candidate, not the earlier disposable CI example of 398,848 B. Never substitute an earlier CI BIN or SHA, or pair it with credentials from a different build. Hashes in this record identify reported files; the JSON by itself is not an independent re-hash of those private files.

### Owner-manifest OTA geometry models (not observed on hardware)

| Hypothetical transition | Rounded incoming sectors | Staging range | Inferred original FS overlap | Nominal gap |
|---|---:|---|---:|---:|
| Stock OEM → exact private SHINO V2 DIRECT | 401,408 B | `0x09E000..0x100000` | 0 B | 151,552 B |
| Running SHINO 4m3m → pinned OEM application | 495,616 B | `0x087000..0x100000` | 0 B | 151,552 B |

These are arithmetic/source-layout models **assuming** a 4m3m-like stock boundary; they do not measure the live proprietary OTA free slot, `Update.begin()`, physical flash ID or actual OEM sector writes. The historical temporary 4m1m loader route remains **not an original-data-preserving fallback**. An exact OEM application BIN cannot restore full original flash, files/settings or a nonbooting device.

## 2. Fresh owner-operated GET-only stock report

Source: owner-generated `stock-report(1).json`, observed **2026-09-27 09:52:23 UTC** (11:52 in France). Its reported HTTP methods were only `GET`; no redirects, firmware upload or write attempt.

| Requested route | Sanitized observation |
|---|---|
| `GET /v.json` | `SmallTV-Ultra`, `Ultra-V9.0.44` |
| `GET /space.json` | Image/GIF filesystem: total **3,121,152 B**; free **1,056,268 B** |
| `GET /app.json` | Theme ID **5** |
| `GET /update` | HTML form: `POST`, default page action, `multipart/form-data`, file field `firmware`, zero script tags |

The storage total agrees numerically with Arduino ESP8266 4m3m filesystem capacity, supporting—but **not proving**—that actual proprietary layout. The storage total/free describe the manufacturer photo/GIF area **not OTA staging capacity**. The `/update` form was inspected via GET only; no POST or acceptance test was performed. Stock OTA capacity and image validation remain **UNKNOWN**.

## 3. Residual risk / stop conditions

- Exact stock V9.0.44 OTA available application bytes, proprietary acceptance of this exact private SHA and actual flash map/physical flash ID are not established.
- No boot, LCD four-card UI, AP/WPA2, HTTP Digest, Windows RAM-only telemetry, stale state or OEM-return behavior has been demonstrated **on the owner's physical unit**.
- No full 4-MiB owner-specific flash backup or reliable independent Wi-Fi recovery from a nonbooting application exists under the stated one-device, Wi-Fi-only/no-UART/no-solder constraints.
- The OEM ZIP is **application-only**, not a full device/filesystem/asset/settings restoration package. The zero-overlap arithmetic does not prove real data preservation or power-loss safety.
- The manifest states that independent `esptool image-info` checks are mandatory; this supplied JSON does not contain the raw esptool output, and the reviewer did not independently inspect the private local BINs. A later hardware decision must bind any independently checked result to these **exact** SHA-256 values.
- Do not send a dummy firmware to the stock updater to discover its capacity; that could exercise write paths.

## 4. Disposition and scope of any later decision

**Owner-specific preinstallation evidence is consolidated and the offline/read-only documentation step is complete.** It does not resolve the risks above. Preserve the private matched packet locally and keep PR #18 Draft. No merge, firmware release, manufacturer `/update` POST, OTA, filesystem upload, flash or physical installation is authorized by this review.

Any later physical action requires a **fresh, separately recorded owner decision** naming the exact private SHINO SHA-256 `bd8c9b1ea86caace5fd088f889071b8091b083887383cdc0123e5d950b2b5738` and the single intended action, after explicit review of the remaining no-boot and original-data risks. General approval of documentation, compilation or the phrase “go” for offline work is not an installation approval.
