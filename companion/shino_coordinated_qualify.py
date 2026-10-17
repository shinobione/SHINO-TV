"""Coordinated read-only qualifier for FUTURE separately approved runs only.

Runs the existing exact B2 qualifier with a coordinated Digest reader. No
changes to frozen QUALIFY-B2.cmd, failed B2-readonly-receipt.json, or firmware.
Requires --authorize-read and a fresh, nonexisting --receipt from the caller;
otherwise inspect/read remains offline. Never retries failed HTTP requests.
"""
import argparse
from pathlib import Path
import sys

import shino_qualify
from shino_digest_coord import CoordinatedReader
from shino_update import Transport


def coordinated_transport(identity):
    io = Transport(identity)
    io.reader = CoordinatedReader(io.reader, io.host)
    return io


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bin", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--identity", type=Path)
    parser.add_argument("--receipt", type=Path, required=True)
    parser.add_argument("--authorize-read", action="store_true")
    args = parser.parse_args(argv)

    # Fail before identity, socket or receipt modification. Historical B2
    # receipt is not an allowable destination for this new wrapper.
    if args.receipt.name in ("B2-readonly-receipt.json", "A2-readonly-receipt.json"):
        parser.error("Historical physical qualification receipts are immutable")
    arguments = ["--bin", str(args.bin), "--manifest", str(args.manifest),
                 "--receipt", str(args.receipt)]
    if args.identity is not None:
        arguments.extend(["--identity", str(args.identity)])
    if args.authorize_read:
        arguments.append("--authorize-read")

    original = shino_qualify.Transport
    try:
        shino_qualify.Transport = coordinated_transport
        return shino_qualify.main(arguments)
    finally:
        shino_qualify.Transport = original


if __name__ == "__main__":
    raise SystemExit(main())
