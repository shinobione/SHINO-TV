# B5.3 Autonomous Clock & Weather — isolated HOST foundation

## Scope

The installed B5.2 is retained without any modification. This isolated branch
starts at the exact B5.2 owner-source HEAD 2ae398dfa8cb5db789622e315930ef5701ce62c8.

The source-only HOST milestone implements bounded, allocation-free decisions:
- Prefer a fresh authenticated PC clock; fall back to an independently **verified**
  SNTP sample when the PC source expires; show no clock if neither is valid.
- Never infer weather, temperature, time, or GPU telemetry. Reject expired and
  out-of-range inputs. Clock lease: PC up to 120 s; SNTP up to 6 h after verified
  synchronization; weather up to 45 min after verified fetch.
- Fixed 240x240 geometry derived from the owner's Paint mock: discrete title,
  large center clock, compact weather row, four metric cards with bars.
- No sockets, file writes, flash, LittleFS, build identity or physical actions
  in the added runtime-free policy. No dynamic allocations.

Test:
```sh
g++ -std=c++17 -Wall -Wextra -Werror -pedantic \
  -Iexperiments/b53_autonomous/include \
  experiments/b53_autonomous/tests/test_b53_policy.cpp -o b53_host_test
./b53_host_test
```

## IMPORTANT — not yet a functioning B5.3 firmware

HOST policy and layout constants are proven by host compiler/tests only.
No SNTP network provider, HTTPS weather client, UI adapter integration,
ESP8266 PlatformIO firmware build, or private BIN has been produced by this
milestone. A CI PASS is never a physical PASS.

## Exact continuation for Codex (single isolated worktree)

1. Re-read this branch HEAD, clean worktree, open PRs, pinned toolchain and
   AGENTS.md/ROADMAP.md. Do not modify the installed B5.2 or the existing LINK
   Windows autostart. Keep B5.2 build generator and evidence reproducible.
2. Implement nonblocking ESP8266 SNTP provider (no legacy blocking NTPClient).
   Only admit a verified synchronization, use Europe/Paris DST rules without
   fixed UTC+1/+2 approximations, cap network and CPU work, prevent RTC/time
   spoofing from overriding a valid authenticated PC source. Protect across
   offline intervals, reconnect and millis wrap; never fabricate valid time.
3. Implement weather provider without an unbounded HTTPS/TLS allocation:
   exact host, bounded timeouts, fixed small payload, strict weather-code and
   temperature validation, stale indicator and bounded periodic refresh.
   Weather fetch must not overlap OTA, digest, clock or telemetry critical
   regions. If native heap/block/stack floors fail, HOLD weather only instead
   of dropping the OTA or security floors. No cleartext downgrade.
4. Integrate this policy into a distinct B5.3 generated graph with the existing
   B5.2 clock protocol and one HTTP owner, then update the 240x240 renderer
   using the owner's layout and exact single-line labels CPU/GPU/RAM/GPU temp.
   Keep 4 cards/bars when fresh; on PC disconnect show clock/weather only.
5. HOST tests for PC ON/OFF, no Wi-Fi, bad NTP/weather, wrong timezone, DST
   transitions, 49-day uptime/wrap, retry/backoff, boot without time,
   slow/stalled TLS, heap exhaustion, Digest/OTA/LittleFS regressions.
   Compile a PUBLIC INERT B5.3 and inspect actual .elf/.bin sizes and static
   RAM/stack call graph. Preserve original 4m2m linker and recovery.
6. Finish with a source-only report; private build and any OTA to SmallTV
   require a separate exact-candidate GO. No unverified sizes or CI claims.

Time/weather provider bounds must be enforced in actual native code; this
pure policy is not a substitute for such validation. The current logic uses
32-bit monotonic subtraction over short leases and expects continuous polling;
an additional native expiration latch is needed before 49-day unattended
wraparound can be certified.
