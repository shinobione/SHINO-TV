# SHINO // TV — Native UI V2 / 240×240 contract

**Status:** V2 implemented on stacked source branch `feature/native-ui-v2-four-cards`; PC/browser and native C++ calculations are exercised by offline tests. Physical ESP8266 LCD, Wi-Fi and OEM first-flash behavior are NOT validated. No physical device touched. Derived from owner's four-card screenshot (CPU usage, GPU usage, RAM in use, GPU temperature), and their requirement for uniform dynamically colored progress bars. This document does not enable OTA, FS/EEPROM writes or first hardware flash.

## Canvas, layout, reading order

A single fixed 240×240 native LCD scene, NOT a shrunk desktop page, no carousel/no scene changes; four visible measurements all the time. Origin is top-left; rects below are `x,y,width,height`, in physical pixels:

| Metric | Card rectangle | Label | Value text origin | Progress track |
|---|---|---|---|---|
| CPU usage | `8,8,108,108` | `18,19` | `18,55` | `17,99,90,6` |
| GPU usage | `124,8,108,108` | `134,19` | `134,55` | `133,99,90,6` |
| RAM in use | `8,124,108,108` | `18,135` | `18,171` | `17,215,90,6` |
| GPU / temperature | `124,124,108,108` | `134,135` / `134,146` | `134,171` | `133,215,90,6` |

Outer margin = 8px, horizontal/vertical gap = 8px, card radius = 12px, border = 1px, label inset = 10px, track left inset = 9px, track width = 90px, track height = 6px. Last card label intentionally wraps into two lines. Don't add a permanent global header: it would steal four-card legibility.

**Font constraint:** existing Arduino_GFX built-in font is normally a 6×8 bitmap cell times integral text size. Label at size 1 (6×8px); value at size 2 (12×16px). Values `100.0%` (6 glyphs, 72px) and `11.2 GB` (7 glyphs, 84px) fit the 90px inner width at size 2. Do NOT blindly use font size 3 (18px per glyph => clipped values). Use a small custom degree ring before `C` when the underlying bitmap font lacks a reliable `°` glyph; do not allow UTF-8 degree bytes to corrupt native cursor width. Browser may use a proportional font but must maintain same visual rectangle geometry at the 240px viewport.

## Locked palette

| Surface or band | sRGB hex |
|---|---|
| Canvas | `#101318` |
| Card | `#222933` |
| Border | `#394755` |
| Label | `#BFC9D4` |
| Value | `#F6F3EF` (all four fixed, never hard-coded type colors) |
| Inactive bar track | `#536277` |
| 0 ≤ p < 20 | mint green `#66D39A` |
| 20 ≤ p < 50 | yellow `#D8C35E` |
| 50 ≤ p < 80 | dark orange `#D9894A` |
| 80 ≤ p ≤ 100 | burgundy `#8E394B` |

Color changes **only the bar fill**. Fixed card/label/value colors improve tiny-display readability. For native LCD convert hex 24-bit sRGB to 16-bit RGB565 with `(r>>3)<<11 | (g>>2)<<5 | (b>>3)`, matching Arduino_GFX's color format. Neither bars nor displayed values imply hardware thermal protection or guaranteed alarm thresholds.

## Four data values and visual fill

These are distinct: the main number is the actual engineering measurement, whereas the bar is a normalized *display percentage*.

| Card | Main value | Fill percentage `p` | Example from screenshot |
|---|---|---|---|
| CPU usage | `cpu_usage.toFixed(1) + "%"` | Clamp original CPU usage to 0…100 | 5.0%, p=5 => mint |
| GPU usage | `gpu_usage.toFixed(1) + "%"` | Clamp GPU usage to 0…100 | 0.0%, p=0 => empty track |
| RAM in use | `memory_used_gb.toFixed(1) + " GB"` | `100 × used / total`, clamp 0…100 | 11.2 / 16 GB => p=70 => dark orange |
| GPU temperature | `gpu_temp_c.toFixed(1) + "°C"` | `100 × (tempC − 30) / (90 − 30)`, clamp 0…100 | 50.0°C => p≈33.3 => yellow |

**Input schema addition required before implementation:** current `companion/metrics_server.py` sends `memory_used_gb` but not total RAM. Add `memory_total_gb = psutil.virtual_memory().total / (1024**3)` to collected metrics, `companion/push_fsless_metrics.py`'s selected fields, firmware `FslessMetrics::Snapshot/apply/describe`, and the localhost preview. Validate finite `memory_total_gb > 0` and `0 ≤ memory_used_gb ≤ memory_total_gb`. Do not infer “16 GB” from owner PC memory, and do not silently invent 70% when total RAM is missing: display the valid used GB value and neutral/unfilled track marked unavailable until a correct denominator is supplied. Treat the new schema as a coordinated versioned protocol change.

**Thermal normalization is a UI-design convention**, not an NVIDIA thermal spec. Default visual range 30…90 °C. Under this normalization the palette transitions correspond to 42 °C / 60 °C / 78 °C. Cap at 0 for ≤30 °C and at 100 for ≥90 °C; the main number always shows true measured °C (within validated input range). Do not claim “danger” purely from a band; GPU-specific warnings, if ever requested, need separate verified thresholds.

## Bar rendering

Track always drawn at 90×6 px with round ends and #536277 background. Fill is `round(90×p/100)` clipped to [0,90]. For `p=0` fill is exactly **zero pixels**, not an artificial positive colored dot. For `0 < p` ensure at least one colored pixel for visibility. At 100, fill completely covers the track. Native rounded geometry can use `fillRoundRect` with radius 3 and avoid temporarily creating a giant 240×240 frame buffer on RAM-limited ESP8266. The existing `DisplayManager::drawLoadingBar` is horizontally centered across the *entire screen* and therefore MUST NOT be reused for the 90px tracks. Add a card-local drawing primitive with explicit x/y/width/height and an RGB565 bar fill.

**Browser preview correction after owner screen recording (27 September 2026):** animate neither CSS fill width nor fill color at this 240-pixel layout. The former 200 ms CSS width transition could leave a visible colored fragment when a displayed value had already reached `0.0%` and could show a distorted/rubbery rounded edge during sampling. Now update discrete integer device pixels immediately; **`p=0` makes the colored fill `display:none`**, exposing only its gray track. Fills 1–5 pixels wide use square ends to match native `fillRect`; from 6 pixels onward use the normal 3-pixel radius. This preserves the exact existing palette, ±2pp band hysteresis and 2-second data refresh, and avoids any pixel-history residue. The LCD renderer already uses discrete pixel draws, so this correction is only to the matching browser preview. A real physical display test is still outstanding.

To avoid threshold flicker, maintain previous palette band **per card** in volatile RAM. Initial valid sample uses raw `band(p)`: p<20 green, p<50 yellow, p<80 orange, otherwise burgundy. Subsequent color switches up only when crossing the next boundary +2 percentage points; switches down only below previous boundary −2 points. A sample jumping across several bands can cross successive thresholds in a loop. This **hysteresis applies only to the fill color, NOT the displayed number or fill width**. Updating readings every two seconds is enough; do not create continuous noisy flashing.

Pseudo-code, shared equivalently in native C++ and embedded browser JavaScript:

```text
thresholds = [20, 50, 80]
colors = [MINT, YELLOW, DARK_ORANGE, BURGUNDY]

band(p): return p < 20 ? 0 : p < 50 ? 1 : p < 80 ? 2 : 3
stableBand(previousOrNone, p):
    if previousOrNone is None: return band(p)
    b = previousOrNone
    while b < 3 and p >= thresholds[b] + 2: b += 1
    while b > 0 and p < thresholds[b - 1] - 2: b -= 1
    return b

clamp100(v): return max(0, min(100, v))
cpuP  = clamp100(cpu_usage)
gpuP  = clamp100(gpu_usage) if gpu_available else None
ramP  = clamp100(100 * used_gb / total_gb) if total_gb > 0 else None
tempP = clamp100(100 * (temp_c - 30) / 60) if gpu_available else None

fillWidth(p):
    if p is None or p == 0: return 0
    return max(1, min(90, round(90 * p / 100)))
```

## Status/refresh/error contract

- The companion sends a short authenticated, numeric **RAM-only** sample every two seconds; device's `FslessMetrics` flags readings stale after six seconds without an accepted valid sample. UI refresh can be rate-limited to ≤4 Hz; redraw only the changed cards/dirty regions to reduce ST7789 flicker.
- If no valid sample or all data are stale: **all four cards and labels remain**; values show `—`; bar tracks remain neutral/unfilled, with one small unobtrusive status indicator or a reserved fallback panel (do not replace the whole grid with a “PC WAITING” scene).
- If `gpu_available=false`: CPU and RAM remain visible/updated; GPU usage and GPU temperature show `—` and neutral tracks. Never show “0.0°C” to mean unavailable.
- If RAM total is unavailable but used GB is valid: keep used-GB number and neutral RAM track, no assumed denominator.
- 0.0% is a real zero: no colored fill. At each rounded boundary, avoid oscillation through the ±2 pp color hysteresis. If the sample becomes invalid/stale, reset each card's previous hysteresis state so the next healthy first sample starts at its direct band.
- **No second dashboard scene, scrolling metrics, additional permanent header, storage writes or arbitrary uploads.** The browser viewport at 240×240 should mirror the native grid; its wider Windows window can center a 240px square and optionally show diagnostics outside that replica, without changing the LCD contract.

## Implementation checkpoints and fixtures

1. Update PC sampler, push sender, firmware validation and JS preview **together** to include actual `memory_total_gb`; add tests for missing/zero denominator, stale GPU and `used>total`.
2. Add shared constants or explicit unit fixtures for `p∈{0,5,19.9,20,20.1,49.9,50,79.9,80,100}`, RAM `11.2/16=70%`, temperature `30→0,42→20,50→33.33,60→50,78→80,90→100`, and upward/downward 2pp hysteresis.
3. Implement card-local RGB565 bar renderer and on-screen bitmap text fit: `100.0%`, `11.2 GB`, `50.0°C`, `100.0°C` must remain within 90px. Render GPU temperature's degree independently when bitmap glyph support is missing.
4. Rework flash-resident `FslessWebUI::PAGE/SCRIPT` using 240px CSS-grid mirror, and native `paintNativeDashboard()` using the exact rectangles above. The existing generic full-width bar function and current wide-browser `auto-fit` grid do **not** meet this specification.
5. Verify via localhost-only preview (no TV); build default FS-less app and optional OEM-app-return variant; run exact OEM ZIP/hash, source/no-FS and image-size checks; **never equate passing tests with permission for the owner's first physical flash**.

## No hardware action

The owner's only GeekMagic SmallTV-Ultra remains stock Ultra-V9.0.44. The official manufacturer OTA ZIP is an *application-only* image, not a full flash/filesystem backup. The default SHINO FS-less build still must not mount/format LittleFS or initialize EEPROM on first boot. This design specification is not an instruction to upload any image, and a nonbooting custom app cannot be guaranteed Wi-Fi recovery without independent hardware access.
