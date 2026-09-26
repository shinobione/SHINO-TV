// SPDX-License-Identifier: GPL-3.0-or-later
#pragma once
// Pure pixel and palette rules shared by the 240x240 renderer and host tests.
// Source of truth: docs/NATIVE_UI_V2_240_SPEC.md. No Arduino/FS/EEPROM dependency.
#include <cmath>
#include <stdint.h>

namespace DashboardV2 {
constexpr int CANVAS = 240;
constexpr int CARD_SIZE = 108;
constexpr int TRACK_WIDTH = 90;
constexpr int TRACK_HEIGHT = 6;
constexpr int X[4] = {8, 124, 8, 124};
constexpr int Y[4] = {8, 8, 124, 124};

constexpr uint16_t rgb565(unsigned r, unsigned g, unsigned b) {
    return static_cast<uint16_t>(((r >> 3) << 11) | ((g >> 2) << 5) | (b >> 3));
}
constexpr uint16_t BACKGROUND = rgb565(0x10, 0x13, 0x18);
constexpr uint16_t CARD = rgb565(0x22, 0x29, 0x33);
constexpr uint16_t BORDER = rgb565(0x39, 0x47, 0x55);
constexpr uint16_t LABEL = rgb565(0xBF, 0xC9, 0xD4);
constexpr uint16_t VALUE = rgb565(0xF6, 0xF3, 0xEF);
constexpr uint16_t TRACK = rgb565(0x53, 0x62, 0x77);
constexpr uint16_t PALETTE[4] = {
    rgb565(0x66, 0xD3, 0x9A), // mint
    rgb565(0xD8, 0xC3, 0x5E), // yellow
    rgb565(0xD9, 0x89, 0x4A), // orange
    rgb565(0x8E, 0x39, 0x4B), // burgundy
};
constexpr float BOUNDARIES[3] = {20.0F, 50.0F, 80.0F};
constexpr float HYSTERESIS = 2.0F;

inline float clamp100(float value) {
    if (!std::isfinite(value)) return 0.0F;
    return value < 0.0F ? 0.0F : (value > 100.0F ? 100.0F : value);
}
inline float ramPercent(float used, float total) {
    if (!std::isfinite(used) || !std::isfinite(total) || total <= 0.0F ||
        used < 0.0F || used > total) return -1.0F; // Unknown, never invent denominator.
    return clamp100(100.0F * used / total);
}
inline float tempPercent(float celsius) {
    return std::isfinite(celsius) ? clamp100((celsius - 30.0F) / 60.0F * 100.0F) : -1.0F;
}
inline uint8_t rawBand(float percentage) {
    float p = clamp100(percentage);
    return p < 20.0F ? 0 : (p < 50.0F ? 1 : (p < 80.0F ? 2 : 3));
}
inline int8_t stableBand(int8_t previous, float percentage) {
    if (percentage < 0.0F || !std::isfinite(percentage)) return -1;
    const float p = clamp100(percentage);
    if (previous < 0 || previous > 3) return static_cast<int8_t>(rawBand(p));
    int8_t b = previous;
    while (b < 3 && p >= BOUNDARIES[b] + HYSTERESIS) ++b;
    while (b > 0 && p < BOUNDARIES[b - 1] - HYSTERESIS) --b;
    return b;
}
inline uint8_t fillPixels(float percentage) {
    if (percentage <= 0.0F || !std::isfinite(percentage)) return 0;
    float px = clamp100(percentage) * TRACK_WIDTH / 100.0F;
    int width = static_cast<int>(std::floor(px + 0.5F));
    if (width < 1) width = 1;
    return static_cast<uint8_t>(width > TRACK_WIDTH ? TRACK_WIDTH : width);
}
} // namespace DashboardV2
