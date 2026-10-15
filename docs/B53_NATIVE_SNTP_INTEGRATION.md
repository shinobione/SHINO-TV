# B5.3 native SNTP — isolated generated public-inert graph
This milestone preserves B5.2's authenticated PC clock/telemetry/Digest and
adds Core 3.1.2 asynchronous SNTP fallback, triggered only by verified
from_sntp callbacks while Wi-Fi STA is connected. Europe/Paris TZ and DST
via Core. NTP data expires after 6 h without a fresh callback, and expiry
is latched to avoid stale revival after millis wraps. Authenticated PC clock
has priority while its 120-second lease is fresh. No blocking NTPClient.
This is unauthenticated public NTP, NOT equivalent to MAC-authorized PC time.
The original four cards remain untouched; user Paint UI and weather provider
are still TO DO. Public-inert only; no private image/OTA/device operations.
Full Core compile, memory, runtime, reconnection, DST and physical acceptance
must be independently measured before any exact-candidate OTA authorization.
