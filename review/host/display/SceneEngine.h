// SPDX-License-Identifier: GPL-3.0-or-later
#pragma once
// Pure, bounded scene/rendering policy. No Arduino, HTTP, storage or allocation.
#include <boot/DashboardV2.h>
#include "B53Layout.h"
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
enum class ClockSource : uint8_t { Unknown, PairedPc, Sntp };
struct ClockData {
    uint32_t observedMs = 0, validForMs = 0;
    uint16_t year = 0;
    uint8_t month = 0, day = 0, hour = 0, minute = 0, second = 0;
    bool valid = false, synthetic = false;
    ClockSource source = ClockSource::Unknown;
    int16_t utcOffsetMinutes = 0;
    uint32_t syncedMs = 0;
};
struct WeatherData {
    uint8_t wmoCode = 255; // Unknown until a verified provider supplies it.
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
    uint32_t revision = 0, stateSince = 0, clockMinute = 0, weatherMinute = 0, clockAgeMinute = 0;
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
                memset(static_cast<void*>(&caption),0,sizeof caption); caption.state = State::NoSession;
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
        const uint32_t clockAge = cf && clock.source == ClockSource::PairedPc ? uint32_t(now-clock.syncedMs)/60000 : 0;
        if (cf != clockWasFresh || wf != weatherWasFresh || minute != clockMinute || weatherAge != weatherMinute || clockAge != clockAgeMinute) {
            headerDirty = true; headerTask = 0;
            clockWasFresh = cf; weatherWasFresh = wf; clockMinute = minute; weatherMinute = weatherAge;
            clockAgeMinute = clockAge;
        }
    }
    void paintCard(Canvas& c, unsigned i) {
        const auto r=B53Layout::CARDS[i];
        if(stale) {
            c.fill(r.x,r.y,r.w,r.h,BG);
            return;
        }
        c.fill(r.x,r.y,r.w,r.h,CARD);
        c.fill(r.x,r.y,r.w,1,BORDER);
        c.fill(r.x,r.y+r.h-1,r.w,1,BORDER);
        c.fill(r.x,r.y,1,r.h,BORDER);
        c.fill(r.x+r.w-1,r.y,1,r.h,BORDER);
        // Owner-approved single-line labels. 8 glyphs at 12px = 96px.
        // Both dimensions remain inside the 111px card.
        static const char* const names[]={"CPU","GPU","RAM","GPU temp"};
        c.text(r.x+7,r.y+5,names[i],LABEL,2);
        const char* value=cards[i].number[0]?cards[i].number:"--";
        // All contracted compact measurements fit at font size 3.
        // Bounds-check even for unexpected source changes.
        const uint8_t fontSize=strlen(value)*18U<=97U?3:2;
        c.text(r.x+7,r.y+25,value,WHITE,fontSize);
        c.fill(r.x+B53Layout::CARD_BAR_OFFSET_X,r.y+B53Layout::CARD_BAR_OFFSET_Y,
               B53Layout::CARD_BAR_WIDTH,B53Layout::CARD_BAR_HEIGHT,TRACK);
        if(cards[i].pixels && cards[i].band>=0)
            c.fill(r.x+B53Layout::CARD_BAR_OFFSET_X,r.y+B53Layout::CARD_BAR_OFFSET_Y,
                   cards[i].pixels,B53Layout::CARD_BAR_HEIGHT,BARS[cards[i].band]);
    }
    // Keep the sparse pointer switch in code, not a 100-entry RAM table.
#if defined(__GNUC__) && !defined(__clang__)
    __attribute__((optimize("no-tree-switch-conversion")))
#endif
    const char* weatherLabel() const {
        switch(weather.wmoCode) {
        case 0:return "Clear";case 1:return "Mostly clear";
        case 2:return "Partly cloudy";case 3:return "Cloudy";
        case 45:case 48:return "Fog";
        case 51:case 53:case 55:return "Drizzle";
        case 56:case 57:return "Icy drizzle";
        case 61:case 63:case 65:return "Rain";
        case 66:case 67:return "Freezing rain";
        case 71:case 73:case 75:return "Snow";case 77:return "Snow grains";
        case 80:case 81:case 82:return "Showers";
        case 85:case 86:return "Snow showers";
        case 95:return "Thunder";case 96:case 99:return "Thunder hail";
        default:return nullptr;
        }
    }
    void paintWeatherIcon(Canvas& c,int x,int y) {
        const unsigned code=weather.wmoCode;
        if(!weatherLabel()) { c.text(x+9,y+8,"?",LABEL,2);return; }
        const uint16_t sky=DashboardV2::rgb565(100,200,255);
        if(code<=2) {
            // Sun disc and eight short rays, all within a 32x30 box.
            for(int row=-6;row<=6;++row)
                for(int col=-6;col<=6;++col)
                    if(row*row+col*col<=36)c.fill(x+14+col,y+12+row,1,1,BARS[1]);
            c.fill(x+13,y+1,3,3,BARS[1]);c.fill(x+13,y+21,3,3,BARS[1]);
            c.fill(x+3,y+11,3,3,BARS[1]);c.fill(x+23,y+11,3,3,BARS[1]);
            c.fill(x+6,y+4,2,2,BARS[1]);c.fill(x+21,y+4,2,2,BARS[1]);
            c.fill(x+6,y+20,2,2,BARS[1]);c.fill(x+21,y+20,2,2,BARS[1]);
            if(code<2)return;
        }
        // Compact cloud silhouette for cloud/precipitation families.
        c.fill(x+3,y+12,27,8,LABEL);
        c.fill(x+7,y+8,10,6,LABEL);c.fill(x+15,y+5,10,10,LABEL);
        if(code==45 || code==48) {
            c.fill(x+1,y+23,30,2,sky);c.fill(x+5,y+28,23,2,sky);
        } else if(code>=95) {
            c.fill(x+17,y+20,5,4,BARS[1]);c.fill(x+13,y+23,6,4,BARS[1]);
            c.fill(x+11,y+26,4,4,BARS[1]);
        } else if((code>=71 && code<=77) || code==85 || code==86) {
            for(int i=0;i<3;++i) {
                c.fill(x+6+i*9,y+23,1,7,WHITE);
                c.fill(x+3+i*9,y+26,7,1,WHITE);
            }
        } else if(code>=51) {
            for(int i=0;i<3;++i)c.fill(x+6+i*9,y+23,2,6,sky);
        }
    }
    void paintHeader(Canvas& c, uint32_t now) {
        // Clear only changing regions on minute/weather updates. Full-screen
        // stripe clearing is reserved for layout/scene transitions.
        if(headerTask==0) {
            c.fill(0,0,240,24,BG);
        } else if(headerTask==1) {
            c.fill(0,stale?64:26,240,stale?48:32,BG);
        } else if(headerTask==2) {
            c.fill(0,stale?126:60,240,stale?16:8,BG);
        } else if(headerTask==3) {
            c.fill(0,stale?166:73,240,stale?40:31,BG);
        } else if(headerTask==4) {
            c.text(87,10,"SHINO // TV",LABEL);
            if(clock.synthetic || weather.synthetic)
                c.text(3,10,"SIMULE",LABEL);
            if(clockFresh(now) && clock.source==ClockSource::PairedPc)
                c.text(219,10,"PC",LABEL);
            else if(clockFresh(now) && clock.source==ClockSource::Sntp)
                c.text(219,10,"NT",LABEL);
        } else if(headerTask==5 || headerTask==6) {
            if(clockFresh(now)) {
                const uint32_t seconds=clock.hour*3600U+clock.minute*60U+
                    clock.second+uint32_t(now-clock.observedMs)/1000U;
                char value[16];
                if(headerTask==5) {
                    snprintf(value,sizeof value,"%02lu:%02lu",
                        (unsigned long)(seconds/3600U)%24U,
                        (unsigned long)(seconds/60U)%60U);
                    c.text(stale?30:60,stale?64:26,value,WHITE,stale?6:4);
                } else {
                    unsigned year=clock.year,month=clock.month,day=clock.day;
                    // The validated clock lease is <=24h; at most one rollover.
                    if(seconds>=86400U && ++day>monthDays(year,month)) {
                        day=1;if(++month>12){month=1;++year;}
                    }
                    snprintf(value,sizeof value,"%02u/%02u/%04u",day,month,year);
                    c.text(stale?60:90,stale?126:60,value,LABEL,stale?2:1);
                }
            } else if(headerTask==5)
                c.text(30,stale?80:32,"TIME NOT SYNCED",WHITE,2);
            else c.text(72,stale?126:60,"DATE UNAVAILABLE",LABEL);
        } else if(headerTask==7) {
            if(weatherFresh(now)) paintWeatherIcon(c,stale?58:46,stale?166:73);
        } else if(headerTask==8) {
            if(weatherFresh(now)) {
                const int magnitude=weather.tenthsC<0?-weather.tenthsC:weather.tenthsC;
                char degrees[16];
                snprintf(degrees,sizeof degrees,"%s%d.%d",
                    weather.tenthsC<0?"-":"",magnitude/10,magnitude%10);
                c.text(stale?100:88,stale?168:76,degrees,WHITE,2);
                const int unit=(stale?100:88)+int(strlen(degrees))*12+2,uy=stale?168:76;
                c.fill(unit+1,uy,2,1,WHITE);c.fill(unit+1,uy+3,2,1,WHITE);
                c.fill(unit,uy+1,1,2,WHITE);c.fill(unit+3,uy+1,1,2,WHITE);
                c.text(unit+6,uy,"C",WHITE,2);
                const char* label=weatherLabel();
                c.text(stale?100:88,stale?190:96,label?label:"ICON UNKNOWN",LABEL);
            } else {
                const char* label=weather.valid?"WEATHER STALE":"WEATHER --";
                c.text((240-int(strlen(label))*6)/2,stale?180:82,label,LABEL);
            }
        } else {
            headerDirty=false;
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
        if (stale != m.stale) { headerDirty = true; headerTask = 0; if(idleScene(scene)) { clearing = true; clearY = 0; } dirty = 15; }
        stale = m.stale;
        for (unsigned i=0;i<4;++i) {
            Card next; float p = -1;
            if (!m.stale && (i == 0 || i == 2 || m.gpuAvailable)) {
                if (i < 2) {
                    const float value = i ? m.gpu : m.cpu;
                    snprintf(next.number,sizeof next.number,"%.0f%%",value);
                    p = DashboardV2::clamp100(value);
                } else if (i == 2) {
                    snprintf(next.number,sizeof next.number,"%.1fG",m.ramGb);
                    p = DashboardV2::ramPercent(m.ramGb,m.ramTotalGb);
                    if (p >= 0) snprintf(next.total,sizeof next.total,"/%.1f GB",m.ramTotalGb);
                } else { snprintf(next.number,sizeof next.number,"%.0fC",m.gpuTempC); p=DashboardV2::tempPercent(m.gpuTempC); }
                // Temperature has no approved normalization: neutral track only.
            }
            next.band = DashboardV2::stableBand(cards[i].band,p);
            next.pixels = p <= 0 ? 0 : uint8_t(DashboardV2::clamp100(p)*B53Layout::CARD_BAR_WIDTH/100+0.5F);
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
            if(stale) { dirty=0; return false; }
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
