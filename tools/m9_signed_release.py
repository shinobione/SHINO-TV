"""Independent 4m2m signed release verifier. Offline; never signs or installs."""
import hashlib
import json
from pathlib import Path
import shutil
import struct
import subprocess
import tempfile

from m9_flash_layout import align_sector, FS_START, FS_END, LINKER_MAX_APP_BYTES
from m9_first_migration import esp8266_v1_image, arduino_crc

MIN_RAW = 64000
SIGNATURE_BYTES = 256


def geometry(current, raw):
    if type(current) is not int or type(raw) is not int or not MIN_RAW <= current <= LINKER_MAX_APP_BYTES or not MIN_RAW <= raw <= LINKER_MAX_APP_BYTES:
        raise ValueError("4m2m application size")
    transport = raw + SIGNATURE_BYTES + 4
    start = FS_START - align_sector(transport)
    if start < align_sector(current) + 4096:
        raise ValueError("4m2m signed staging overlap/guard")
    return dict(raw_bytes=raw, transport_bytes=transport, current_rounded=align_sector(current),
                transport_rounded=align_sector(transport), stage_start=start, stage_end=FS_START,
                filesystem_end=FS_END, guard_bytes=start-align_sector(current))


def validate_image(raw):
    if not MIN_RAW <= len(raw) <= LINKER_MAX_APP_BYTES:
        raise ValueError("4m2m raw size")
    boot, app = esp8266_v1_image(raw), esp8266_v1_image(raw, 0x1000)
    if boot["end_exclusive"] > 4096 or app["end_exclusive"] != len(raw):
        raise ValueError("eboot/application image framing")
    size, crc = struct.unpack_from("<II", raw, 0x1010)
    if size != len(raw) or crc != arduino_crc(raw):
        raise ValueError("Arduino image CRC")
    # Stronger segment bounds than historical plausibility checks. Memory-
    # mapped IROM must track its exact transport offset under this linker.
    for offset in (0, 0x1000):
        entry = struct.unpack_from("<I", raw, offset+4)[0]
        if not 0x40100000 <= entry < 0x4010C000:
            raise ValueError("IRAM entry")
        cursor, ranges = offset+8, []
        for _ in range(raw[offset+1]):
            address, count = struct.unpack_from("<II", raw, cursor)
            cursor += 8
            upper = next((hi for lo, hi in ((0x3FFE8000, 0x40000000),
                          (0x40100000, 0x4010C000), (0x40201010, 0x402FFFF0)) if lo <= address < hi), None)
            if upper is None or address+count > upper or address % 4 or count % 4:
                raise ValueError("segment/linker bounds")
            if address >= 0x40200000 and address != 0x40200000+cursor:
                raise ValueError("IROM mapped offset")
            if any(address < end and start < address+count for start, end in ranges):
                raise ValueError("overlapping segments")
            ranges.append((address, address+count))
            cursor += count
    return dict(boot=boot, application=app, crc_valid=True, binary_alone_proves_linker=False)


def openssl_path():
    found = shutil.which("openssl")
    if not found and Path("C:/Program Files/Git/usr/bin/openssl.exe").is_file():
        found = "C:/Program Files/Git/usr/bin/openssl.exe"
    if not found:
        raise ValueError("OpenSSL fixture verifier unavailable")
    return found


def verify(package, public_der, *, raw_sha256, key_sha256, package_sha256,
           current_bytes, linker="eagle.flash.4m2m.ld"):
    # Pins are independently selected caller input, never parsed from upload.
    for value in (raw_sha256, key_sha256, package_sha256):
        if len(value) != 64 or any(c not in "0123456789abcdef" for c in value):
            raise ValueError("independent SHA256 pin")
    if linker != "eagle.flash.4m2m.ld" or hashlib.sha256(public_der).hexdigest() != key_sha256:
        raise ValueError("independent public trust/linker")
    if not MIN_RAW+260 <= len(package) <= LINKER_MAX_APP_BYTES+260 or package[-4:] != struct.pack("<I", 256):
        raise ValueError("signed package/trailer size")
    raw = package[:-260]
    if hashlib.sha256(raw).hexdigest() != raw_sha256 or hashlib.sha256(package).hexdigest() != package_sha256:
        raise ValueError("independently selected release changed")
    layout, image = geometry(current_bytes, len(raw)), validate_image(raw)
    if not 64 <= len(public_der) <= 2048:
        raise ValueError("public key only")
    with tempfile.TemporaryDirectory(prefix="m9-public-verification-") as folder:
        p = Path(folder)
        (p/"public.der").write_bytes(public_der)
        (p/"raw.inert").write_bytes(raw)
        (p/"sig").write_bytes(package[-260:-4])
        tool = openssl_path()
        inspect = subprocess.run([tool,"pkey","-pubin","-inform","DER","-in",str(p/"public.der"),"-text","-noout"],capture_output=True,timeout=15)
        if inspect.returncode or b"(2048 bit)" not in inspect.stdout or b"Modulus:" not in inspect.stdout:
            raise ValueError("RSA2048 public key required")
        result = subprocess.run([tool,"dgst","-sha256","-keyform","DER","-verify",str(p/"public.der"),
                  "-signature",str(p/"sig"),str(p/"raw.inert")],capture_output=True,timeout=15)
        if result.returncode:
            raise ValueError("RSA2048 SHA256 signature")
    return dict(SIGNED_RELEASE_OFFLINE_GATE="PASS", raw_sha256=raw_sha256,
                package_sha256=package_sha256, key_sha256=key_sha256,
                geometry=layout, image=image, permission_to_flash=False, device_contacts=0)


if __name__ == "__main__":
    print(json.dumps(dict(mode="OFFLINE_LIBRARY_ONLY", permission_to_flash=False,
                         device_contacts=0, owner_files_read=0)))
