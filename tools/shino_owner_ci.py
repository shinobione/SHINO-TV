"""CI builds the actual private transition graph with disposable random secrets.

Secrets stay in a git-ignored temporary directory and never appear in stdout,
CI artifact uploads or source commits. Pure offline build, no physical access.
"""
import hashlib
import json
import secrets
import shutil
import subprocess
import tempfile
from pathlib import Path

from m9_stagea_build import ROOT, ENV
from m9_signed_release import validate_image
from shino_owner_transition import OWNER, private_source, validate_owner
from shino_wifi_resources import one


def main():
    pio = shutil.which("pio") or shutil.which("platformio")
    if not pio:
        raise RuntimeError("Pinned PlatformIO required")
    OWNER.mkdir(parents=True, exist_ok=True)
    ephemeral = validate_owner({
        "device": secrets.token_hex(8),
        "build": secrets.token_hex(32),
        "ap_psk": secrets.token_urlsafe(24),
        "api_token": secrets.token_urlsafe(36),
        "digest_password": secrets.token_urlsafe(36),
        "maintenance_password": secrets.token_urlsafe(48),
    })
    with tempfile.TemporaryDirectory(prefix="ci-ephemeral-", dir=OWNER) as tmp:
        source = private_source(Path(tmp) / "owner-graph", ephemeral)
        log = Path(tmp) / "build-private.log"
        with log.open("w", encoding="utf-8") as sink:
            status = subprocess.run([pio, "run", "-d", str(source), "-e", ENV],
                                    cwd=ROOT, stdout=sink, stderr=subprocess.STDOUT,
                                    stdin=subprocess.DEVNULL, check=False, timeout=1200)
        if status.returncode:
            # Logs contain private build source and must remain temporary,
            # even though the credentials here are disposable fixtures.
            raise RuntimeError("Synthetic owner build failed (log withheld)")
        raw = (source / ".pio/build" / ENV / "firmware.bin").read_bytes()
        validate_image(raw)
        audit = one(source)
        assert audit["bin_bytes"] == len(raw)
        assert audit["noinit"] == 56
        src = (source / "src/boot/M9NormalStageA.cpp").read_text(encoding="utf-8")
        policy = (source / "include/shino_private_policy.h").read_text(encoding="utf-8")
        ini = (source / "platformio.ini").read_text(encoding="utf-8")
        assert "SHINO_OWNER_PRIVATE_TRANSITION=1" in ini
        assert "SHINO_PUBLIC_INERT_REVIEW=1" not in ini
        assert "PUBLIC_REVIEW_DRY_RUN_ONLY" not in src
        assert "if(!armGate.consume(p))return false;" in src
        assert "c={p.device,p.build,p.key,true,p.dryRun};return true;" in src
        assert ephemeral["ap_psk"] in policy
        assert ephemeral["digest_password"] in policy
        assert ephemeral["api_token"] in policy
        assert hashlib.sha256(ephemeral["maintenance_password"].encode()).hexdigest() in src
        assert ephemeral["maintenance_password"] not in src
        assert not any(value in json.dumps(audit) for value in (
            ephemeral["maintenance_password"], ephemeral["api_token"],
            ephemeral["digest_password"], ephemeral["ap_psk"]))
        print(json.dumps({
            "status": "SYNTHETIC_OWNER_PRIVATE_BUILD_PASS_OFFLINE",
            "bin_bytes": len(raw),
            "static_ram": audit["static_ram"],
            "noinit": audit["noinit"],
            "physical_memory": "NOT_MEASURED",
            "device_contacts": 0,
            "physical_flash_authorized": False,
        }, indent=2))


if __name__ == "__main__":
    main()
