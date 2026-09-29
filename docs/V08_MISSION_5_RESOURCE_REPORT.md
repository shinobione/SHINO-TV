# SHINO // TV — V0.8 Mission 5: host resource and scheduling evidence

**HOST MEASUREMENTS ONLY. No ESP8266 runtime heap, stack, CPU, WDT, socket lifetime or LCD qualification.** Date: 29 September 2026, Europe/Paris.

## Measurement method and provenance

`v08_m5_socket_lab.cpp` wraps each real `handleClient()` poll with steady-clock time, deltas of actual application TCP bytes consumed, first-response-write timing, and a byte-count histogram. Histograms record count→number of polls, including zero-byte polls. Read/write counters exclude the peer's response reads and include the server adapter's actual recv/send bytes. Worst poll is wall duration through function return, including waits. First-response-write latency runs from poll entry to the adapter's first response write; it includes parser/auth/dispatch/serialization. Synchronous transaction duration also includes arrival/peer receive overhead and is a different metric.

Host new/new[] and delete/delete[] counters are process-wide C++ allocation **call counts**. They exclude C allocator/library internals, OS TCP memory and aligned allocation forms; they are not peak resident bytes or native heap reserves. Counts are sampled while the global bridge, handlers, cookies, Strings and histogram remain alive; unequal totals are not by themselves a leak result. No production allocator is replaced. Socket descriptor/context counts track accepted shared host contexts plus listener/peers; every test teardown proves zero live descriptors and equal created/destroyed contexts. Context and peer maximum wall lifetime are measured separately. Explicit stop count includes test setup/cleanup as well as source decisions, and must not be interpreted as a count of native FINs.

Local `V08_MISSION_5_LOCAL_EVIDENCE.json` records three MSVC runs from a working snapshot based on Mission 4, with per-input and generated hashes. CI reruns all three using the final checked-out SHA, GNU C++/OpenSSL and real ArduinoJson. The separate Draft PR body is updated with verified final head, run URLs and job conclusions at delivery; its CI artifact contains exact `source_head`. Local values below are rounded observations and can vary by host load. They are not hard upper bounds or performance targets.

## Observations

| Measurement | Stock/default | Overlay/default | Overlay/conditional inert OEM |
|---|---|---|---|
| Assertion set | 70 checks, zero failures | 171 checks, zero failures | 174 checks, zero failures |
| First-line-only maximum bytes/poll | Stock has no preparse slice | 64 | 64 |
| Whole-poll maximum bytes | 4214 | 4214 | 4214 |
| Worst deliberately observed poll | About 47 ms, delayed line/header fixture | About 2.1 s, delayed header fixture | About 2.1 s, delayed header fixture |
| Ready client real-clock wall wait | About 67 ms | About 2035 ms | About 2041 ms |
| Injected-clock owner release | At tick31 after >30ms grace | At elapsed2000 | At elapsed2000 |
| Peak live PC socket descriptors | 13 | 13 | 13 |
| Cleanup | Every context destroyed; zero live sockets | Same | Same |

Read the JSON for exact counts, durations, response bytes, first-write latency, lifetime, allocation/deallocation counts and histograms for the measured input hashes. Different variants have different assertion/traffic totals and are **not equal-work throughput benchmarks**. The 130/131-byte fixture measures at most64 in polls that do only preparse; the poll that admits legacy immediately parses headers/body and dispatches. A whole-poll cap of64 is therefore false. The 4096-byte body case produced4214 application bytes in one poll and still denied authentication afterward.

The real-clock contention fixture requests 1-ms sleep between polls; Windows scheduling need not provide that cadence. Stock's source grace is30ms, but observed service also includes cadence, accept/drop-next-poll, socket readiness and response transfer. The overlay replaces that policy with a2000ms first-line deadline. Injected-clock waits exercise exact policy boundaries without spending the same wall time; their sub-millisecond wall measurements must not be used to claim real service latency. The separate real-clock measurements demonstrate the roughly2-second ready-client delay.

The deliberately2100ms trickled header continuation proves a single overlay poll can run beyond the first-line deadline once legacy parsing starts. Application return, repaint, OEM tick and WDT service are deferred until that poll returns. The actual application loop was exercised with inert dependencies, but this is not physical watchdog or dashboard latency evidence. Stock partial first lines similarly block inside pinned `Stream::readStringUntil`; the earlier fake immediate-return behavior is not PC socket behavior.

## Qualification boundaries

Real PC FIN/RST, unread pipeline bytes and shared-context cleanup narrow the host gap. SDK reference counting, receive buffer reclamation, send-buffer progress/flush/abort paths, close failures and unacknowledged native response drain remain unmeasured. The host adapter's flush is explicitly a no-op and its stop shuts down/closes an OS descriptor; no300ms native-stop bound is claimed.

All native memory figures and linked/compiler-frame evidence in Missions2–4 remain historical evidence and are not refreshed or relabeled runtime qualification here. No private keys, firmware images or device operations are part of this experiment. **HOLD for runtime/resource acceptance; BLOCKED for active native media.**
