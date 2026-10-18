// SPDX-License-Identifier: GPL-3.0-or-later
// Dedicated OEM application OTA route. Not a full flash restore.
#pragma once

#include <ESP8266WebServer.h>

namespace FactoryRollback {
void status(ESP8266WebServer& server);
void upload(ESP8266WebServer& server, bool authenticated);
void complete(ESP8266WebServer& server, bool authenticated);
void tick();
} // namespace FactoryRollback
