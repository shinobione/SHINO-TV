# SHINO // LINK V0.2 — NOW PLAYING (PC only)

**Separate draft experiment** stacked on the owner-verified Windows V0.1 pilot in PR #22. The existing detached `C:\Users\jerry\SHINO-LINK` worktree, Windows login-start entry, V2.1 private firmware and four-metric transmission **are not updated by this PR**. Run this experiment in a separate worktree; never overwrite the live tray script to test experimental media.

## What V0.2 reads

Windows' **Global System Media Transport Controls (GSMTC)** exposes media sessions that applications elect to publish. An actual, selected/playing compatible session can provide: source app, title, artist, album, playing/paused/stopped, approximate elapsed/total time, and whether a thumbnail is offered. The probe prefers a playing session over a paused "current" browser; otherwise uses current. If no session, reports NO_SESSION. It does NOT promise every browser, website, Spotify variant or player exposes metadata/art.

Optional explicit `--cover-preview` obtains **one maximum 1 MiB thumbnail**, validates image dimensions/pixel count, strips metadata, converts/crops on PC into an at-most **192 × 192, 40 KiB JPEG** and writes one owner-local preview file `%LOCALAPPDATA%\SHINO-TV\media-preview.jpg`. No cover saved without this flag. Missing/unusable cover clears the old local preview. No external API, cloud token, playback control, HTTP listener, SmallTV upload, flash write or generic image transport. Music metadata is printed only when the owner explicitly runs the standalone CLI; normal V0.1 tray and numeric PC metric stream are untouched.

The cover flag is for **PC-only research**. The current real V2.1 SmallTV has a bounded numeric `/api/v1/bridge/metrics` endpoint and no artwork/scene interface. NEVER send the JPEG or text to that route and never change that firmware without a new separately authorized installation.

## Use on the owner's Windows PC without stopping live V0.1

From the existing repository checkout, while keeping current SHINO // LINK V0.1 in its dedicated `$HOME\SHINO-LINK` folder, create a second independent detached worktree on the new commit/branch:

```powershell
cd "$HOME\Documents\SHINO-TV"
git fetch origin refs/heads/feature/shino-link-v02-now-playing:refs/remotes/origin/feature/shino-link-v02-now-playing
git worktree add --detach "$HOME\SHINO-LINK-MEDIA" refs/remotes/origin/feature/shino-link-v02-now-playing
cd "$HOME\SHINO-LINK-MEDIA"
py -3 -m pip install -r companion/requirements-media.txt
```

No need for `--configure`, credential files or access to the SHINO Wi-Fi AP: NOW PLAYING is entirely PC-side. Before starting, use a player on the PC with actual music playing, for example the Spotify desktop app or a browser that publishes a Windows media session. Then:

```powershell
py -3 companion/media_sessions.py --demo
py -3 companion/media_sessions.py --probe
py -3 companion/media_sessions.py --once
py -3 companion/media_sessions.py --watch
```

`--demo` is clearly labeled fake metadata for offline schema/test confirmation. `--probe` genuinely awaits Windows GSMTC `RequestAsync` (without accessing titles, artists or covers); it requires the pinned `Windows.Foundation` and `Windows.Foundation.Collections` packages as well as `Windows.Media.Control`. `--once` reads one actual Windows session and prints bounded JSON; `--watch` prints on changes every ~3s, Ctrl+C stops. No media session means `{"state":"NO_SESSION",...}`; an OS/projection problem returns UNAVAILABLE without exposing raw WinRT errors. Actual title/artist may be empty for sources that do not publish them. Source identification is a publisher-supplied app ID, not a cryptographic identity of a streaming provider.

If the session reports a cover, and **only if you want a disposable owner-private artwork preview**:

```powershell
py -3 companion/media_sessions.py --once --cover-preview
```

A valid JPEG is stored only outside the checkout at `%LOCALAPPDATA%\SHINO-TV\media-preview.jpg`; the script prints that local path. Do not commit the preview or show private filesystem credentials. JPEG is an offline conversion target, **not** a verified transport fit or a device-bound payload. Large/invalid images get no preview. The CLI does not open the file or call the TV.

## Release gates before integration

- Prove actual source behavior (Spotify, browser, another player) on owner's PC, including pause/resume, source switch, and missing cover; never assume source can provide thumbnail.
- The media probe stays independent of live V0.1 metric worker. The running tray must continue sending numeric telemetry whether GSMTC fails, times out or returns NO_SESSION. Integrate into tray only after actual owner media-source results, optional opt-in, timeout/stop, and silent/privacy UX are reviewed.
- No V0.1 source worktree mutation; no automatic app installation, auto-login changes, secrets or firmware changes from this separate branch. CI runs pure mocked fixtures on Linux/Windows and projection import smoke on Windows; CI cannot prove owner's actual media session.
