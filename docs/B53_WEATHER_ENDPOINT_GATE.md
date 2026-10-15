# B5.3 native weather endpoint capability gate (NOT device testing)

This branch adds an isolated public-network diagnostic run in GitHub Actions.
It contacts **only** public `api.open-meteo.com:443` using a **fixed
example location (Paris)**, never the owner's address, Wi-Fi, SmallTV or
any other private target.

The script uses OpenSSL TLS 1.2 / SNI / proposed MFLN=512 and the **exact
ISRG Root X1 anchor already committed** for B5.3 to check full certificate
validation and whether the server echoes the 512-byte extension. A
second HTTP/1.1 request checks real Open-Meteo headers and size of a
small current-conditions JSON response (without publishing temperature).

A network outage or unavailable evidence is `NON_VERIFIE`, not PASS.
The gate FAILS if certificate, MFLN or bounded HTTP response preconditions
are not confirmed. No automatic fallback to insecure HTTP.

Even a successful endpoint gate does NOT qualify the native handshake:
the current hard guard demands 36,864 B free heap / 32,768 B largest block /
3,072 B stack. The B5.2 **last physical observed** values do not meet it.
Do not disable floors to make this gate green.

If HOLD: retain B5.3 SNTP/UI progress, defer direct weather TLS
activation. Avoid adding proxy infrastructure or another OTA until the
owner agrees to an alternative architecture. No OTA, Wi-Fi or file system
device operations are performed by this gate.
