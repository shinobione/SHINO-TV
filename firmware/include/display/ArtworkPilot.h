// SPDX-License-Identifier: GPL-3.0-or-later
#pragma once
// Offline-first 32px pilot. No Arduino, authentication, storage or allocation.
#include <boot/DashboardV2.h>
#include <stddef.h>
#include <stdio.h>
#include <string.h>

namespace ArtworkPilot {
enum class State : uint8_t { Playing, Paused, Stopped, NoSession, Unavailable };
inline State stateFrom(const char* s) {
    if (!strcmp(s, "PLAYING")) return State::Playing;
    if (!strcmp(s, "PAUSED")) return State::Paused;
    if (!strcmp(s, "STOPPED")) return State::Stopped;
    if (!strcmp(s, "NO_SESSION")) return State::NoSession;
    return State::Unavailable;
}
inline const char* stateText(State s) {
    switch (s) {
    case State::Playing: return "PLAYING";
    case State::Paused: return "PAUSED";
    case State::Stopped: return "STOPPED";
    case State::NoSession: return "NO SESSION";
    default: return "UNAVAILABLE";
    }
}
// Input has already passed native UTF-8/metadata validation. Classic GFX's
// ASCII font cannot render UTF-8; one '?' replaces each unsupported codepoint.
// Fixed 20-column lines end in '...' when the entire caption exceeds capacity.
template<size_t N> inline void captionText(char (&out)[N], const char* in) {
    size_t n = 0;
    while (*in && n < N - 1) {
        const uint8_t c = uint8_t(*in++);
        if (c < 0x80) out[n++] = (c >= 32 && c < 127) ? char(c) : '?';
        else {
            out[n++] = '?';
            while ((uint8_t(*in) & 0xc0) == 0x80) ++in;
        }
    }
    if (*in && n >= 3) memcpy(out + n - 3, "...", 3);
    out[n] = 0;
}
struct Caption {
    char title[55] = {};
    char artist[41] = {};
    State state = State::NoSession;
};
enum class Cover : uint8_t { None, Image32, Missing, Unsupported, Invalid };
// A borrowed view expires when step() returns. Never retain its data/caption.
// Only DisplaySink constructs the native view; staging is never exposed here.
struct View {
    const uint8_t* data = nullptr;
    const Caption* caption = nullptr;
    uint32_t revision = 0;
    Cover cover = Cover::None;
};
inline View committedView(const uint8_t* data, size_t bytes, const Caption& caption,
                          bool committed, uint32_t revision) {
    View v{nullptr, committed ? &caption : nullptr, revision, Cover::None};
    if (!committed) return v;
    if (!data && !bytes) v.cover = Cover::Missing;
    else if (!data || (bytes != 2048 && bytes != 4608)) v.cover = Cover::Invalid;
    else if (bytes == 4608) v.cover = Cover::Unsupported;
    else { v.cover = Cover::Image32; v.data = data; }
    return v;
}
struct Metrics {
    float cpu = 0, gpu = 0, ramGb = 0, ramTotalGb = 0, gpuTempC = 0;
    bool gpuAvailable = false, stale = true;
};
class Canvas {
public:
    virtual ~Canvas() = default;
    virtual void fill(int x, int y, int w, int h, uint16_t color) = 0;
    virtual void text(int x, int y, const char* s, uint16_t color, uint8_t size = 1) = 0;
    // Values are native uint16_t RGB565, not a cast of wire-format bytes.
    virtual void row(int x, int y, uint16_t* pixels, int count, int repeats) = 0;
};
class Renderer {
    struct Card { char number[16] = {}; uint8_t pixels = 0; int8_t band = -1; };
    Card cards[4];
    uint16_t scanline[96] = {}; // owned renderer scratch, never crypto/staging
    uint32_t revision = 0;
    Cover cover = Cover::None;
    uint8_t clearY = 0, topY = 0, captionLine = 0, artRow = 0, dirty = 15;
    bool initialized = false, seen = false;
    static void line(Canvas& c, int y, const char* text, unsigned index,
                     uint16_t color) {
        char part[21] = {};
        const size_t offset = index * 20, length = strlen(text);
        if (offset < length) {
            size_t count = length - offset;
            if (count > 20) count = 20;
            memcpy(part, text + offset, count);
        }
        c.text(112, y, part, color);
    }
    void paintCard(Canvas& c, unsigned i) {
        const int x = i % 2 ? 124 : 8, y = i < 2 ? 120 : 178;
        c.fill(x, y, 108, 1, DashboardV2::BORDER);
        c.fill(x, y + 53, 108, 1, DashboardV2::BORDER);
        c.fill(x, y + 1, 1, 52, DashboardV2::BORDER);
        c.fill(x + 107, y + 1, 1, 52, DashboardV2::BORDER);
        c.fill(x + 1, y + 1, 106, 52, DashboardV2::CARD);
        const char* labels[] = {"CPU", "GPU", "RAM", "GPU TEMP"};
        c.text(x + 9, y + 7, labels[i], DashboardV2::LABEL);
        if (cards[i].number[0]) c.text(x + 9, y + 21, cards[i].number, DashboardV2::VALUE,
                                      strlen(cards[i].number) * 12 <= 90 ? 2 : 1);
        else c.fill(x + 9, y + 27, 12, 2, DashboardV2::VALUE);
        c.fill(x + 9, y + 43, 90, 4, DashboardV2::TRACK);
        if (cards[i].pixels && cards[i].band >= 0)
            c.fill(x + 9, y + 43, cards[i].pixels, 4, DashboardV2::PALETTE[cards[i].band]);
    }
public:
    void setMetrics(const Metrics& m) {
        for (unsigned i = 0; i < 4; ++i) {
            Card next;
            float p = -1;
            if (!m.stale && (i == 0 || i == 2 || m.gpuAvailable)) {
                if (i == 0 || i == 1) {
                    const float v = i ? m.gpu : m.cpu;
                    snprintf(next.number, sizeof next.number, "%.1f%%", v);
                    p = DashboardV2::clamp100(v);
                } else if (i == 2) {
                    snprintf(next.number, sizeof next.number, "%.1f GB", m.ramGb);
                    p = DashboardV2::ramPercent(m.ramGb, m.ramTotalGb);
                } else {
                    snprintf(next.number, sizeof next.number, "%.1f C", m.gpuTempC);
                    p = DashboardV2::tempPercent(m.gpuTempC);
                }
            }
            next.band = DashboardV2::stableBand(cards[i].band, p);
            next.pixels = DashboardV2::fillPixels(p);
            if (strcmp(next.number, cards[i].number) || next.band != cards[i].band ||
                next.pixels != cards[i].pixels) dirty |= uint8_t(1U << i);
            cards[i] = next;
        }
    }
    // One fixed task per loop: 8px background stripe, one compact metric card,
    // one caption line, or one 32px source row enlarged to three LCD rows.
    // No HTTP service callbacks during a borrow. GFX may yield to the SDK;
    // receiver ownership is changed only by the serialized main-loop owner.
    // Each source row/caption line is copied before calling the LCD driver.
    // No allocation or image cache.
    bool step(Canvas& c, const View& v) {
        if (!initialized) {
            c.fill(0, clearY, 240, 8, DashboardV2::BACKGROUND);
            clearY += 8;
            if (clearY == 240) initialized = true;
            return true;
        }
        if (!seen || revision != v.revision || cover != v.cover) {
            revision = v.revision; cover = v.cover; seen = true;
            topY = captionLine = artRow = 0;
        }
        // Telemetry takes priority without delaying it for a complete cover.
        for (unsigned i = 0; i < 4; ++i) if (dirty & (1U << i)) {
            paintCard(c, i); dirty &= uint8_t(~(1U << i)); return true;
        }
        if (topY < 112) {
            c.fill(0, topY, 240, 8, DashboardV2::BACKGROUND);
            topY += 8; return true;
        }
        if (captionLine < 7) {
            const Caption* caption = v.caption;
            if (captionLine == 0) c.text(112, 8, "NOW PLAYING", DashboardV2::LABEL);
            else if (captionLine <= 3) {
                const char* title = caption && caption->title[0] ? caption->title : "No track";
                line(c, 28 + (captionLine - 1) * 12, title, captionLine - 1, DashboardV2::VALUE);
            } else if (captionLine <= 5) {
                const char* artist = caption && caption->artist[0] ? caption->artist : "Unknown artist";
                line(c, 70 + (captionLine - 4) * 12, artist, captionLine - 4, DashboardV2::LABEL);
            } else {
                const State state = caption ? caption->state : State::NoSession;
                c.text(112, 96, stateText(state),
                       state == State::Playing ? DashboardV2::PALETTE[0] : DashboardV2::LABEL);
            }
            ++captionLine; return true;
        }
        if (artRow < 32) {
            if (v.cover == Cover::Image32 && v.data) {
                for (unsigned sx = 0; sx < 32; ++sx) {
                    const unsigned at = (artRow * 32 + sx) * 2;
                    const uint16_t pixel = uint16_t(v.data[at]) | (uint16_t(v.data[at + 1]) << 8);
                    scanline[sx * 3] = scanline[sx * 3 + 1] = scanline[sx * 3 + 2] = pixel;
                }
                c.row(8, 8 + artRow * 3, scanline, 96, 3);
                ++artRow;
            } else {
                c.fill(8, 8, 96, 96, DashboardV2::CARD);
                const char* label = v.cover == Cover::Invalid ? "INVALID COVER" :
                    v.cover == Cover::Unsupported ? "32px PILOT" : "NO ARTWORK";
                c.text(8 + (96 - int(strlen(label)) * 6) / 2, 52, label, DashboardV2::LABEL);
                artRow = 32;
            }
            return true;
        }
        return false;
    }
};
} // namespace ArtworkPilot
