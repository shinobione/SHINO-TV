# B5.3 LEAN — préparation propriétaire locale, hors ligne

Branch **feature/shino-tv-b53-lean-qualification**. The working
tree must be clean and HEAD must match the remote-tracking SHA.
Prior B5.2 private credentials are REUSED read-only from exactly one
existing Git worktree. They are never regenerated, copied or printed.
If identity is ambiguous, build is HOLD.

On the owner's Windows Codex checkout on that exact branch:
\`\`\`powershell
py -3 tools/shino_b53_lean_owner_candidate.py
\`\`\`
If and only if pinned dependencies are absent, use the explicit
\`--bootstrap-libraries\` option (it MAY download pinned PlatformIO
dependencies, but NEVER contacts the SmallTV).

Private outputs exist **only** in this checkout's ignored
\`research-local/m9-owner/b53-lean-private-<unique>/\`, including:
\`firmware.bin\`, \`release.json\`, \`report.json\`, generated C++ and
\`b53-lean-safe-receipt.json\`. Do not commit, upload, attach, email,
or publish private BIN, credential files, manifests or build logs.

The builder verifies bytes and SHA-256 from the actual private BIN,
the manifest/report match, clean SHA, 4m2m layout, 56-byte noinit,
private clock identity and absence of weather HTTPS in the private
generated graph. A receipt with non-secret build facts is printed.
It does NOT perform a live GET or POST, OTA, flash, reboot, Wi-Fi
change, LittleFS write or Windows LINK modification.

**Evidence boundary**: CI tests use mocks and PUBLIC inert graphs
only. No GitHub private firmware build. The physical heap/stack and
OTA minima remain **NON VÉRIFIÉS**; the installed B5.2 remains unchanged.
No upgrade may be attempted until a fresh owner authorization names
the exact computed candidate SHA and a no-retry install plan.
