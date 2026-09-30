# Mission 7 findings and preservation matrix

Exact start/current truth: PR#36 `4d6180959b843c64e92b72425134c2dfc6688c88`. Earlier documents/tests/PRs remain historical. FIXED below means only the isolated offline candidate; host/compiler evidence cannot authorize deployment.

| ID | Mission7 evidence/status | Remaining boundary |
|---|---|---|
| R1 revocation | Native enabled/revoked/media-role/operation/revision checks; terminal revocation, post-proof body denial and final consume invalidation tested | Production persisted lifecycle/custody absent; privileged single-owner APIs only |
| R2 exact magic | Literal STV7 bytes after exact-body SHA and strict wire checks; native10,207-case differential matches unchanged reference | No signature forgery, exhaustive2^32 magic or device claim |
| R3 freshness/bounds | Fixed16-principal/four-global/two-per-principal challenge storage; ordered watermark, single consume, exact/wrapped expiry, increasing epoch | PARTIAL: reconstruction/power-loss freshness, production entropy/trusted issuer/revocation persistence unproved |
| R4 cheap denial | Unknown/used/expired/wrong-role/operation principal deny with zero ECDSA/body; real proof + serial/revision/expiry recheck; single consume | Native timing/rate limits/interrupt concurrency unqualified; synchronous crypto may block one poll |
| R5 scheduling | Mission6A first-line clocks and >30ms predicate retained; media continuation competing legacy exact30/31 and one terminal cleanup | SDK close latency/fairness/application timing remain HOLD |
| R6 namespace | Mission6A reservation view/raw legacy handoff unchanged; media acceptance requires strict exact raw target | PARTIAL:130-byte cap/strict path restrictions and OEM/external-client physical compatibility remain |
| R7 legacy | Mission6C evidence preserved; new candidate uses Mission6A parser/auth, preserving authorized conditional inert multipart | OPEN legacy weaknesses; Mission6C multipart-deny behavior is not adopted. Media uses its own pre-body proof gate |
| R8 lifetime/resources | PC FIN/terminal close/body cleanup and balanced contexts/zero descriptors; full native links/static section/object/frame evidence | HOLD SDK/lwIP/heap/stack/WDT/close/ACK/flush/runtime qualification |
| R9 composition | Real generated owner→native Gate1→bounded body→Gate2→wire/staging→inert ownership sink exercised over loopback; full native graph linked | Offline composition established, physical/runtime/display/active route acceptance HOLD |
| R10 provisioning | Public retained and ephemeral synthetic fixtures only; required roster/issuer/epoch/reboot interfaces documented | BLOCKED real owner-approved provisioning/custody/enrollment/entropy/delivery; no production private key |

| Preservation item | Evidence |
|---|---|
| PR#29–35 | Read-only live inspection: all OPEN/Draft at original heads |
| PR#36 | OPEN/Draft at exact start; preserved as current truth, not rewritten |
| Frozen production/companion/simulator/public vectors | Allowed-diff guard permits only new Mission7 tools/project/docs, CI and ignore entries; no production source edits |
| Earlier mission reports/tests/generators | Unchanged; native runner executes the inherited224/227 legacy tests against the new owner with media disabled |
| Mission6C incompatible multipart candidate | Retained as historical research; not used as native media's legacy parser |
| Private policy/device/OTA/sender/install/merge | None performed; no authorization granted by green tests/CI |
