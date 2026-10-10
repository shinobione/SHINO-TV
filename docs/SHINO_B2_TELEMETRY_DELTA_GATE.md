# SHINO // TV — B2 telemetry stack candidate gate (public, offline)

**Starting evidence.** GitHub Actions run \`38089232890\` on public HEAD
\`bd4519e8979de05319fea104df157b4d25442961\`, artifact
\`11684050916\`, compiled \`ota/firmware/Normal.cpp\` with source SHA
\`bd20e294427a381a5833da52763b76b8e193a0bfd3625c917e2bf753430d83fd\`.
Measured \`telemetry()\` frame: **224 B**; \`identity()\` 160 B,
\`status()\` 96 B, \`metrics()\` 112 B. Public build static RAM **43,496 B**,
image **407,712 B**. These are baseline-only compiler artifacts, **not the
private B2 binary, not its physical memory**, and should not be conflated.

## Candidate review contract

\`tools/shino_telemetry_stack_delta.py\` compares a newly built **public** candidate
stack and build report with an immutable baseline JSON stored in
\`tools/fixtures\`. It fails closed if the compiled \`telemetry()\` frame
is missing/dynamic/not smaller than 224 B; if protected normal/OTA frames
regress; if static RAM grows by more than a proposed 256 B budget; if
4m2m/flash symbols, 4096 B Updater buffer, 56 B noinit, stack-free
floor 2048, historical stack watermark semantics or device isolation
change. It does **not** change the thresholds or erase history.

Run **only after generating a candidate public build**:

\`python tools/shino_telemetry_stack_delta.py --stack-report <candidate-public-http-ota-normal-stack.json> --build-report <candidate-public-http-ota-build.json>\`

The unchanged B2 baseline produces \`CANDIDATE_HOLD\` (zero improvement).
A synthetic 144-B candidate passes the checker in unit tests with an
80-B **compiled frame delta** only, not 80 B proven physical stack recovery.

## Engineering hypothesis (NOT yet implemented)

A later firmware proposal may move temporary \`JsonDocument\` and error
\`String\` objects in the \`POST /api/v1/bridge/metrics\` handler outside the
continuation stack, provided a single-owner / reentrancy-guarded scratch
workspace preserves the exact Digest, payload bounds, parser lifetime,
application validation, RAM-only metrics and error responses. This can increase
static RAM and/or heap; monitor both, preserve normal HTTP and OTA tests, and
reject if the compiler shows no actual reduction.

**Scope:** No firmware edit, B3 build or private image is part of this
preparatory gate. Installed B2 and all PRE/POST, failed qualifications, OTA
receipts and attempt markers remain untouched. A compiler PASS is **not**
physical qualification or authorization for another OTA.
