// SPDX-License-Identifier: GPL-3.0-or-later
#pragma once
// Stand-alone initial entry: no LittleFS mount, EEPROM init, config migration,
// owner-data formatting, or persisted SDK Wi-Fi credentials.
namespace FirstBootBridge {
void run();
void loop();
bool isActive();
} // namespace FirstBootBridge
