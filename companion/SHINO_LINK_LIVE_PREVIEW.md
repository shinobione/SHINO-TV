# SHINO // TV V0.4 — Live Media Bridge (PC-only)

This separate experiment stacks on the already owner-reviewed V0.3 scene preview in PR #24 and the owner-verified real GSMTC V0.2 in PR #23. **The owner's active V0.1 metrics system tray, its Windows HKCU login start, standalone $HOME\SHINO-LINK folder and physically installed V2.1 review-003 firmware remain unchanged.** This V0.4 is **NOT** an update for the physical TV.

## Architecture and boundaries

The manually started Windows process `companion/media_preview_server.py` polls Windows GSMTC (using V0.2 `capture(include_cover=True)`) ~every 3 seconds, preserving at most **one** bounded, private PC-RAM latest snapshot and JPEG preview (<=40 KiB). The browser and its data service are deliberately the **same loopback origin** at `127.0.0.1:8765`; no cross-origin fetch, no Spotify cloud API, no Spotify account token, no image files written by this bridge, no device interaction or changes to the independent CPU/GPU/RAM/GPU TEMP metrics worker. Covers are served as a separate fixed read-only path using the SHA-256 revision of the latest RAM JPEG. Old covers are revoked on track, cover or provider state change; old/stalled capture is marked STALE after 13 seconds rather than displaying old data as live.

Allowed browser files are ONLY `/now-playing-live.html`, `/now-playing-live.mjs` and `/now_playing.mjs`, no directory listing or arbitrary Python/repo/private-file route. JSON API `GET /api/v1/media/state` and JPEG `GET /api/v1/media/cover?revision=<sha256>` require a custom preview header and exact local Host; OPTIONS, POST and PUT have no handler. Browser sends no external requests. CORS permission is not supplied. The custom header prevents *ordinary unrelated websites* from reading the local API; it is not authentication from other already-local PC processes. Do not run the preview while sharing the Windows account with untrusted processes.

The V0.4 browser page **initially has live mode OFF**; press START LIVE PREVIEW to poll every ~3 seconds and automatically receive real published title, artist, pause/play state, progress and optional cover. Existing V0.3 Canvas code keeps PC HEALTH with **all four fields together** as default (only DEMO metric numbers on this page). Newly PLAYING titles create the tested 5-second overlay then return to PC HEALTH; pause, same-title progress and failure do not restart the overlay. Manual view choice and STOP LIVE remain available; failed/empty/stale media removes old artwork and shows explicit feedback. The viewer does not attempt playback control. Browsers decode local JPEG in memory, with byte/pixel caps and revision checks. A PNG is exported only if manually requested. The page does not silently grab an older PC image file.

## How to run without interrupting working metrics

Stop the **older V0.3 preview's** `py -3 -m http.server 8765 --bind 127.0.0.1` with Ctrl+C if it is still open, because V0.4 takes that preview-only port. **Do not stop the separate SHINO // LINK tray**; its four LCD cards must continue updating.

From PowerShell with Internet and the normal Git repository, create a **fourth detached worktree**, not a change to the existing `SHINO-LINK`, `SHINO-LINK-MEDIA` or `SHINO-LINK-SCENE` directories:

```powershell
cd "$HOME\Documents\SHINO-TV"
git fetch origin refs/heads/feature/shino-link-v04-live-media-preview:refs/remotes/origin/feature/shino-link-v04-live-media-preview
git worktree add --detach "$HOME\SHINO-LINK-LIVE" refs/remotes/origin/feature/shino-link-v04-live-media-preview
cd "$HOME\SHINO-LINK-LIVE"
py -3 -m pip install -r companion/requirements-media.txt
py -3 companion/media_preview_server.py
```

Wait for the printed browser URL. In Chrome on this same Windows PC open:

`http://127.0.0.1:8765/now-playing-live.html`

Press **START LIVE PREVIEW** while Spotify desktop (or another GSMTC source) plays a track. It should show real source/title/artist, static progress sampled every ~3s, and automatically fetch the current JPEG art from RAM if available. Press FOUR METRICS to leave the complete four-value view on screen, then switch tracks: NOW PLAYING should overlay for five seconds and return. Try pause/resume and switch to a music player without art; check that an older track's cover is not reused. Press STOP LIVE when done. Ctrl+C in this *new bridge* console shuts down only the optional browser/media server, not the tray metrics sender.

If Git says the new `SHINO-LINK-LIVE` worktree already exists, inspect before changing; never delete a folder without checking whether it has local changes. If bind fails, close the older **simulator http.server** or choose a different preview-only port using `--port 8766` and update the address to match. The listener always binds 127.0.0.1 even with an alternate port. No connection to the SmallTV's `192.168.4.1` or credential file is needed.

## Status / future gates

CI uses fake GSMTC snapshots to test stale/cover revocation, loopback Host/Origin and read-only routes; Windows verifies the real WinRT manager is available. It cannot prove this V0.4 background polling and artwork timing on owner's actual Spotify until owner runs it. The existing numeric V2.1 `/api/v1/bridge/metrics` cannot receive music JSON or image; converting this desktop design into an actual native display needs a separately reviewed authenticated transport, measured ESP8266 heap and flash budgets and individual owner installation approval. **No firmware image, OTA operation, merge or device write is authorized by this V0.4 PR.**
