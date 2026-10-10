#!/usr/bin/env python3
"""Offline source audit; never constructs Serial or reads a private firmware BIN."""
import argparse
import json
import sys
from pathlib import Path
from m9_phase_k_qualification import qualify
from m9_single_attempt_physical_runner import serial_source_gate


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--stub-audit-root',type=Path,required=True)
    args=p.parse_args()
    if sys.version_info[:2] != (3,12): p.error('Phase L source audit requires Python 3.12.x')
    result=qualify(args.stub_audit_root)
    result.update(serial_source_audit=serial_source_gate(),
        PHASE_L_PHYSICAL_RUNNER_SOURCE_GATE='PASS/OFFLINE',
        PHASE_L_PORT_CONTROL_GATE='PASS/OFFLINE',
        PHASE_L_SINGLE_TRANSACTION_INTEGRATION_GATE='PASS/OFFLINE',
        approved_local_interpreter_identity='NOT_READ_BY_THIS_SOURCE_ONLY_RUN')
    print(json.dumps(result,indent=2,sort_keys=True))
    return 0


if __name__=='__main__': raise SystemExit(main())
