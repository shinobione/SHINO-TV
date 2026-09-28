# SHINO // TV V0.3 — isolated 240 × 240 PC SCENE LAB

Branch: feature/shino-link-v03-scene-preview, stacked on V0.2 Draft PR #23. This is a browser-only concept. The owner's **actual installed SmallTV remains private V2.1 review-003** with the four metrics sent by the separately working V0.1 Windows tray in C:\Users\jerry\SHINO-LINK. Do not modify that worktree, its current-user login startup, or its credential file to preview a new scene.

**What is and isn't implemented**

- An exact 240 × 240 Canvas display with **PC HEALTH as initial/main view**: all four CPU/GPU/RAM/GPU TEMP cards simultaneously visible; percent-based gauge hues mint/yellow/orange/burgundy and missing values shown as em dash rather than fake zero. GPU TEMP's gauge is a design-only 0–100 °C visualization, **not** a thermal threshold or hardware alert.
- Separate NOW PLAYING preview: square cover with local-image fallback, bounded title/artist, PLAYING/PAUSED/other status, static provided elapsed/total time, progress. If a user-selected artwork is 320×200 it is square center-cropped on PC; it is **not** a device memory format or media transport.
- Two preview policies: manual choice, or **5 seconds of music overlay** on new PLAYING track followed by health screen. Progress-only updates and pause do not retrigger. Both views can be explicitly selected at any time.
- Two labeled fixtures for design exploration; support for manually pasting a SINGLE JSON result copied from V0.2 GSMTC `py -3 companion/media_sessions.py --once` and manually choosing existing `%LOCALAPPDATA%\SHINO-TV\media-preview.jpg`. A browser cannot silently open that PC path. Paste a new single snapshot to refresh status/timing. This is **not automatic live playback or artwork sync**. Choosing a different title/source clears the previous cover to prevent false attribution.
- Security boundaries: no server endpoint or browser network call from app JS, account access, device communication, automatic folder scanning, flash/reboot/OTA or binary/image write to SmallTV. An owner-initiated PNG export stays on PC. Browser image file limit: 1 MiB, <=4096 px per side, <=4,000,000 pixels.

## Safe owner walkthrough (a third separate worktree)

Use a PowerShell that currently has Internet, and leave the existing Windows tray alive. In the original repository, fetch the V0.3 branch explicitly; then create an independent detached preview worktree:

```powershell
cd "$HOME\Documents\SHINO-TV"
git fetch origin refs/heads/feature/shino-link-v03-scene-preview:refs/remotes/origin/feature/shino-link-v03-scene-preview
git worktree add --detach "$HOME\SHINO-LINK-SCENE" refs/remotes/origin/feature/shino-link-v03-scene-preview
cd "$HOME\SHINO-LINK-SCENE\simulator"
py -3 -m http.server 8765 --bind 127.0.0.1
```

Keep that console open only while inspecting the preview; it is a loopback static HTTP server needed for modern browser ES modules, **not the existing V0.1 metrics tray**. It serves only the `simulator` directory of this separate checkout. In Chrome visit `http://127.0.0.1:8765/now-playing.html`. No Wi-Fi change, auth credentials or SmallTV network required; Ctrl+C in this scene-server console stops only the preview server.

Try FOUR METRICS, NOW PLAYING, the demo-track buttons and overlay policy. In the separate existing `SHINO-LINK-MEDIA` console, run the real GSMTC `--once` as desired and manually paste its JSON output into the editor; then APPLY MEDIA SNAPSHOT. In the file picker, explicitly browse to the already generated owner-local `media-preview.jpg`; the browser reads that one file for *visual-only* preview. It does not publish or upload it. An old cover is cleared on track identity change. For a manual PNG export, use SAVE LOCAL 240 × 240 PNG.

**Limitations:** The current SmallTV V2.1's authenticated /api/v1/bridge/metrics is narrow numeric telemetry only. Do not misuse it to send media JSON or art; real scene switching, image compression/transfer/buffering, heap/fragmentation, timing and failure paths all need a new reviewed protocol plus individually authorized firmware build/installation. A browser preview cannot validate RGB565/font contrast on the actual 240 × 240 LCD. The original simulator at `index.html` remains available.
