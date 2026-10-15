"""B5.3 owner-Paint IDLE renderer, generated graph only (not PR40/B5.2).

Pure textual materialization with exact anchored replacements. Fail closed on
base renderer drift. The native firmware renderer itself has no new heap use.
"""
from shino_b5_lan_build import once


def _replace_section(source, begin, end, replacement):
    if source.count(begin) != 1 or source.count(end) != 1:
        raise ValueError("B5.3 renderer anchor drift")
    start = source.index(begin)
    stop = source.index(end)
    if stop <= start:
        raise ValueError("B5.3 renderer section order drift")
    return source[:start] + replacement + source[stop:]


CARD = """    void paintCard(Canvas& c, unsigned i) {
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
"""
HEADER = """    void paintHeader(Canvas& c, uint32_t now) {
        // 13 cooperative 8px stripes; unlike B5.2, NEVER paint over cards.
        if(headerTask<13) {
            c.fill(0,headerTask*8,240,8,BG);
        } else if(headerTask==13) {
            c.text(87,10,"SHINO // TV",LABEL);
            if(clockFresh(now) && clock.source==ClockSource::PairedPc)
                c.text(219,10,"PC",LABEL);
            else if(clockFresh(now) && clock.source==ClockSource::Sntp)
                c.text(219,10,"NT",LABEL);
            else if(clock.synthetic || weather.synthetic)
                c.text(219,10,"SIM",LABEL);
        } else if(headerTask==14) {
            if(clockFresh(now)) {
                const uint32_t seconds=clock.hour*3600U+clock.minute*60U+
                    clock.second+uint32_t(now-clock.observedMs)/1000U;
                char hhmm[8];
                snprintf(hhmm,sizeof hhmm,"%02lu:%02lu",
                    (unsigned long)(seconds/3600U)%24U,
                    (unsigned long)(seconds/60U)%60U);
                // Five size-4 Arduino glyphs = 120 pixels, centered.
                c.text(60,32,hhmm,WHITE,4);
            } else c.text(30,39,"TIME NOT SYNCED",WHITE,2);
        } else if(headerTask==15) {
            if(weatherFresh(now)) {
                const int magnitude=weather.tenthsC<0?-weather.tenthsC:weather.tenthsC;
                char degrees[16];
                snprintf(degrees,sizeof degrees,"%s%d.%d C",
                    weather.tenthsC<0?"-":"",magnitude/10,magnitude%10);
                const int pixels=int(strlen(degrees))*12;
                if(pixels<=216)c.text((240-pixels)/2,76,degrees,WHITE,2);
                if(weather.condition[0]) {
                    const int width=int(strlen(weather.condition))*6;
                    c.text((240-width)/2,96,weather.condition,LABEL);
                }
            } else {
                c.text(87,82,weather.valid?"WEATHER STALE":"WEATHER --",LABEL);
            }
        } else {
            headerDirty=false;
        }
        ++headerTask;
    }
"""


def patch_design(source):
    source=once(source,'#include <boot/DashboardV2.h>',
                '#include <boot/DashboardV2.h>\n#include "B53Layout.h"')
    source=once(source,'    bool pauseExpired = false;',
                '    bool pauseExpired = false;\n    bool offlineRendered = false;')
    source=_replace_section(source,"    void paintCard(Canvas& c, unsigned i) {",
                            "    void paintHeader(Canvas& c, uint32_t now) {",CARD)
    source=_replace_section(source,"    void paintHeader(Canvas& c, uint32_t now) {",
                            "    void textRow(Canvas& c,",HEADER)
    source=once(source,
        'if (stale != m.stale) { headerDirty = true; headerTask = 0; }',
        'if (stale != m.stale) { headerDirty = true; headerTask = 0; '
        'offlineRendered = false; dirty = 15; }')
    source=once(source,
        'scene = nextScene; headerDirty = true; headerTask = 0; dirty = 15;',
        'scene = nextScene; headerDirty = true; headerTask = 0; '
        'dirty = 15; offlineRendered = false;')
    # Geometry and readability only: retain metric acceptance and dynamic bands.
    source=once(source,
        'snprintf(next.number,sizeof next.number,"%.1f%%",value);',
        'snprintf(next.number,sizeof next.number,"%.0f%%",value);')
    source=once(source,
        'snprintf(next.number,sizeof next.number,"%.1f GB",m.ramGb);',
        'snprintf(next.number,sizeof next.number,"%.1fG",m.ramGb);')
    source=once(source,
        'snprintf(next.number,sizeof next.number,"%.1f C",m.gpuTempC);',
        'snprintf(next.number,sizeof next.number,"%.0fC",m.gpuTempC);')
    source=once(source,
        'p <= 0 ? 0 : uint8_t(DashboardV2::clamp100(p)*98/100+0.5F)',
        'p <= 0 ? 0 : uint8_t(DashboardV2::clamp100(p)*'
        'B53Layout::CARD_BAR_WIDTH/100+0.5F)')
    # The 30..90 C scale already exists in DashboardV2; do not imply
    # temperature percentage is GPU utilization. Missing GPU remains neutral.
    source=once(source,
        'else snprintf(next.number,sizeof next.number,"%.0fC",m.gpuTempC);',
        'else { snprintf(next.number,sizeof next.number,"%.0fC",m.gpuTempC); '
        'p=DashboardV2::tempPercent(m.gpuTempC); }')
    old='''            for (unsigned i=0;i<4;++i) if (dirty & (1U<<i)) {
                paintCard(c,i); dirty &= uint8_t(~(1U<<i)); return true;
            }
            return false;'''
    new='''            for (unsigned i=0;i<4;++i) if (dirty & (1U<<i)) {
                paintCard(c,i); dirty &= uint8_t(~(1U<<i)); return true;
            }
            if(stale && !offlineRendered) {
                c.text(60,148,"PC OFFLINE",LABEL,2);
                c.text(75,178,"NO PC METRICS",LABEL);
                offlineRendered=true;
                return true;
            }
            return false;'''
    source=once(source,old,new)
    return source
