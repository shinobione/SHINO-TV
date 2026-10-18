# Public/private correspondence and limits

This branch copies an allowlisted source graph into a fresh history descending
from public `main` at `8425dd7f2526c29e6c53b4294909a4bf03d3112f`.
The original local integration, source branches, full history, private candidates
and receipts are preserved. Audit found private identity/fingerprint material in
that history; the original branches are not pushed, rewritten or merged here.

The complete native application, the exact materialized Core HTTP parser, the
isolated Updater512 source/patch, the 4m2m linker and the actual HOST test sources
are published. A private local correspondence record maps every copied file to its
original path/hash and records controlled transformations. It is not published.
Original private source commit IDs, firmware hashes/manifests, keys and receipts
are deliberately absent from this export. No statement of identical private BIN
or public/private build identity is made.

Documented rematerializations:

1. Three identity/key policy headers use explicit HOST-only synthetic fixtures.
   They cannot preprocess for ESP8266. HOST fixture constants are not production
   defaults, owner keys or activation authority.
2. Private location binding is replaced with DEMO-CITY, coordinates0/0 and opaque
   eight-byte identity DEMO0001. Exact binding validation remains exact; it is not
   generalized to arbitrary locations. The independent protocol golden vector is
   rematerialized with that same synthetic binding and standard HMAC calculation.
3. HOST network fixtures use a synthetic private subnet. AP protocol defaults are
   preserved; no private device/VM target or discovery mechanism is supplied.
4. CRLF is normalized to LF. A simulator include path becomes relative. Build/test
   adapters are portable and use public source dependencies. Pure image/signature
   helpers and two Digest classes are exact excerpts from existing tests/clients;
   provisioning/collection executable code is not included.

Algorithms, routes, protocol domains and framing, 6-second LINK TTL, replay/clock
checks, memory admission/floors and flash/RTC paths are retained. Native and HOST
application function bodies are compared in tests after those parameter bindings.
Updater upstream-to-512 difference is checked independently; U_FLASH is opt-in,
stock/non-U_FLASH branches and invalid-macro refusal are preserved.
The original private provenance/build association is not relaxed or claimed to
pass on this independent public history. The public inventory is a new source-only
review integrity check, not a substitute for the private eligibility gate.

The public tests are rerun from these exported files. Historical private native
build/resource and exact-image test claims are not reclassified as public CI or
physical evidence. The runner generates an explicitly inert, nonbootable test image
in memory; no private image is used or distributed. Native resource budgets, private
release eligibility, installed-image identity and recovery qualification remain
separate HOLD gates.

Licenses: SHINO/Times-Z source under the included project LICENSE; ESP8266 Core
under its included upstream license; ArduinoJson under the included MIT license;
BearSSL has its copyright/permission notice in each source; classic Adafruit GFX
font attribution remains in the source. No third-party binary package is included.
