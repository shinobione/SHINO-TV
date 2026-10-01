// SPDX-License-Identifier: GPL-3.0-or-later
#pragma once
// Pure, bounded scene/rendering policy. No Arduino, HTTP, storage or allocation.
#include <boot/DashboardV2.h>
#include <stddef.h>
#include <stdio.h>
#include <string.h>

#ifndef SHINO_ARTWORK_SCALE
#define SHINO_ARTWORK_SCALE 5
#endif
namespace ArtworkPilot {
constexpr unsigned SCALE = SHINO_ARTWORK_SCALE;
static_assert(SCALE >= 3 && SCALE <= 5, "only reviewed integer artwork scales");
constexpr int ART_SIZE = 32 * SCALE, ART_X = (240 - ART_SIZE) / 2, ART_Y = 8;
constexpr int TITLE_X = 8, TITLE_Y = 176, TEXT_WIDTH = 224, ARTIST_Y = 196;
constexpr uint16_t BG = DashboardV2::rgb565(3, 8, 20);
constexpr uint16_t CARD = DashboardV2::rgb565(16, 32, 55);
constexpr uint16_t BORDER = DashboardV2::rgb565(54, 89, 121);
constexpr uint16_t LABEL = DashboardV2::rgb565(168, 200, 243);
constexpr uint16_t WHITE = DashboardV2::rgb565(245, 249, 255);
constexpr uint16_t TRACK = DashboardV2::rgb565(51, 68, 91);
constexpr uint16_t BARS[4] = {
    DashboardV2::rgb565(102, 211, 154), DashboardV2::rgb565(245, 211, 78),
    DashboardV2::rgb565(201, 103, 36), DashboardV2::rgb565(142, 57, 75)
};
enum class State : uint8_t { Playing, Paused, Stopped, NoSession, Unavailable };
enum class Scene : uint8_t { Idle, Playing, Paused, NoArtwork, Offline };
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
// Every valid native title/artist has at most 60 codepoints. Preserve all of
// them for scrolling; transliterate common Latin accents, '?' for other glyphs.
// Also bounded for malformed host input: no read past the supplied byte extent.
template<size_t N> inline void captionText(char (&out)[N], const char* in, size_t bytes) {
    size_t at = 0, n = 0;
    if (bytes > 512) bytes = 512;
    while (in && at < bytes && n < N - 1) {
        uint32_t cp = uint8_t(in[at++]);
        unsigned more = 0;
        if (cp >= 0xc2 && cp <= 0xdf) { more = 1; cp &= 31; }
        else if (cp >= 0xe0 && cp <= 0xef) { more = 2; cp &= 15; }
        else if (cp >= 0xf0 && cp <= 0xf4) { more = 3; cp &= 7; }
        else if (cp >= 0x80) cp = '?';
        if (more) {
            if (more > bytes - at) { out[n++] = '?'; break; }
            bool valid = true;
            for (unsigned i = 0; i < more; ++i) {
                const uint8_t b = uint8_t(in[at]);
                if ((b & 0xc0) != 0x80) { valid = false; break; }
                ++at; cp = (cp << 6) | (b & 63);
            }
            if (!valid) cp = '?';
        }
        char ch = '?';
        if (cp >= 32 && cp < 127) ch = char(cp);
        else if (cp >= 0xc0 && cp <= 0xc5) ch = 'A';
        else if (cp >= 0xe0 && cp <= 0xe5) ch = 'a';
        else if (cp == 0xc7 || cp == 0xe7) ch = cp == 0xc7 ? 'C' : 'c';
        else if (cp >= 0xc8 && cp <= 0xcb) ch = 'E';
        else if (cp >= 0xe8 && cp <= 0xeb) ch = 'e';
        else if (cp >= 0xcc && cp <= 0xcf) ch = 'I';
        else if (cp >= 0xec && cp <= 0xef) ch = 'i';
        else if (cp == 0xd1 || cp == 0xf1) ch = cp == 0xd1 ? 'N' : 'n';
        else if (cp >= 0xd2 && cp <= 0xd6) ch = 'O';
        else if (cp >= 0xf2 && cp <= 0xf6) ch = 'o';
        else if (cp >= 0xd9 && cp <= 0xdc) ch = 'U';
        else if (cp >= 0xf9 && cp <= 0xfc) ch = 'u';
        out[n++] = ch;
    }
    out[n] = 0;
}
struct Caption {
    char title[61] = {}, artist[61] = {};
    uint8_t trackKey[32] = {};
    State state = State::NoSession;
    bool positionValid = false, durationValid = false;
    uint32_t position = 0, duration = 0;
};
enum class Cover : uint8_t { None, Image32, Missing, Unsupported, Invalid };
// Borrow expires when step returns. Native sink alone supplies committed image
// ownership. Authenticated Begin metadata may be presented without an image.
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
// Local civil time from an eventual trustworthy provider; validity and lease
// are mandatory. A valid lease can keep ticking while PC telemetry disconnects.
// No network provider is installed by this pilot. Synthetic is preview-only.
struct ClockData {
    uint32_t observedMs = 0, validForMs = 0;
    uint16_t year = 0;
    uint8_t month = 0, day = 0, hour = 0, minute = 0, second = 0;
    bool valid = false, synthetic = false;
};
struct WeatherData {
    char place[17] = {}, condition[17] = {};
    uint32_t observedMs = 0, validForMs = 0;
    int16_t tenthsC = 0;
    bool valid = false, synthetic = false;
};
struct Policy {
    // Zero means retain PAUSED indefinitely. Owner's final timeout is open.
    uint32_t pausedToIdleMs = 0;
    uint16_t stoppedDebounceMs = 300;
};
struct Marquee {
    static constexpr uint32_t INITIAL_MS = 1500, END_MS = 900, PIXEL_MS = 80;
    uint32_t started = 0;
    void reset(uint32_t now) { started = now; }
    uint16_t offset(uint32_t now, unsigned pixels, unsigned width = TEXT_WIDTH) const {
        if (pixels <= width) return 0;
        const uint32_t distance = pixels - width, travel = distance * PIXEL_MS;
        const uint32_t phase = uint32_t(now - started) % (INITIAL_MS + 2 * travel + END_MS);
        if (phase < INITIAL_MS) return 0;
        if (phase < INITIAL_MS + travel) return uint16_t((phase - INITIAL_MS) / PIXEL_MS);
        if (phase < INITIAL_MS + travel + END_MS) return uint16_t(distance);
        return uint16_t(distance - (phase - INITIAL_MS - travel - END_MS) / PIXEL_MS);
    }
};
class Canvas {
public:
    virtual ~Canvas() = default;
    virtual void fill(int x, int y, int w, int h, uint16_t color) = 0;
    virtual void text(int x, int y, const char* s, uint16_t color, uint8_t size = 1) = 0;
    virtual uint8_t glyphColumn(uint8_t ascii, unsigned column) = 0;
    // Native RGB565 words -> pinned driver sends MSB first. Never cast LE bytes.
    virtual void row(int x, int y, uint16_t* pixels, int count, int repeats) = 0;
};
class Renderer {
    struct Card { char number[16] = {}, total[12] = {}; uint8_t pixels = 0; int8_t band = -1; };
    Card cards[4];
    // One row shared ONLY by cooperative artwork/text tasks, never HTTP/crypto.
    // 224 words suffice for a text viewport and every supported artwork scale.
    uint16_t scanline[TEXT_WIDTH] = {};
    Caption caption;
    ClockData clock;
    WeatherData weather;
    Policy policy;
    Marquee titleMotion, artistMotion;
    uint32_t revision = 0, stateSince = 0, clockMinute = 0, weatherMinute = 0;
    Cover cover = Cover::None;
    Scene scene = Scene::Offline;
    State observedState = State::NoSession;
    uint16_t titleOffset = 0, artistOffset = 0;
    uint8_t clearY = 0, headerTask = 0, artRow = 32, titleRow = 8, artistRow = 8, dirty = 15;
    bool seen = false, clearing = true, headerDirty = true, decorationDirty = false;
    bool statusDirty = false, progressDirty = false, stale = true;
    bool pauseExpired = false;
    bool clockWasFresh = false, weatherWasFresh = false;
    static bool idleScene(Scene s) { return s == Scene::Idle || s == Scene::Offline; }
    static unsigned monthDays(unsigned year, unsigned month) {
        static const uint8_t days[] = {31,28,31,30,31,30,31,31,30,31,30,31};
        if (month < 1 || month > 12) return 0;
        return days[month-1] + (month == 2 && year % 4 == 0 && (year % 100 || year % 400 == 0));
    }
    bool clockFresh(uint32_t now) const {
        return clock.valid && clock.validForMs && clock.validForMs <= 86400000 &&
            uint32_t(now - clock.observedMs) <= clock.validForMs &&
            clock.year >= 2000 && clock.year <= 2199 && clock.day >= 1 &&
            clock.day <= monthDays(clock.year, clock.month) && clock.hour < 24 &&
            clock.minute < 60 && clock.second < 60;
    }
    bool weatherFresh(uint32_t now) const {
        return weather.valid && weather.validForMs && weather.validForMs <= 86400000 &&
            uint32_t(now - weather.observedMs) <= weather.validForMs &&
            weather.tenthsC >= -1000 && weather.tenthsC <= 1000;
    }
    Scene targetScene(uint32_t now) const {
        const bool image = cover == Cover::Image32;
        if (caption.state == State::Playing) return image ? Scene::Playing : Scene::NoArtwork;
        if (caption.state == State::Paused &&
            !pauseExpired)
            return image ? Scene::Paused : Scene::NoArtwork;
        if (caption.state == State::Stopped && !idleScene(scene) &&
            uint32_t(now - stateSince) < policy.stoppedDebounceMs)
            return image ? Scene::Playing : Scene::NoArtwork;
        return stale && !clockFresh(now) ? Scene::Offline : Scene::Idle;
    }
    void sync(const View& v, uint32_t now) {
        const Cover nextCover = v.cover == Cover::Image32 && !v.data ? Cover::Invalid : v.cover;
        if (!seen || revision != v.revision || cover != nextCover) {
            const Caption* next = v.caption;
            const State nextState = next ? next->state : State::NoSession;
            const bool trackChanged = !next || memcmp(caption.trackKey, next->trackKey, 32) ||
                strcmp(caption.title, next->title) || strcmp(caption.artist, next->artist);
            if (!seen || nextState != observedState) {
                stateSince = now; observedState = nextState; pauseExpired = false;
            }
            if (trackChanged || !seen) {
                titleMotion.reset(now); artistMotion.reset(now);
                titleOffset = artistOffset = 0;
            }
            if (trackChanged || caption.state != nextState) titleRow = artistRow = 0;
            progressDirty = statusDirty = true;
            if (next) caption = *next;
            else {
                // Reset owned scalar/array fields directly, avoiding a second
                // full Caption temporary on the small continuation stack.
                memset(&caption,0,sizeof caption); caption.state = State::NoSession;
            }
            revision = v.revision; cover = nextCover; seen = true;
            artRow = 0; decorationDirty = true;
        }
        if (caption.state == State::Paused && policy.pausedToIdleMs &&
            uint32_t(now-stateSince) >= policy.pausedToIdleMs) pauseExpired = true;
        const Scene nextScene = targetScene(now);
        if (nextScene != scene) {
            if (idleScene(nextScene) != idleScene(scene)) { clearing = true; clearY = 0; }
            scene = nextScene; headerDirty = true; headerTask = 0; dirty = 15;
            titleMotion.reset(now); artistMotion.reset(now); titleOffset = artistOffset = 0;
            titleRow = artistRow = 0; artRow = 0; decorationDirty = true;
            statusDirty = progressDirty = true;
        }
        const bool cf = clockFresh(now), wf = weatherFresh(now);
        const uint32_t minute = cf ? (clock.hour * 3600U + clock.minute * 60U + clock.second +
                                    uint32_t(now-clock.observedMs) / 1000) / 60 : 0;
        const uint32_t weatherAge = wf ? uint32_t(now-weather.observedMs)/60000 : 0;
        if (cf != clockWasFresh || wf != weatherWasFresh || minute != clockMinute || weatherAge != weatherMinute) {
            headerDirty = true; headerTask = 0;
            clockWasFresh = cf; weatherWasFresh = wf; clockMinute = minute; weatherMinute = weatherAge;
        }
    }
    void paintCard(Canvas& c, unsigned i) {
        const int x = i % 2 ? 122 : 8, y = i < 2 ? 124 : 181;
        c.fill(x, y, 110, 50, CARD);
        c.fill(x, y, 110, 1, BORDER); c.fill(x, y+49, 110, 1, BORDER);
        c.fill(x, y+1, 1, 48, BORDER); c.fill(x+109, y+1, 1, 48, BORDER);
        const char* labels[] = {"CPU", "GPU", "RAM", "GPU TEMP"};
        c.text(x+6, y+6, labels[i], LABEL);
        if (cards[i].total[0]) c.text(x+104-int(strlen(cards[i].total))*6, y+6, cards[i].total, LABEL);
        c.text(x+6, y+19, cards[i].number[0] ? cards[i].number : "--", WHITE,
               strlen(cards[i].number)*12 <= 98 ? 2 : 1);
        c.fill(x+6, y+40, 98, 4, TRACK);
        if (cards[i].pixels && cards[i].band >= 0)
            c.fill(x+6, y+40, cards[i].pixels, 4, BARS[cards[i].band]);
    }
    void paintHeader(Canvas& c, uint32_t now) {
        // Each background stripe or text item is its own cooperative task.
        if (headerTask < 14) {
            const int y = 4+headerTask*8;
            c.fill(4, y, 232, headerTask == 13 ? 9 : 8,
                   DashboardV2::rgb565(8+headerTask, 22, 40+headerTask*3));
        } else if (headerTask == 14) {
            c.text(8, 12, (clock.synthetic || weather.synthetic) ? "SYNTHETIC PREVIEW DATA" :
                   scene == Scene::Offline ? "PC OFFLINE" : "SHINO // TV", LABEL);
        } else if (headerTask == 15 || headerTask == 16) {
            if (clockFresh(now)) {
                unsigned year = clock.year, month = clock.month, day = clock.day;
                const uint32_t seconds = clock.hour*3600U + clock.minute*60U + clock.second +
                                         uint32_t(now-clock.observedMs)/1000;
                if (seconds >= 86400 && ++day > monthDays(year,month)) {
                    day = 1; if (++month > 12) { month = 1; ++year; }
                }
                char value[20];
                if (headerTask == 15) {
                    snprintf(value, sizeof value, "%02u:%02u", (unsigned)(seconds/3600)%24,
                             (unsigned)(seconds/60)%60); c.text(8, 35, value, WHITE, 4);
                } else {
                    snprintf(value, sizeof value, "%02u/%02u/%04u", day, month, year);
                    c.text(8, 79, value, LABEL);
                }
            } else if (headerTask == 15) c.text(8, 39,
                scene == Scene::Offline ? "WAITING FOR PC" : "TIME NOT SYNCED", WHITE, 2);
            else c.text(8, 79, clock.valid ? "CLOCK STALE / INVALID" : "DATE UNAVAILABLE", LABEL);
        } else {
            char value[38];
            if (weatherFresh(now)) {
                // Integer tenths, including -0.1C; never a fictitious weather value.
                const int magnitude = weather.tenthsC < 0 ? -weather.tenthsC : weather.tenthsC;
                snprintf(value, sizeof value, "%s%d.%d C | %.16s", weather.tenthsC < 0 ? "-" : "",
                         magnitude/10, magnitude%10, weather.place);
                c.text(8, 97, value, LABEL);
                if (weather.condition[0]) c.text(8,109,weather.condition,LABEL);
                char age[12];snprintf(age,sizeof age,"%lum old",(unsigned long)(uint32_t(now-weather.observedMs)/60000));
                c.text(232-int(strlen(age))*6,109,age,LABEL);
            } else c.text(8, 97, weather.valid ? "WEATHER STALE / INVALID" : "WEATHER UNAVAILABLE", LABEL);
            headerDirty = false;
        }
        ++headerTask;
    }
    void textRow(Canvas& c, const char* s, uint8_t size, uint16_t offset,
                 uint8_t sourceRow, int y, uint16_t color) {
        const unsigned length = unsigned(strlen(s)), cell = 6U*size;
        for (unsigned x=0; x<TEXT_WIDTH; ++x) {
            const unsigned pos = x+offset, index = pos/cell, column = (pos%cell)/size;
            const bool ink = index < length && column < 5 &&
                (c.glyphColumn(uint8_t(s[index]), column) & (1U << sourceRow));
            scanline[x] = ink ? color : BG;
        }
        // Strict viewport: even a fractional glyph cannot touch another region.
        c.row(TITLE_X, y+sourceRow*size, scanline, TEXT_WIDTH, size);
    }
    static void timeText(char* out, size_t n, uint32_t seconds) {
        if (seconds >= 3600) snprintf(out,n,"%lu:%02lu:%02lu", (unsigned long)(seconds/3600),
            (unsigned long)((seconds/60)%60), (unsigned long)(seconds%60));
        else snprintf(out,n,"%lu:%02lu", (unsigned long)(seconds/60), (unsigned long)(seconds%60));
    }
    void paintProgress(Canvas& c) {
        c.fill(8, 222, 224, 4, TRACK); c.fill(8, 230, 224, 8, BG);
        const bool valid = caption.positionValid && caption.durationValid &&
            caption.duration > 0 && caption.position <= caption.duration;
        if (valid) {
            const unsigned filled = (caption.position*224U+caption.duration/2)/caption.duration;
            if (filled) c.fill(8,222,int(filled),4, BARS[0]);
            char value[16]; timeText(value,sizeof value,caption.position); c.text(8,230,value,LABEL);
            timeText(value,sizeof value,caption.duration); c.text(232-int(strlen(value))*6,230,value,LABEL);
        } else { c.text(8,230,"--:--",LABEL); c.text(202,230,"--:--",LABEL); }
    }
public:
    Scene currentScene() const { return scene; }
    bool telemetryStale() const { return stale; }
    uint16_t currentTitleOffset() const { return titleOffset; }
    uint16_t currentArtistOffset() const { return artistOffset; }
    void setPolicy(Policy p) {
        if (p.stoppedDebounceMs > 2000) p.stoppedDebounceMs = 2000;
        if (p.pausedToIdleMs >= 0x80000000U) p.pausedToIdleMs = 0;
        policy = p; pauseExpired = false;
    }
    void setClock(const ClockData& value) { clock = value; headerDirty = true; headerTask = 0; }
    void setWeather(const WeatherData& value) {
        weather = value; weather.place[16] = weather.condition[16] = 0;
        // Provider labels are bounded ASCII; this seam has no network authority.
        char* labels[] = {weather.place, weather.condition};
        for (char* text : labels)
            for (unsigned i=0;i<16;++i) if (uint8_t(text[i]) < 32 || uint8_t(text[i]) > 126) {
                if (!text[i]) break;
                text[i] = '?';
            }
        headerDirty = true; headerTask = 0;
    }
    void setMetrics(const Metrics& m) {
        if (stale != m.stale) { headerDirty = true; headerTask = 0; }
        stale = m.stale;
        for (unsigned i=0;i<4;++i) {
            Card next; float p = -1;
            if (!m.stale && (i == 0 || i == 2 || m.gpuAvailable)) {
                if (i < 2) {
                    const float value = i ? m.gpu : m.cpu;
                    snprintf(next.number,sizeof next.number,"%.1f%%",value);
                    p = DashboardV2::clamp100(value);
                } else if (i == 2) {
                    snprintf(next.number,sizeof next.number,"%.1f GB",m.ramGb);
                    p = DashboardV2::ramPercent(m.ramGb,m.ramTotalGb);
                    if (p >= 0) snprintf(next.total,sizeof next.total,"/%.1f GB",m.ramTotalGb);
                } else snprintf(next.number,sizeof next.number,"%.1f C",m.gpuTempC);
                // Temperature has no approved normalization: neutral track only.
            }
            next.band = DashboardV2::stableBand(cards[i].band,p);
            next.pixels = p <= 0 ? 0 : uint8_t(DashboardV2::clamp100(p)*98/100+0.5F);
            if (strcmp(next.number,cards[i].number) || strcmp(next.total,cards[i].total) ||
                next.band != cards[i].band || next.pixels != cards[i].pixels) dirty |= uint8_t(1U<<i);
            cards[i] = next;
        }
    }
    // Exactly one task after the HTTP owner returns. No image pointer persists;
    // a source row is copied before GFX can yield to SDK (which does not reenter
    // the serialized HTTP/receiver owner). No render allocation or framebuffer.
    bool step(Canvas& c, const View& v, uint32_t now) {
        sync(v,now);
        if (clearing) {
            c.fill(0,clearY,240,8,BG); clearY += 8;
            if (clearY == 240) clearing = false;
            return true;
        }
        if (idleScene(scene)) {
            if (headerDirty) { paintHeader(c,now); return true; }
            for (unsigned i=0;i<4;++i) if (dirty & (1U<<i)) {
                paintCard(c,i); dirty &= uint8_t(~(1U<<i)); return true;
            }
            return false;
        }
        if (artRow < 32) {
            if (cover == Cover::Image32 && v.data) {
                for (unsigned sx=0;sx<32;++sx) {
                    const unsigned at = (artRow*32+sx)*2;
                    const uint16_t pixel = uint16_t(v.data[at]) | (uint16_t(v.data[at+1])<<8);
                    for (unsigned r=0;r<SCALE;++r) scanline[sx*SCALE+r] = pixel;
                }
                c.row(ART_X,ART_Y+artRow*SCALE,scanline,ART_SIZE,SCALE);
            } else c.fill(ART_X,ART_Y+artRow*SCALE,ART_SIZE,SCALE,CARD);
            ++artRow; return true;
        }
        if (decorationDirty) {
            if (cover != Cover::Image32) {
                c.fill(ART_X+ART_SIZE/2-10,ART_Y+ART_SIZE/2-22,4,28,LABEL);
                c.fill(ART_X+ART_SIZE/2-10,ART_Y+ART_SIZE/2-22,20,4,LABEL);
                c.fill(ART_X+ART_SIZE/2+6,ART_Y+ART_SIZE/2-22,4,24,LABEL);
                const char* label = cover == Cover::Invalid ? "INVALID COVER" :
                    cover == Cover::Unsupported ? "32px PILOT" : "NO ARTWORK";
                c.text((240-int(strlen(label))*6)/2,ART_Y+ART_SIZE/2+22,label,LABEL);
            }
            decorationDirty = false; return true;
        }
        const char* title = caption.title[0] ? caption.title : "Unknown track";
        const char* artist = caption.artist[0] ? caption.artist : "Unknown artist";
        // Finish both fixed sweeps and status/progress before scheduling more
        // motion. Even slow loop iterations cannot starve artist or status.
        if (titleRow < 8) { textRow(c,title,2,titleOffset,titleRow++,TITLE_Y,WHITE); return true; }
        if (artistRow < 8) { textRow(c,artist,1,artistOffset,artistRow++,ARTIST_Y,LABEL); return true; }
        if (statusDirty) {
            c.fill(8,210,224,8,BG); c.text(8,210,stateText(caption.state),
                caption.state == State::Paused ? BARS[1] : BARS[0]);
            c.text(184,210,"REPORTED",LABEL); statusDirty = false; return true;
        }
        if (progressDirty) { paintProgress(c); progressDirty = false; return true; }
        // A sweep's eight source rows use one offset to avoid vertical tearing.
        const uint16_t nextTitle = titleMotion.offset(now,unsigned(strlen(title))*12);
        const uint16_t nextArtist = artistMotion.offset(now,unsigned(strlen(artist))*6);
        if (nextTitle != titleOffset) { titleOffset = nextTitle; titleRow = 0; }
        if (nextArtist != artistOffset) { artistOffset = nextArtist; artistRow = 0; }
        if (titleRow < 8) { textRow(c,title,2,titleOffset,titleRow++,TITLE_Y,WHITE); return true; }
        if (artistRow < 8) { textRow(c,artist,1,artistOffset,artistRow++,ARTIST_Y,LABEL); return true; }
        return false;
    }
};
} // namespace ArtworkPilot
