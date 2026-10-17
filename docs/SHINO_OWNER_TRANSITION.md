# SHINO // TV — Mission 9 owner-private transition

The reviewed public qualification is complete on the owner's Windows machine.
This workflow prepares a device-specific binary **offline**, not a flash-ready release.

## Windows

From a clean, up-to-date `feature/shino-tv-m9-flash-layout-liberation` checkout,
run `companion/SHINO-OWNER-TRANSITION.cmd`.

The command checks private-source regressions, generates unique AP, HTTP Digest,
bridge API and maintenance credentials locally (first run only), then runs an
isolated 4m2m Xtensa build. Later calls never overwrite the existing credentials
or prior build. Use Python 3, Git, and PlatformIO 6.1.18.

**Only share:** `research-local/m9-owner/transition-report.json`.

**NEVER share or commit:** `research-local/m9-owner/owner-credentials.json`,
`research-local/m9-owner/transition-build/`, any private BIN, compiler log,
AP/Digest credentials, maintenance secret or SHA-256 preimage. This directory
is excluded by `.gitignore`. The credentials file is a local plaintext file;
protect it with your Windows account and a private backup.

The generated AP/Digest/API credentials are **new**, not the currently installed
StageA credentials. SHINO // LINK must be explicitly reconfigured after any
future approved physical installation. There is NO silent credential migration.

The private candidate contains the dormant authenticator/receiver code, including
an owner-only INSTALL route guarded by a separate HMAC proof and successful
memory probe. It has NOT been qualified on the real TCP/SDK heap, stack or flash,
and building it does NOT grant installation authority.

**Explicitly forbidden now:** UART flashing, live network probing, OTA writer
activation, boot selection, filesystem changes, repository merge, or uploading
private artifacts to GitHub. Permission requires a new review of the exact
firmware SHA-256, resource floors and return path, plus separate owner approval.
