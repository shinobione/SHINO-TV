"""Owner-only physical packet commands. Default is PRINT_ONLY, no subprocess.

One durable attempt per PRE/write/POST operation. Exact book SHA, candidate,
private reference flash fingerprint and fresh PRE are checked before COM access.
Codex prepares/tests this tool offline and must never use --execute on hardware.
"""
import argparse
import hashlib
import json
import os
import subprocess
from pathlib import Path


def regular(path):
    path=Path(path)
    if path.is_symlink() or not path.is_file():raise ValueError("Regular private file required")
    return path


def reserve(path):
    with Path(path).open("x",encoding="ascii") as out:
        out.write("ONE_PHYSICAL_ATTEMPT_NO_RETRY\n");out.flush();os.fsync(out.fileno())


def run(book,operation,expected_sha256,execute=False,owner_go=None,runner=subprocess.run):
    book=regular(book);root=book.resolve().parent
    if hashlib.sha256(book.read_bytes()).hexdigest()!=expected_sha256:raise ValueError("Exact packet command SHA required")
    data=json.loads(book.read_text(encoding="utf-8"));control=data["physical_control"]
    if operation not in ("pre","write","post"):raise ValueError("Unknown operation")
    marker=root/("UART-"+operation+".attempt")
    if marker.exists() or (root/"PHYSICAL-HOLD.marker").exists():raise ValueError("Previous physical attempt or unknown result: STOP, no retry")
    for name,sha in data["source_sha256_lf"].items():
        source=regular(root/control["helper_directory"]/name)
        if hashlib.sha256(source.read_bytes().replace(b"\r\n",b"\n")).hexdigest()!=sha:raise ValueError("Pinned private helper changed")
    argv=data[{"pre":"fresh_pre_argv","write":"writer_internal_argv","post":"fresh_post_argv"}[operation]]
    if not execute:return dict(status="PRINT_ONLY_NO_PORT_OPEN",operation=operation,physical_authorized=False,serial_io=0)
    if owner_go!=control["owner_go"][operation]:raise ValueError("Separate exact-operation owner GO required")
    candidate=regular(control["candidate"])
    if hashlib.sha256(candidate.read_bytes()).hexdigest()!=data["candidate_sha256"]:raise ValueError("Candidate SHA changed")
    if operation in ("pre","post"):
        output=Path(argv[-1])
        if output.resolve().parent!=root or output.is_symlink() or output.exists():raise ValueError("Readback output exists or is outside the new packet")
    if operation=="write":
        pre_receipt=root/"UART-pre-result.json"
        if not pre_receipt.is_file() or json.loads(pre_receipt.read_text())["completed"] is not True:
            raise ValueError("Fresh acknowledged PRE capture required before write")
        reference=control.get("reference")
        if not reference:raise ValueError("Private installed-device reference required")
        ref=regular(reference["path"]);pre=regular(data["fresh_pre_argv"][-1])
        if pre.resolve()==ref.resolve() or os.path.samefile(pre,ref):raise ValueError("Independent fresh PRE required")
        if ref.stat().st_size!=0x400000 or pre.stat().st_size!=0x400000:raise ValueError("Exact 4MiB reference and PRE required")
        original=ref.read_bytes();fresh=pre.read_bytes()
        if hashlib.sha256(original).hexdigest()!=reference["sha256"]:raise ValueError("Archived reference changed")
        size=reference["installed_bytes"]
        if hashlib.sha256(fresh[:size]).hexdigest()!=reference["installed_sha256"] or fresh[0x200000:]!=original[0x200000:]:
            raise ValueError("Wrong installed image or private device flash fingerprint: STOP before COM")
        # The failed historical OTA may have changed staging. Compare the
        # running private application and FS/SDK, not historical staging bytes.
        if "--execute" not in argv:raise ValueError("Bound single-attempt writer required")
    if operation=="post":
        receipt=root/"UART-write-result.json"
        if not receipt.is_file() or json.loads(receipt.read_text())["completed"] is not True:
            raise ValueError("No acknowledged write; stop physical sequence")
    reserve(marker) # Durable before any serial object or child process exists.
    try:
        result=runner(argv,capture_output=True,text=True,timeout=1200)
        complete=result.returncode==0
        if complete and operation in ("pre","post"):
            complete=regular(argv[-1]).stat().st_size==0x400000
    except (Exception,KeyboardInterrupt):complete=False
    receipt=dict(operation=operation,completed=complete,automatic_retries=0,
                 status="COMMAND_COMPLETED_PENDING_INDEPENDENT_VERIFICATION" if complete else "UNKNOWN_STOP_NO_RETRY")
    with (root/("UART-"+operation+"-result.json")).open("x",encoding="utf-8") as out:json.dump(receipt,out,indent=2)
    if not complete:
        reserve(root/"PHYSICAL-HOLD.marker")
        raise ValueError("Physical command failed or result unknown: STOP, no retry")
    return receipt


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__,allow_abbrev=False)
    parser.add_argument("book",type=Path);parser.add_argument("operation",choices=("pre","write","post"))
    parser.add_argument("--expected-sha256",required=True);parser.add_argument("--execute",action="store_true")
    parser.add_argument("--owner-go")
    args=parser.parse_args(argv)
    try:
        print(json.dumps(run(args.book,args.operation,args.expected_sha256,args.execute,args.owner_go)));return 0
    except (ValueError,OSError,KeyError):
        print("PACKET_STOP_NO_RETRY; no raw protocol or credential diagnostic");return 2


if __name__=="__main__":raise SystemExit(main())
