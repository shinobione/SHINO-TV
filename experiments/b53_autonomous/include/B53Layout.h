// SPDX-License-Identifier: GPL-3.0-or-later
#pragma once
// Owner's 240x240 layout: large centred clock, compact weather, four cards.
// Bounds only, not a replacement of the installed B5.2 renderer.
namespace B53Layout {
constexpr int WIDTH=240, HEIGHT=240;
struct Rect { int x,y,w,h; };
constexpr Rect HEADER = {0,0,240,104};
constexpr Rect TITLE = {0,9,240,10};
constexpr Rect CLOCK = {44,27,152,40};
constexpr Rect WEATHER = {0,73,240,17};
constexpr Rect CARDS[4] = {
    {6,106,111,60}, {123,106,111,60},
    {6,174,111,60}, {123,174,111,60}
};
constexpr int CARD_LABEL_OFFSET_X=7, CARD_LABEL_OFFSET_Y=7;
constexpr int CARD_VALUE_OFFSET_X=7, CARD_VALUE_OFFSET_Y=20;
constexpr int CARD_BAR_OFFSET_X=7, CARD_BAR_OFFSET_Y=51;
constexpr int CARD_BAR_WIDTH=97, CARD_BAR_HEIGHT=4;
constexpr bool within(Rect r) {
    return r.x>=0 && r.y>=0 && r.w>0 && r.h>0 &&
        r.x+r.w<=WIDTH && r.y+r.h<=HEIGHT;
}
constexpr bool overlaps(Rect a,Rect b) {
    return a.x < b.x+b.w && a.x+a.w>b.x && a.y < b.y+b.h && a.y+a.h>b.y;
}
static_assert(within(HEADER) && within(CLOCK) && within(WEATHER), "Header out of LCD");
static_assert(within(CARDS[0]) && within(CARDS[1]) &&
              within(CARDS[2]) && within(CARDS[3]), "Card out of LCD");
static_assert(!overlaps(CARDS[0],CARDS[1]) && !overlaps(CARDS[0],CARDS[2]) &&
              !overlaps(CARDS[1],CARDS[3]) && !overlaps(CARDS[2],CARDS[3]),
              "Cards overlap");
static_assert(!overlaps(HEADER,CARDS[0]), "Header overlaps metrics");
}
