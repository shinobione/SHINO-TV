# OEM upload client correction — OFFLINE PASS / physical HOLD

Subsequent separately authorized single-hop evidence is recorded in
[the corrected actual upload report](OEM_SINGLE_HOP_2026-10-02.md).
The no-contact/M8-running statements below describe this earlier offline
investigation, not the subsequent physical operation.

2 October 2026. Continuation of PR #41 from `d7565ca`, addressing
[owner review #5942560005](https://github.com/shinobione/SHINO-TV/pull/41#issuecomment-5942560005).
No device contact, firmware POST, reboot, credential write or firmware build was
performed in this investigation. M8 is left running; its last physical health
evidence remains the [preceding attempt report](DEVICE_INSTALLATION_2026-10-02.md).

## Recoverable cause and precise uncertainty

**Confirmed diagnostic defect:** the actual private `Device.once_upload` let
`urllib.error.HTTPError` escape without reading its code/headers/body, and the
Hop-1 caller reduced it to `failure_type=HTTPError` / `SANITIZED_EXCEPTION`.
The completed subprocess and retained receipt contain no status, response stream,
raw request, server challenge history or packet capture. The original status and
body are **unrecoverable from retained evidence**. Do not relabel the original
failure 401 or 422 after reproducing those cases locally.

| Candidate explanation | Retained/source evidence | Conclusion |
| --- | --- | --- |
| Wrong field, extension, image or multipart layout | Original helper reconstructed without network I/O: POST `/api/v1/bridge/factory-return`, field `factory_v9_0_44`, 32-byte `.bin` filename, exact 494144-byte OEM SHA, one multipart part; corrected multipart is byte-identical | No construction discrepancy found |
| Wrong Digest method/URI/hash | Actual private credentials checked only in memory with a synthetic challenge: exact POST URI and MD5 `qop=auth` calculation match pinned Core 3.1.2; callback validation does not mutate nonce/opaque | No deterministic calculation defect found; original challenge values are not retained |
| Stale Digest / LINK challenge contention | Core stores one shared nonce/opaque pair and replaces both on `requestAuthentication`; ordinary successful authentication does not consume them. Existing LINK refreshes on 401. A refresh between the final GET and POST can invalidate this client | Supported mechanism, **not a proven cause**; actual rotation/order absent |
| Firmware transfer/storage/resource rejection | Installed M8 can return 422 before accepted completion; a begun failed transfer schedules a restart. Same boot was observed later, but there is no upload status or flash trace | Cannot identify the rejected gate or prove whether staging sectors were written |
| Client's 90-second timeout | Original upload timeout is 90 s; entire wrapper elapsed 3.323 s and exception was HTTPError. Native maximum service rose to 3.082 s | Not evidence of a 90-second client timeout; HTTP/parser rejection remains possible. Timing correlation is not causation |
| Regressed upload recipe | Earlier retained OEM returns acknowledged 200/staged using the same `Device.once_upload` recipe and wrapper, including the 18:46 CEST return; raw wire/challenge transcript and contemporaneous helper hash were not retained | Historical success supports compatibility, not identical runtime challenge or new device success |

No evidence requires a P1 firmware rebuild. Its retained 464544-byte BIN remains
SHA-256 `31e3f225744bd806df3302dbf3355770a313f8b71f65b33fd6e2f431449b0be5`.

## Exact installed-M8 request comparison

Reviewed **PR #39 `9fce7137f9fadd83678887442bf91cf60ea86b2e`**, not the new P1
network overlay, and hash-verified locally retained stock Core 3.1.2 sources:

- `FirstBootBridge.cpp` SHA-256 `338cfe8e8e978fbbf2f2a82feb686d932e2453cb50d63dca5073ea0be78eda73`:
  upload callbacks authenticate each phase; completion first calls `requireAuth`.
- `FactoryRollback.cpp` SHA-256 `346be17993ef0f1333032b3c10f9a083458f198efb61a19c50534933a4c6e550`:
  exact field/extension, 4 MiB flash, available staging space, Update state, image
  header, exact byte count, MD5 and `Update.end(false)` gates. 401/denied,
  422/rejected, and 200/staged are distinct outcomes. `requireAuth` can instead
  generate a 401 challenge with an empty HTML response; parser rejection also exists.
- Core `ESP8266WebServer-impl.h`: server authentication matches realm/nonce/opaque,
  method POST, URI and MD5(qop) on START/WRITE/END and completion. It does not mutate
  challenge state on success. Only a new authentication challenge rotates it.
- Core `Parsing-impl.h`: one multipart part's START, WRITE and END callbacks run
  while parsing the request; no second `handleClient` call is added by that parser.
  Network yielding is not proof of concurrent application-level request handling.

The retained **M8R overlay** was also compared to the exact PR #39 transforms,
in memory without materializing or rebuilding anything. It matches; the OEM
`_parseForm` tail and Digest/challenge functions are unchanged from the pinned
Core. M8R uses the Mission 6A legacy parser, **not Mission 6C's multipart-denial
candidate**. Its 2000 ms / 30 ms ingress guards do not turn the full legacy OEM
multipart body into a new 2000 ms upload deadline. Overlay SHA-256 values:
`ESP8266WebServer-impl.h` `49f1807f2f21f3cd9e079204e26c0a6d70d76db5c29a363a935e6adea08f3952`;
`Parsing-impl.h` `ab3da42e849af911ba75172c9f5ad5e8695ed28457cc564c94b5841189fc41d4`;
`ESP8266WebServer.h` `bf4f11930335fd79f443a375dcb5321b91648307f3506af8f32c74a207526316`.

The original constructed envelope is **494357 bytes** (494144-byte image plus
213-byte envelope), boundary **29 ASCII bytes**, with CRLF delimiters and terminal
`--boundary--\r\n`. Original urllib adds Host and Content-Length on the wire;
the corrected client makes both explicit. There is no Cookie, Transfer-Encoding,
Expect/100-continue, redirect handler that follows redirects, or upload auth retry.
The image suffix is `.bin`, per-part MIME is `application/octet-stream` and
outer MIME is `multipart/form-data`. Authorization is preemptive on the initial
POST; callback authentication is server-side reuse of that header, not further
client requests. A timeout/socket failure or stale challenge stops without retry.

## Concrete corrected client

The **actual existing private `m8_device.py`** is corrected in place to delegate
`Device.once_upload` to the tracked [owner_install_http.py](../../tools/owner_install_http.py).
Its original bytes are preserved privately before editing, SHA-256
`b1f8795f5fb4a102b82c77c7c60602b9cbcf6252dbff42a16789ee22aca18c75`.
The original Hop-1 wrapper and failed receipt are preserved unchanged; receipt
SHA-256 `14122f18d51deb83632dc9db453022dce6051675a033ff5e5adfa26989fb5199`.
The actual corrected wrapper is local `research-local/p1_install_hop1_corrected.py`;
default invocation is review-only and makes **zero** device requests. It requires
a new owner-approved execution flag and exact current source HEAD for any future
operation, and never proceeds to Hop 2 automatically. The flag is an execution
guard, not a substitute for owner approval or LCD/power confirmation.

The transport exclusively creates a durable attempt receipt before network I/O.
An existing receipt prevents another POST. It uses one proxy-free request, no
Digest or cookie handler on the write opener, and no redirect following/retry.
It records:

- Numeric target/Host, allowed path/field, filename suffix/length, image size/hash,
  content length, boundary, MIME, presence/length of preemptive Digest and timeout.
- HTTP status **before** reading the response, elapsed time and final outcome.
- Safe header allowlist: numeric Content-Length, known MIME, `no-store`, `nosniff`,
  challenge scheme and redirect-presence booleans. No challenge values or Location.
- At most **4097 observed response bytes**, to detect the 4096-byte cap. A safe
  snippet is reconstructed from recognized status words and exact known firmware
  messages; arbitrary server text and other fields are omitted, not regex-redacted.

Authorization, usernames/passwords, cookies, nonce/opaque/cnonce, private filenames
and paths, raw body/image, arbitrary headers and exception text are never copied
to receipts. A 200 without a complete recognized acknowledgement stays HOLD.
401, 422, redirects, stale Digest, oversized/malformed/incomplete responses,
timeouts and lost acknowledgements all stop without resubmission. Capturing an
error does not establish zero flash writes, even for 401: without callback history
and a fresh boot/storage trace, the transport retains `staging_sector_writes=UNKNOWN`.

## Local validation and corrected owner-review plan

**HOST-PASS:** ten unittest methods, including multiple HTTP variants, exercise
the shared transport against a disposable `127.0.0.1` server. The same ten methods
also pass through the **actual corrected private `Device.once_upload` method**
with synthetic local credentials/payload, never the owner device. Exact request
body/length/Host/field, independent MD5(qop) model, all four callback checks,
error preservation, secret omission, one-POST behavior and exclusive receipts
are checked. A truncated request/late disconnect never triggers a replay.
Hash/source/request comparison with real retained private inputs is in-memory
only, with a capture-only opener and synthetic challenge, not a native receiver
or flash test. These results are not DEVICE-PASS.

Future plan, **not authorized or executed here**:

1. Obtain new authorization for **one corrected M8→exact OEM Hop 1** (494144 B,
   SHA-256 `a6421f5bfee7860d97bed26620c346b8008f503e513702d4bfdf6e01010a7718`),
   including its expected installation reboot. Confirm current physical LCD and
   stable USB power, fresh boot/4 MiB/resources/LINK/OEM gates, exact file rehash.
2. Use the corrected private wrapper on the reviewed final HEAD. Leave LINK and
   firmware unchanged; run serial preflight with no parallel diagnostic observer.
   Use the final authenticated OEM capability GET immediately before the single
   POST; do not force a second challenge or retry an upload on 401. This narrows
   but does **not eliminate** the shared-nonce race.
3. Persist the bounded/sanitized receipt. Any error, missing acknowledgement,
   resource failure or unexpected reset stops. No automatic retry or rollback.
4. Only a verified staged acknowledgement permits waiting for the expected OEM
   boot and subsequent read-only LAN rediscovery/version/recovery/display checks.
   This corrected Hop-1 wrapper stops there. Hop 2 and subsequent provisioning
   require their applicable exact owner gates; no first persistent Wi-Fi write
   before P1's three-minute boot/AP/LCD/LINK/resource baseline and separate consent.

**Decision:** corrected client OFFLINE READY; original upload cause UNKNOWN;
another physical upload awaits new owner authorization. P1 DEVICE HOLD,
R3 PARTIAL / R10 BLOCKED. PR #39/#40 and both retained application images unchanged.
