// SPDX-License-Identifier: GPL-3.0-or-later
#include "boot/ShinoBootProfile.h"
#if SHINO_M9_NORMAL_QUALIFICATION == 1
#include "boot/DashboardV2.h"
#include "boot/FslessMetrics.h"
#include "display/DisplayManager.h"
namespace M9NormalDashboard {
struct Card {
    char number[16] = {};
    float percent = -1.0F;  // negative: unavailable/neutral track.
    bool degree = false;
};
bool firstFrame = true;
char lastNumbers[4][16] = {};
uint8_t lastPixels[4] = {255, 255, 255, 255};
int8_t priorBand[4] = {-1, -1, -1, -1};

void paintCard(uint8_t index, const Card& card) {
    const int8_t band = DashboardV2::stableBand(priorBand[index], card.percent);
    const uint8_t pixels = DashboardV2::fillPixels(card.percent);
    if (!firstFrame && strcmp(lastNumbers[index], card.number) == 0 &&
        lastPixels[index] == pixels && priorBand[index] == band) return;

    Arduino_GFX* gfx = DisplayManager::getGfx();
    const int16_t x = static_cast<int16_t>(DashboardV2::X[index]);
    const int16_t y = static_cast<int16_t>(DashboardV2::Y[index]);
    gfx->fillRoundRect(x, y, DashboardV2::CARD_SIZE, DashboardV2::CARD_SIZE, 12, DashboardV2::CARD);
    gfx->drawRoundRect(x, y, DashboardV2::CARD_SIZE, DashboardV2::CARD_SIZE, 12, DashboardV2::BORDER);

    gfx->setTextColor(DashboardV2::LABEL);
    gfx->setTextSize(1);
    gfx->setTextWrap(false);
    gfx->setCursor(x + 10, y + 11);
    if (index == 0) gfx->print(F("CPU usage"));
    else if (index == 1) gfx->print(F("GPU usage"));
    else if (index == 2) gfx->print(F("RAM in use"));
    else {
        gfx->print(F("GPU"));
        gfx->setCursor(x + 10, y + 22);
        gfx->print(F("temperature"));
    }

    const int16_t valueX = x + 10;
    const int16_t valueY = y + 47;
    gfx->setTextColor(DashboardV2::VALUE);
    if (card.number[0] == '\0') {
        // Original Arduino bitmap font does not reliably support UTF-8 em dash.
        // Draw a neutral em dash as a primitive, preserving all four cards.
        gfx->fillRect(valueX, valueY + 8, 16, 2, DashboardV2::VALUE);
    } else if (card.degree) {
        gfx->setTextSize(2);
        gfx->setCursor(valueX, valueY);
        gfx->print(card.number);  // ASCII number only; UTF-8 degree is NOT sent to bitmap font.
        const int16_t degreeX = valueX + static_cast<int16_t>(strlen(card.number)) * 12 + 3;
        gfx->drawCircle(degreeX, valueY + 4, 2, DashboardV2::VALUE);
        gfx->setCursor(degreeX + 5, valueY);
        gfx->print('C');
    } else {
        // 6x8 bitmap font at size 2 = 12px/glyph; long RAM strings
        // must never clip outside a 90px-wide value region.
        gfx->setTextSize(strlen(card.number) * 12 <= 90 ? 2 : 1);
        gfx->setCursor(valueX, valueY);
        gfx->print(card.number);
    }

    const int16_t trackX = x + 9;
    const int16_t trackY = y + 91;
    gfx->fillRoundRect(trackX, trackY, 90, 6, 3, DashboardV2::TRACK);
    if (pixels > 0 && band >= 0) {
        const uint16_t color = DashboardV2::PALETTE[band];
        if (pixels < 6) gfx->fillRect(trackX, trackY, pixels, 6, color);
        else gfx->fillRoundRect(trackX, trackY, pixels, 6, 3, color);
    }
    memcpy(lastNumbers[index], card.number, sizeof(card.number));
    lastPixels[index] = pixels;
    priorBand[index] = band; // a stale/unavailable card resets hysteresis to -1.
    yield();
}

void render() {
    const FslessMetrics::Snapshot m = FslessMetrics::snapshot();
    const bool old = FslessMetrics::stale();
    if (firstFrame) DisplayManager::getGfx()->fillScreen(DashboardV2::BACKGROUND);

    Card cards[4]{};
    if (!old) {
        snprintf(cards[0].number, sizeof(cards[0].number), "%.1f%%", m.cpu);
        cards[0].percent = DashboardV2::clamp100(m.cpu);

        if (m.gpuAvailable) {
            snprintf(cards[1].number, sizeof(cards[1].number), "%.1f%%", m.gpu);
            cards[1].percent = DashboardV2::clamp100(m.gpu);
            snprintf(cards[3].number, sizeof(cards[3].number), "%.1f", m.gpuTempC);
            cards[3].degree = true;
            cards[3].percent = -1.0F; // Celsius shown; no invented device thermal denominator.
        }
        snprintf(cards[2].number, sizeof(cards[2].number), "%.1f GB", m.memoryGb);
        cards[2].percent = DashboardV2::ramPercent(m.memoryGb, m.memoryTotalGb);
    }
    for (uint8_t i = 0; i < 4; ++i) paintCard(i, cards[i]);
    firstFrame = false;
}

} // namespace M9NormalDashboard
#endif
