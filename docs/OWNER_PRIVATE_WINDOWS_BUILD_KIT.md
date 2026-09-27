# SHINO // TV — private owner Windows build kit (NO DEVICE INSTALL)

**Purpose:** create a **single matched, local and private** proof-of-build folder for the owner-approved V2 four-card dashboard, plus the exactly pinned official GeekMagic V9.0.44 **application-only** return image. It is **NOT** a bootloader, OTA uploader, factory-data dump or flash approval. The owner's single SmallTV-Ultra still runs its stock V9.0.44 software. No spare PCB, soldering, COM port, UART or purchase is required to prepare this package.

This guide and companion script are in **PR #17 Draft**, stacked upon the [PR #16 no-LittleFS 4m3m installation decision packet](FIRST_INSTALL_DECISION_PACKET.md). The kit only builds/checks private local files and downloads the immutable manufacturer reference from GitHub; it never opens the TV's \`/update\` page or accesses its LAN address.

## Requirements on owner's Windows PC

- A **fresh Git checkout** of the reviewed source commit (a downloaded ZIP does **not** preserve verifiable \`git rev-parse HEAD\`). Git for Windows and Python 3 with the \`py\` launcher available.
- Internet only for downloading the *original pinned manufacturer ZIP*, Python/PlatformIO packages and their firmware compiler dependencies. This is not a connection to your TV.
- A private **non-cloud-synchronised** destination, with enough free disk space for PlatformIO packages, temporary compiler objects and a small final packet. The launcher defaults to \`%USERPROFILE%\SHINO-TV-private-builds\`; check that this location isn't synchronised, shared or backed up publicly. The Python tool also supports \`--output-root\` to choose another local destination.
- Source commit SHA reviewed in the PR and explicitly copied as the **full 40-character hex value**. Never take an arbitrary moving branch HEAD as approved; the tool compares the exact local Git HEAD to the supplied SHA, requires a clean checkout, the correct GitHub origin, and PR #16 as an ancestor. The complete current SHA is shown in the PR. If the PR changes, re-review and use its newly approved SHA.
- **No previous ignored** \`firmware/include/shino_private_policy.h\`, \`firmware/private/credentials.txt\` or \`firmware/.pio\` build folder: the script refuses to mix older credentials/compiled objects with this run. Prefer a new clone.

### Owner-initiated, software-only steps

From PowerShell or the Git Bash/Git CMD environment:

\`\`\`powershell
git clone --branch safety/owner-private-windows-build-kit https://github.com/shinobione/SHINO-TV.git SHINO-TV-private-source
cd SHINO-TV-private-source
git rev-parse HEAD
\`\`\`

Review that this commit is the exact SHA recorded in the PR/review. Then double-click **\`start-owner-private-build.cmd\`** and paste the reviewed full SHA when prompted. It installs/checks only the local \`platformio\` and \`esptool\` Python tools before running the offline-to-device build. It makes no web request to the TV, sends no HTTP POST and has no serial/flash command.

The CLI equivalent permits another **private** local output root outside the Git repository:

\`\`\`powershell
py -3 -m pip install "platformio>=6.1,<7" "esptool>=5,<6"
py -3 tools/build_owner_private_packet.py --expected-source-sha FULL_REVIEWED_40_HEX_COMMIT --output-root "C:\PRIVATE_LOCAL_FOLDER\SHINO-TV-private-builds"
\`\`\`

The second command is a *compiler/verification command*, **not** a command to install firmware on the SmallTV. Do not enter or publish private WPA2, Digest or bearer-token values on the command line or in a GitHub issue/chat.

## What the script checks, in order

1. Validates reviewed SHA/source provenance, clean Git tree, stock-like \`eagle.flash.4m3m.ld\` linker, missing stale build objects and output destination outside the Git checkout **before** creating the packet.
2. Downloads only the **immutable historical** manufacturer's \`Ultra-V9.0.44/FW-Smalltv-Ultra-V9.0.44.zip\` from its specific published Git commit. Independently checks **exact ZIP byte length, SHA-256, Git blob SHA-1 and inner app member SHA-256** against the pinned local source manifest. It extracts the verified 494,144-byte original **application-only BIN**; this does not create a 4-MiB factory readback.
3. Generates unique per-build WPA2 setup AP, HTTP Digest and API bearer secrets **locally**, plus a build policy explicitly containing: \`SHINO_BOOT_PROFILE=0\`, \`SHINO_ENABLE_FACTORY_RESTORE=1\` (experimental **exact original app-only receiver**, not a generic OTA route), \`SHINO_FS_IMAGE_PRESENT=0\` and \`SHINO_ENABLE_FS_MIGRATION=0\`. Builds the actual 240×240 FS-less V2 via PlatformIO without a filesystem image.
4. **Moves** the matching original generated private policy and credentials into the owner's private folder. Checks the matching active compiled WPA2/Digest secrets and exact compiled OEM image pin, ESP image header and independent Espressif \`image-info\` checksum on the two app files. Checks 4m3m Arduino modeled OTA geometry (direct stock→SHINO and booting SHINO→official original app), and that both modeled stages end before the *inferred* original manufacturer's FS start.
5. Saves the sanitized report and exact actual candidate **size and SHA-256** without printing private passwords. Deletes ignored local compiler objects so a later build will not accidentally reuse them. It never creates an upload file for any remote service or any device command.

### Directory produced ONLY on the PC that runs it

\`\`\`text
%USERPROFILE%\SHINO-TV-private-builds\
└── SHINO-V2-PRIVATE-<source-SHA-prefix>-<UTC-timestamp>\
    ├── READ_ME_FIRST.txt
    ├── images\
    │   ├── original-GeekMagic-Ultra-V9.0.44.zip
    │   ├── FW-Smalltv-Ultra-V9.0.44.bin
    │   └── SHINO-TV-V2-4m3m-private-experimental-OEM-return.bin
    ├── private\                        <-- KEEP SECRET / DO NOT SHARE
    │   ├── shino_private_policy.h
    │   └── credentials.txt
    └── reports\
        ├── owner-private-build-manifest.json
        ├── sanitized-offline-review.json
        ├── platformio-build-PRIVATE.log
        ├── esptool-shino-PRIVATE.log
        └── esptool-original-PRIVATE.log
\`\`\`

No exact candidate hash is invented in advance: **the firmware contains independently randomized per-build credentials**, so its actual hash only exists after this owner-private run. The public CI test builds its own *different* ephemeral candidate, checks it, and deletes all secrets and binaries; it cannot give the owner a matching local deliverable.

On any failure the script leaves \`INCOMPLETE__DO_NOT_FLASH.txt\` with the private evidence. Keep it private; do not upload anything from an incomplete folder or mix it with a second run.

### What is useful to report back privately

Only the **\`reports/owner-private-build-manifest.json\`** and, if useful, **\`reports/sanitized-offline-review.json\`**. Before sharing, inspect them to confirm they contain no usernames, machine paths or private secrets you do not wish to reveal. **Never attach the entire folder, BIN, ZIP, private policy or credentials.txt** to a public PR, chat, GitHub Action or release. The script's success terminal output includes only candidate SHA-256 and lengths, which are fine to compare as fingerprints.

## Hard stop: none of this proves the stock flash is safe

- The owner's original manufacturer's \`/update\` free slot, app acceptance rules, real physical flash ID and end-to-end boot behaviour remain **UNKNOWN**. Its reported 3,121,152-byte photo/GIF FS is a compelling stock \`4m3m\` *fingerprint*, not an original-flash dump.
- Our 4m3m U_FLASH software model stages a size-fitting direct app and a later original-app return below the inferred manufacturer's data region. That **does not guarantee** the proprietary updater, SDK or power interruption cannot touch original data.
- The downloaded original GeekMagic ZIP restores only the *application* while an appropriate compatible updater is still running. It cannot recreate erased photo/GIF/settings bytes or rescue an unbootable app without independent resident recovery/hardware access.
- The temporary 4m1m loader's second hop **overlaps inferred old file sectors**, so it is NOT a stock-data-preserving substitute for a rejected direct OTA.
- No physical installation command or auto-install button is included. The script's JSON always says \`permission_to_flash: false\`. After reviewing a complete local packet, a **new explicit owner decision** must name that precise SHA-256 and one particular operation before any write to the single physical TV.

**Current outcome expected: PRIVATE SOFTWARE EVIDENCE READY, OWNER DEVICE UNCHANGED.**
