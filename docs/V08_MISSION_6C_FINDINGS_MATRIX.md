# Mission 6C R7 differential and preserved findings

Exact start: `7d40df9f69bead1aa3a8c7ebd88dbfa0121968e0`. FIXED means only the isolated source/host candidate. All historical documents/tests remain unchanged. Known-failure assertions reproduce vulnerabilities; green CI does not accept them as secure.

| Historical R7 case | Stock / previous remediated | Partial R7 candidate | Disposition |
|---|---|---|---|
| Basic! scheme | Valid credentials accepted | 401 | FIXED |
| Digest wrong URI, including query substitution | Accepted | Actual raw target required | FIXED |
| Same nc/proof replay on same target or another path | Accepted | Target binding and monotonic nc reject | FIXED in live nonce; reset/entropy/persistence not qualified |
| cnonce switch / zero nc | Accepted | Nonzero, increasing shared watermark required | FIXED with stricter concurrent-client compatibility |
| Digest POST proof reused with changed body | Accepted | Exact replay rejects; FIRST-use altered body still accepts | PARTIAL: replay fixed; content integrity remains ACCEPTED LEGACY LIMITATION / security HOLD |
| qop=auth content not authenticated | Changed first-use metrics accepted | Same altered first-use metrics accepted | ACCEPTED LEGACY LIMITATION for characterization only; no integrity or compliant-extension claim |
| Duplicate Authorization order | Last field wins, 401/200 order dependent | Terminal close both orders | FIXED |
| Duplicate Cookie header ambiguity | Last field wins | Duplicate field terminal close | FIXED by parser critical-field rule; duplicate session-name policy unchanged |
| Incomplete final header before FIN | Still dispatches 200 | Strict CRLF/blank terminator required; closes | FIXED |
| Unauthorized ordinary body before 401 | 4096 consumed | 4096 consumed | BLOCKED BY ARCHITECTURE; never security PASS |
| Multipart unauthorized callbacks before completion auth | START/WRITE/END callbacks run | Multipart terminal denial, zero body/callbacks | BLOCKED BY ARCHITECTURE for compatible authenticated upload; denial alone is not auth repair |
| Indefinite trickled legacy headers | Per-read timeout restarts; >2.1-second poll reproduced | Absolute shared deadline, finite work/byte caps | PARTIAL: input loops bounded; no native total-poll or incremental-body acceptance |
| Declared huge/negative/duplicate framing | Permissive integer/last-field behavior | Strict checked length <=4096; duplicates/TE reject before body | FIXED for rejected framing; authorized/unauthorized ordinary bodies still buffered before application auth |
| Slow/incomplete ordinary body | Blocking body read before handler | Absolute deadline and shared work cap terminate | PARTIAL: pre-body authorization and per-poll incremental receipt blocked |
| Application behavior | Actual routes, metrics and conditional inert uploads | Ordinary routes/metrics preserved; authorized multipart unavailable | PARTIAL / upload compatibility HOLD |

| ID | Current status retained at Mission 6C |
|---|---|
| R1 | Mission 6B FIXED host lifecycle; production authority not supplied |
| R2 | Mission 6B FIXED host exact bytes; unchanged wire differential evidence |
| R3 | Mission 6B PARTIAL; persistent freshness/trusted issuer gap remains |
| R4 | Mission 6B FIXED host cheap denial/consume; native synchronization/timing gap remains |
| R5 | Mission 6A FIXED isolated strict >30-ms no-data policy; candidate retains exact 30/31 and rollover |
| R6 | Mission 6A PARTIAL capped/strict-path compatibility policy; classifier unchanged |
| R7 | PARTIAL; pre-body application authorization and compatible incremental multipart BLOCKED BY ARCHITECTURE; qop=auth content integrity HOLD |
| R8 | NATIVE/RUNTIME GAP: SDK/lwIP/flush/abort/ACK/resource and allocation-failure behavior absent |
| R9 | NATIVE/ACCEPTED-MEDIA COMPOSITION GAP: legacy host source composition retained, media DENY-ALL |
| R10 | BLOCKED: production custody, enrollment, revocation authority, entropy, persistent freshness and delivery absent |
