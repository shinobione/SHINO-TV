# Exact OEM factory-return path — security review candidate

**Status: compiled source candidate only. Physical device untouched. No first flash approval.**

SHINO // TV now contains a dedicated factory-return module that can be built **READ-ONLY by default**, or with experimental upload enabled only by a verified per-build device policy. Both the normal SHINO application and its boot-loop Rescue mode share the same exact-image logic. This is deliberately different from the temporary first-hop Wi-Fi loader, which is overwritten when SHINO is installed.

## Why we implemented this

The owner has one SmallTV-Ultra V9.0.44, requests no soldering/no spare PCB and wants Wi-Fi-only installation. The exact official [historical Ultra-V9.0.44 update](https://github.com/GeekMagicClock/smalltv-ultra/blob/55d7877fcba8b1cb7a66a0830d35d5b374bc8540/Ultra-V9.0.44/FW-Smalltv-Ultra-V9.0.44.zip) is available, but it is **application OTA**, not the full original flash. Keeping a verified original app image outside Git is essential. Embedding the proprietary OEM image in our custom image would consume flash and would not help if the program cannot boot.

## Deployment states

| Source build | Factory GET status | Factory POST | Other OTA / rescues |
|---|---|---|---|
| Default (no `--enable-restore`) | Authenticated status only | **Not registered** | No generic arbitrary firmware or filesystem upload; no `/legacyupdate` |
| Experimental (`--enable-restore`) | Authenticated status | Exactly OEM V9.0.44 PIN ONLY; never arbitrary image | Rescue AP uses distinct HTTP Digest auth, same exact OEM image restriction |

The normal application routes are `GET /api/v1/shino/factory-restore` (Bearer token) and optionally POST there with multipart field `factory_v9_0_44`; Rescue mode serves `GET` and optionally POST `/api/v1/rescue/factory-restore`, protected by Digest authentication on its private WPA2 AP. There are **no anonymous token-reset, reboot, rescue generic OTA or reset-counter operations**. A failed filesystem mount does not enable a legacy open updater, and `/config.json` is no longer directly exposed.

We have deliberately **not supplied an upload command** here. Before any such instruction, the owner must inspect and explicitly approve the build, understand unresolved filesystem/boot risks, and separately authorize the action.

## Exact image acceptance

- Generator `tools/generate_shino_device_policy.py` verifies the pinned OEM **ZIP and inner SHA-256**, and generates a private local header containing only official size/MD5/SHA-256 plus separate random credentials. It never includes the proprietary OEM bytes or sends any network request.
- Owner image accepted only if flash capacity is 4 MiB; free sketch space is sufficient; multipart field matches; ESP8266 image header is plausible; size is exactly **494,144 bytes**; and the complete stream matches the **compiled original manufacturer MD5**. The compiled MD5 is generated from the archive with the separately verified SHA-256, not accepted from client input.
- `Update.end(false)` (not `end(true)`) is called only on an exactly complete stream; incomplete/wrong digest updates are rejected without requesting a boot switch. On a staged failure the running app schedules a reboot to discard its Update state.
- The completed endpoint sends a JSON response before the controlled restart; it does **not** erase/format the filesystem.

MD5 is only the hash supported by the ESP8266 Arduino streaming Updater. Trusted off-device SHA-256 is separately checked against the manufacturer's pinned archive. This does not create hardware secure boot.

## Credentials

Private files `firmware/include/shino_private_policy.h` and `firmware/private/credentials.txt` are **gitignored**, generated independently for each build from the exact OEM source. The Wi-Fi password, initial API Bearer token and Rescue-mode HTTP Digest password are three different random values. There is no publicly known default SSID/password to use for SHINO setup or Rescue. If encrypted storage is unavailable the in-memory initial API token still exists; do not mistake its XOR-obfuscated persistent storage for encryption.

Use no default credentials from the old Times-Z code. Protect the generated credential file and do not send it in a public chat, repository, screenshot or CI artifact. Experimental CI uses ephemeral credentials and deletes them immediately.

## What remains unproven (deployment NO-GO)

1. Free OTA space and actual acceptance of the first loader by the owner's proprietary V9.0.44 remain unmeasured.
2. ESP8266 factory *filesystem partition layout* after our `4m2m` flash setting remains unknown. A correct original application image does not necessarily restore stock assets, settings or layout.
3. If the CPU cannot boot *either* SHINO or its boot-loop rescue code, no Wi-Fi route can accept a repair image. The first-hop loader is overwritten by final OTA, not resident.
4. An incomplete/power-interrupted write, actual screen/Wi-Fi boot and full OEM restoration are not proven by compiling or source checks.
5. Main app security still needs broader runtime review; these source changes address specifically inherited recovery/AP/config/OTA routes.

This PR does not publish a flashable release image, commit any OEM binary or touch any physical device.

Related: [Single-device Wi-Fi plan](ONE_DEVICE_WIFI_PATH.md), [Original image pin](../recovery/README.md), [Dedicated temporary loader](../recovery_loader/README.md).
