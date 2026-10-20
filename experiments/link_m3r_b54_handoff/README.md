# B5.4 / M3-R pre-body handoff — HOST only

This laboratory imports the six-file socket overlay reviewed in increment 2.
It does not replace `firmware/`, merge the B5.4 source branch, apply the stock
M3-P parser patch, or enable a display writer. The original M3-O deny-only
profile and M3-C/R headers on this branch remain unchanged.

## Exact sources and six adaptations

The B5.4 dependency is the public source-only `review/` graph of PR #72,
commit `91969aceb45e0c43d44f93a702a3997b57e8f89e`. Its unchanged closed
439-file `SOURCES.json` inventory and its own source hash are checked before
copying. No private source history, identity, key, BIN, receipt or manifest
is a dependency. See that source graph's PROVENANCE.md and LICENSE files.

`overlay.patch` is the actual code import, not a replacement tree. Its six
paths are checked against `overlay-identities.json` before/after applying:

| Paths in the materialized graph | Adaptation |
|---|---|
| `host/Parsing-impl.h`, `native/http/Parsing-impl.h` | Exact POST request line before the existing `_hook`; original StageA bounds/deadline retained. |
| `host/normal_host.inc`, `native/src/boot/M9NormalStageA.cpp` | Opt-in HOST declaration, hook installation and retained-client service under the existing `httpBusy`. |
| `host/M3RB54Lab.inc` | Same socket context, one static M3-C Gate, STA/resource/OTA/journal admissions, release/wipe and unconditional final refusal. |
| `tests/lab.cpp` | Observations of actual byte counts, ownership and protected simulated flash regions; synthetic fault controls. |

The active B52Clock renderer, weather algorithms, LINK, clock, Digest, OTA,
4m2m linker and thresholds are not patched. The existing M3-C/R/BearSSL
headers are source-pinned and copied from this PR. Comparing them with the
old isolated lab revealed only one surplus final blank line in its BearSSL
copy; this lab uses the exact current Git source, with explicit LF pins.
No original pin or protected receipt was changed to hide that difference.

## Run locally or in CI

Supply a checkout of the exact public dependency; no automatic network or
device discovery is performed by the runner:

```text
python -B experiments/link_m3r_b54_handoff/run.py --source-review <public-checkout>/review --output <fresh-ignored-output>
```

Use a fresh output directory. The runner refuses overwrite, source drift,
inventory additions/removals, wrong M3 header identity, unexpected patch
paths, fuzzy contexts and wrong output hashes. Sources are materialized only
inside that output. Never run the old stock-Core patcher on this graph.

The existing single listener binds to loopback and executes the complete B5.4 app with
the genuine Core HTTP/Digest parser and Updater512/eboot sources; radio,
LCD, time, RTC and flash are explicitly HOST seams. All client endpoints
are numeric 127.0.0.1. Keys, network metadata and identities are synthetic.
There is no production key custody, device authority or display command.

The 19 handoff tests and 13 selected regressions are the original 32 cases,
adapted only for output/executable paths and POSIX compatibility. Four
additional tests cover exact patch context and negative source substitution.
Every suite must report its exact count with zero skips. Outputs include
source/build logs, observed counters, executable hashes and resource sections.

## Safety and interpretation

The extra hook is enabled only by `SHINO_M3R_B54_HOST_HANDOFF=1` in the
HOST runner; activating it outside HOST is a compile error. It never reads
the body before HMAC, never applies a mode, never commits a revision and
never emits a successful command ACK. Even VerifiedFrame returns 503.
Music, monitoring and clock override remain unimplemented commands.

PE/ELF sizes, static Gate size and socket counters describe this HOST
simulator and its instrumentation. They are not an ESP8266 firmware BIN,
native static-RAM budget, physical heap/block minimum, CONT margin or WDT
qualification. No firmware is built or installed by this workflow.

No SmallTV/VM access, OTA, serial, flash, reboot, deployed EXE, weather
activation, merge, retry of physical actions or protected-state cleanup.
