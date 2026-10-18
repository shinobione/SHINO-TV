// SPDX-License-Identifier: GPL-3.0-or-later
#pragma once
#include "boot/ShinoBootProfile.h"
#if SHINO_M9_MOUNT_PROBE_RESOURCE_DIAGNOSTICS == 1
#include <ESP8266WebServer.h>
namespace M9MountProbeResources {
void beforeMount();
void afterMount();
void poll();
bool sendStatus(ESP8266WebServer& server);
}
#endif
