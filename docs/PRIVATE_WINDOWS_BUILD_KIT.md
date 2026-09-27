# SHINO // TV — private Windows owner review kit (NO FLASH)

**Status: software preparation only.** The owner's sole SmallTV-Ultra stays on factory Ultra-V9.0.44. No second board, hardware UART, soldering, actual flash, manufacturer's update-page upload, or owner-LAN request is required or performed.

## Purpose and outputs

GitHub CI deliberately destroys ephemeral private credentials and BINs after its builds. The new Windows-only-by-choice private pack builder instead compiles the exact reviewed 4m3m FS-less V2 with a fresh pair of local AP/HTTP credentials and copies everything into ONE new private folder outside the Git checkout. It refuses an existing kit and will not reuse old keys.

The folder contains these **private** files:

- SHINO-TV-V2-PRIVATE-NOT-A-FLASH-APPROVAL.bin — compiled FS-less V2 using a source SHA pinned in the command, with experimental authenticated, exact-official-application-only return enabled. No claimed hardware test.
- OEM-V9.0.44-APPLICATION-ONLY.bin — independently verified original 494,144-byte OEM application, not an owner-specific whole-flash backup or an OEM photo/GIF/settings restoration guarantee.
- shino_private_policy.h and credentials.txt — per-build one-use secret values that correspond to the actual compiled SHINO BIN. KEEP PRIVATE, never paste in this chat, commit to GitHub, attach to a public issue or put in synced/shareable storage.
- REVIEW-ONLY-MANIFEST.json — sanitized source commit, BIN sizes, SHA-256, explicit modeled direct/OEM-return staging geometry and never-flash status. No passwords or API token.

The generator deletes temporary secrets and compiled firmware left in the source checkout after transferring the checked pair. It removes an incomplete temporary kit if it fails. It will not overwrite anything in an earlier kit. The original OEM ZIP remains separately where the user obtained it.

## Windows prerequisites

Install Python 3 with the py -3 launcher, Git, PlatformIO 6.x and esptool 5.x. For example, from PowerShell:

    py -3 -m pip install "platformio>=6.1,<7" "esptool>=5,<6"

The initial package installation and PlatformIO dependency resolver may access public registries. The kit generator does NOT download the manufacturer's original firmware or contact the SmallTV. Obtain the official ZIP manually from this exact pinned manufacturer commit:

https://github.com/GeekMagicClock/smalltv-ultra/blob/55d7877fcba8b1cb7a66a0830d35d5b374bc8540/Ultra-V9.0.44/FW-Smalltv-Ultra-V9.0.44.zip

The generator checks both the entire ZIP and the one original application member against the committed exact SHA-256 manifest before doing any build. It does not accept a similarly named substituted package.

**Use a FULL Git checkout, not GitHub's Download ZIP.** That ZIP omits the Git commit provenance required by the gate. After reviewing the completed PR #17 and its green CI, copy its **full 40-character reviewed HEAD SHA** and checkout that exact SHA locally (detached HEAD is fine), then require an otherwise clean source tree. Branch names alone move and are not a sufficient production freeze.

    git checkout FULL_40_CHARACTER_REVIEWED_GIT_SHA
    git rev-parse HEAD
    git status --porcelain

The last output must be empty. Existing generated policy/credentials, old candidate BIN or config.json are a STOP condition. Do not bypass by mixing files from different builds.

## Running the local-only step

Create a private LOCAL parent folder OUTSIDE the repository, for example D:\SHINO-PRIVATE. Prefer a local encrypted/BitLocker drive rather than OneDrive/Google Drive/shared directories. Choose a NEW child path that DOES NOT exist yet, then from the exact checkout root use:

    py -3 tools/build_private_owner_packet.py --expected-source-sha "FULL_40_CHARACTER_REVIEWED_GIT_SHA" --official-zip "D:\SHINO-PRIVATE\FW-Smalltv-Ultra-V9.0.44.zip" --out-dir "D:\SHINO-PRIVATE\review-001"

Alternatively invoke the included batch wrapper:

    start-private-owner-build.cmd "D:\SHINO-PRIVATE\FW-Smalltv-Ultra-V9.0.44.zip" "D:\SHINO-PRIVATE\review-001" "FULL_40_CHARACTER_REVIEWED_GIT_SHA"

The wrapper never installs packages or runs a device upload. The Python tool executes the checked local policy generator, the PlatformIO ESP8266 compilation and esptool IMAGE-INFO on the two exact local BINs. It confirms the footer checksum is explicitly reported VALID, compares the copied private policy and generated credentials to those embedded in that very candidate, checks the fixed 4m3m source layout and that the source-level model stages direct installation and official app return before the inferred original FS boundary. It produces a sanitized report only if all gates pass.

Only share the non-secret source SHA, firmware size and SHA-256, plus sanitized manifest's modeled results for an eventual review. Do NOT share credentials, private header, BIN, owner flash data or screenshots containing secrets. A SHA-256 checks file identity, not whether the vendor updater will physically accept it.

## Separate physical decision, still not made

Successful private compilation is NOT permission to upload. The real stock V9.0.44 available OTA slot, proprietary accept/boot behavior, exact owner flash map, preservation of owner data through any SDK writes, uninterrupted power and a recovery method from a nonbooting application remain unknown. The historical OEM ZIP restores the application only, not the complete original 4-MiB owner chip, and no reliable Wi-Fi-only rescue exists if SHINO fails to start.

Before any physical use, confirm the sole TV is still on stock firmware using a fresh GET-only owner report, compare the named frozen candidate SHA-256 and the real local sanitized manifest, discuss the remaining no-boot risk, and request a NEW explicit authorization for a specific image and one named OTA action. The generated private kit deliberately contains no install command, HTTP POST or physical flash tool invocation.

See FIRST_INSTALL_DECISION_PACKET.md in this folder for the numerical direct-vs-temporary-loader comparison, including the original-data-overwriting second hop of the old 4m1m loader.
