// SPDX-License-Identifier: GPL-3.0-or-later
#pragma once
class ConfigManager;
namespace M9NormalStageA {
void beforeSetup();
void begin(ConfigManager& config);
void afterSetup();
void loop();
} // namespace M9NormalStageA
