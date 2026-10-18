#include <pgmspace.h>
#include "B5Lan_host.inc"
#include "FslessMetrics_host.inc"
#include "ClockFreshness.h"
#undef HOST_MOCK
#include "B52Clock_host.inc"
#define HOST_MOCK 1
#include "B53Sntp_host.inc"
#include "B53Integrated_host.inc"
#include "B54LanNative_host.inc"
#include "normal_host.inc"
