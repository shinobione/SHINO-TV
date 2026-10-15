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

## Verified public probe — 2026-10-15

At `6d72df798063ddcef75bd9fb673d8edaff373d5f`,
GitHub Actions run `38783256220` observed TLS1.2 certificate validation
against the *committed* ISRG Root X1 **PASS**; 512-byte MFLN server
extension **ACCEPTED**; HTTP 200; Content-Type application/json;
366 bytes of decoded example JSON, with `Transfer-Encoding: chunked`
and no `Content-Length`. The first gate returned HOLD because the
B5.3 client **then** supported only Content-Length framing.

The native chunked decoder added at
`889ec00610e6143c1d92cf9ba26c8047cbf634f0` supports that
framing with a 768-byte decoded limit and strict CRLF, no extensions
or trailers. These are **public GitHub-runner observations** and
HOST/compile tests, not physical proof of TLS success or weather display.

Endpoint verification may change if the server rotates its chain,
stops negotiating MFLN, or changes HTTP framing. The workflow is
a point-in-time observation, not a permanent guarantee.
