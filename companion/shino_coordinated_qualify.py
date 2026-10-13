"""Coordinated read-only qualifier for FUTURE separately approved runs only.

Runs the existing exact B2 qualifier with a coordinated Digest reader. Optional
--b3-paced leaves a LINK window between GETs; B2 defaults remain unchanged. No
changes to frozen QUALIFY-B2.cmd, failed B2-readonly-receipt.json, or firmware.
Requires --authorize-read and a fresh, nonexisting --receipt from the caller;
otherwise inspect/read remains offline. Never retries failed HTTP requests.
"""
import argparse
from pathlib import Path
import sys

import shino_qualify
from shino_digest_coord import CoordinatedReader, HttpDiagnostics
from shino_update import Transport


B3_READ_GAP_SECONDS = 2.25
B3_HTTP_BOUND_MS = 1000


def coordinated_transport(identity, *, diagnostics=None, b3_paced=False):
    io = Transport(identity)
    io.reader = CoordinatedReader(io.reader, io.host, diagnostics=diagnostics,
                                  read_gap_seconds=B3_READ_GAP_SECONDS if b3_paced else 0)
    return io


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bin", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--identity", type=Path)
    parser.add_argument("--receipt", type=Path, required=True)
    parser.add_argument("--authorize-read", action="store_true")
    parser.add_argument("--b3-paced", action="store_true",
                        help="B3 only: 2.25s unlocked window between GETs; HOLD if a GET exceeds 1s")
    parser.add_argument("--http-diagnostics", action="store_true",
                        help="Include at most 64 sanitized HTTP timings and counters in the new receipt")
    args = parser.parse_args(argv)

    # Fail before identity, socket or receipt modification. Historical B2
    # receipt is not an allowable destination for this new wrapper.
    if args.receipt.name.casefold() in ("b2-readonly-receipt.json", "a2-readonly-receipt.json"):
        parser.error("Historical physical qualification receipts are immutable")
    arguments = ["--bin", str(args.bin), "--manifest", str(args.manifest),
                 "--receipt", str(args.receipt)]
    if args.identity is not None:
        arguments.extend(["--identity", str(args.identity)])
    if args.authorize_read:
        arguments.append("--authorize-read")

    diagnostics = HttpDiagnostics() if args.http_diagnostics else None
    original = shino_qualify.Transport
    original_read = shino_qualify.read_json
    original_qualify = shino_qualify.qualify

    def read(io, path, cycle):
        try:
            value = original_read(io, path, cycle)
        except shino_qualify.QualificationFailure:
            outcome = (io.reader.last_exchange or {}).get("outcome")
            if outcome in ("coordination_busy", "coordination_unavailable"):
                shino_qualify.fail(outcome.upper(), cycle, "GET " + path)
            raise
        elapsed = io.reader.last_exchange["http_under_lock_ms"]
        if args.b3_paced and elapsed > B3_HTTP_BOUND_MS:
            shino_qualify.fail("B3_HTTP_DURATION_OUT_OF_BOUNDS", cycle, "GET " + path,
                               observed_ms=round(elapsed, 3), maximum_ms=B3_HTTP_BOUND_MS)
        return value

    def qualify(*positional, **keywords):
        try:
            result = original_qualify(*positional, **keywords)
        except shino_qualify.QualificationFailure as error:
            if diagnostics is not None:
                error.diagnostic["windows_http"] = diagnostics.snapshot()
            raise
        if diagnostics is not None:
            result["windows_http"] = diagnostics.snapshot()
        if args.b3_paced:
            result["windows_pacing"] = dict(profile="B3_PACED", read_gap_ms=2250,
                                             maximum_get_ms=B3_HTTP_BOUND_MS)
        return result

    try:
        shino_qualify.Transport = lambda identity: coordinated_transport(
            identity, diagnostics=diagnostics, b3_paced=args.b3_paced)
        if args.b3_paced or args.http_diagnostics:
            shino_qualify.read_json = read
        shino_qualify.qualify = qualify
        return shino_qualify.main(arguments)
    finally:
        shino_qualify.Transport = original
        shino_qualify.read_json = original_read
        shino_qualify.qualify = original_qualify


if __name__ == "__main__":
    raise SystemExit(main())
