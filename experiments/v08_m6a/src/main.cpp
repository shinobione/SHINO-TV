// Unstarted isolated compile/link specimen, equivalent across all three builds.
#include <Arduino.h>
#ifdef LAB_PREVIOUS
#include "../.pio/previous_overlay/ESP8266WebServer.h"
#elif defined(SHINO_V08_PREPARSE_EXPERIMENT)
#include "../.pio/pinned_overlay/ESP8266WebServer.h"
#else
#include <ESP8266WebServer.h>
#endif
using LabServer = esp8266webserver::ESP8266WebServerTemplate<WiFiServer>;
static LabServer labServer(80);
volatile uint8_t labCompilePath = 0;
__attribute__((used)) void compileOnlyPreparse(LabServer& server) {
  server.handleClient();
}
void setup() {
  if (labCompilePath) compileOnlyPreparse(labServer);
}
void loop() { delay(1000); }
