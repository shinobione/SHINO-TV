// Compile/link-only research image. setup() never starts Wi-Fi or WebServer.
// No route, listener, sender, credential, update or device action is present.
#include <Arduino.h>
#ifdef SHINO_V08_PREPARSE_EXPERIMENT
#include "../.pio/pinned_overlay/ESP8266WebServer.h"
#else
#include <ESP8266WebServer.h>
#endif

using LabServer = esp8266webserver::ESP8266WebServerTemplate<WiFiServer>;
static LabServer labServer(80);
volatile uint8_t labCompilePath = 0;

// Force the modified pinned template path through the target compiler/linker.
// This function is retained for build evidence and is never called.
__attribute__((used)) void compileOnlyPreparse(LabServer& server) {
  server.handleClient();
}

void setup() {
  // Volatile guard retains the link graph; its fixed value leaves the server idle.
  if (labCompilePath) compileOnlyPreparse(labServer);
}
void loop() { delay(1000); }
