# MUSIC V1 Windows follow: public source review

This is a source-only review checkpoint of completed Windows work from 26â€“27 October 2026. It is based on the published PR #85 dependency commit `1e27cec7b95c19fdc93651800f83524cb2583e93`. It does not replace the existing companion or firmware and contains no packaged MUSIC launcher, owner evidence, binary or credentials.

## Included

- Exact finished runtime sources for GSMTC selection/transitions, 64x64 indexed artwork encoding, the single telemetry worker, authenticated media transport, bounded sanitized diagnostics and the POST_ACK scheduling correction. Only line endings were normalized; `SOURCES.json` records original and published SHA-256 values.
- Existing tests selected from the original HOST qualification. Imports now use this directory and public companion dependencies. A HOST-only exception fixture replaces the unavailable private admission exception in fault injection; it grants no production authority.
- `display-admission-review.patch`: the exact existing decoupling changes for review against the private CLASSIFIED source predecessor. The owner-bound admission implementations and descriptors are deliberately excluded. This patch is not an operational integration into the PR #85 companion.

## Safety and limits

An authenticated accepted ACK must be validated before its deadline. All post-ACK proof guards/context exits remain mandatory. Only a timeout at the isolated final scheduler check, after those steps succeed, consumes the proven ACK once and yields/locks the current metrics slot. Late/lost/invalid ACK or failed proof remains UNKNOWN with no retry. ACK age uses its original validation timestamp.

The existing 0.25â€“1.5 s command budget, 6 s freshness, 7.5 s local transaction and 8 s native pending limits are unchanged. Long local IO can still overrun telemetry timing; tests expose that limitation rather than certify physical resource bounds.

The optional trace is OFF by default and retains the latest 64 events in a newly created run file, with fixed labels only. It excludes media content, identifiers, authentication and exception text. The new event `POST_ACK_BUDGET_EXHAUSTED` is distinct from `SEND_OUTCOME_UNKNOWN`.

Public runtime tests inject inert identities, fault guards and HTTP peers. No test may open a device socket. `production_lease()` and legacy display configuration still require the omitted owner-bound admission modules; no fallback or fabricated capability is supplied here. Do not use this review tree as an installation package.

## Reproduce HOST qualification

From the repository root, with Python 3.12 and Pillow installed:

```text
python -B -m unittest discover -s review/music_follow/tests -p "test_*.py" -v
```

The focused GitHub workflow runs this suite on Linux and Windows. No firmware/native build, VM, Wi-Fi, device read, OTA, installation or autostart operation belongs to this checkpoint.

See [the dated state record](../../docs/MUSIC_FOLLOW_SYNC_2026-11-03.md) for completed work, private dependencies and physical limitations. HOST PASS is not physical acceptance. Historical UNKNOWN and one-shot authorities remain unchanged and private.
