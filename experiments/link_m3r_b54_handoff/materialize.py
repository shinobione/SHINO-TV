"""Source-only B5.4 overlay. Never patches firmware/ or a global Core."""
import hashlib, json, re, shutil
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
PUBLIC_COMMIT = '91969aceb45e0c43d44f93a702a3997b57e8f89e'
MANIFEST_SHA = 'acbae479d51a6b119e9ec361ec93440b57b14c6a0ebae355bd2de64b820ea7e8'
TARGETS = {'host/M3RB54Lab.inc', 'host/normal_host.inc', 'host/Parsing-impl.h',
           'native/http/Parsing-impl.h', 'native/src/boot/M9NormalStageA.cpp', 'tests/lab.cpp'}

def sha(raw):
    return hashlib.sha256(raw).hexdigest()

def lf(path):
    path = Path(path)
    if path.is_symlink():
        raise ValueError('Source symlink refused')
    return path.read_bytes().replace(b'\r\n', b'\n')

def apply_exact(before, patch):
    """Strict, single-file unified diff; no fuzz, offset search or path writes."""
    old = before.decode('utf-8').splitlines(True)
    out, at = [], 0
    lines = patch.splitlines(True)
    n = 0
    while n < len(lines):
        match = re.fullmatch(r'@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@[^\n]*\n', lines[n])
        if not match:
            raise ValueError('Invalid unified hunk')
        start = max(0, int(match[1]) - 1)
        old_count, new_count = int(match[2] or 1), int(match[4] or 1)
        if start < at or start > len(old):
            raise ValueError('Invalid hunk bounds')
        out.extend(old[at:start]); at = start
        consumed = produced = 0
        n += 1
        while n < len(lines) and not lines[n].startswith('@@ '):
            line = lines[n]
            if line.startswith((' ', '-')):
                if at >= len(old) or old[at] != line[1:]:
                    raise ValueError('Patch context mismatch')
                at += 1; consumed += 1
            if line.startswith((' ', '+')):
                out.append(line[1:]); produced += 1
            elif not line.startswith('-'):
                raise ValueError('Unsupported patch control')
            n += 1
        if (consumed, produced) != (old_count, new_count):
            raise ValueError('Hunk count mismatch')
    out.extend(old[at:])
    return ''.join(out).encode('utf-8')

def patch_sections(text):
    sections = {}
    chunks = re.split(r'(?m)^--- a/', text)
    if chunks[0]:
        raise ValueError('Unexpected patch preamble')
    for chunk in chunks[1:]:
        name, plus, hunks = chunk.split('\n', 2)
        if name not in TARGETS or name in sections or plus != '+++ b/' + name:
            raise ValueError('Unapproved/duplicate patch path')
        sections[name] = hunks
    if set(sections) != TARGETS:
        raise ValueError('Incomplete overlay')
    return sections

def prepare(source, output):
    source, output = Path(source).resolve(), Path(output).resolve()
    if output.exists():
        raise ValueError('Fresh laboratory output required; never overwrite')
    manifest_raw = lf(source / 'SOURCES.json')
    if sha(manifest_raw) != MANIFEST_SHA:
        raise ValueError('B5.4 manifest identity mismatch')
    manifest = json.loads(manifest_raw)['files']
    actual = {p.relative_to(source).as_posix() for p in source.rglob('*')
              if p.is_file() and '.build' not in p.relative_to(source).parts
              and '__pycache__' not in p.relative_to(source).parts and p.name != 'SOURCES.json'}
    if actual != set(manifest):
        raise ValueError('B5.4 closed inventory mismatch')
    for name, pin in manifest.items():
        raw = lf(source / name)
        if sha(raw) != pin['sha256'] or len(raw) != pin['bytes']:
            raise ValueError('B5.4 source drift: ' + name)
    pins = json.loads((HERE / 'PINS.json').read_text())
    expected_m3={'experiments/link_m3r_single_parser/M3RSingleParser.h',
                 'experiments/link_m3c_crypto/M3CAuthenticatedIngress.h',
                 'experiments/link_m3c_crypto/M3CBearSslCrypto.h'}
    if set(pins['m3_headers'])!=expected_m3 or pins['source_commit']!=PUBLIC_COMMIT:
        raise ValueError('M3/dependency manifest substitution refused')
    patch = lf(HERE / 'overlay.patch')
    if sha(patch) != pins['overlay_sha256']:
        raise ValueError('Overlay drift')
    identities_raw = lf(HERE / 'overlay-identities.json')
    if sha(identities_raw) != pins['identities_sha256']:
        raise ValueError('Overlay identities drift')
    identities = json.loads(identities_raw)
    if set(identities) != TARGETS:
        raise ValueError('Overlay target mismatch')
    sections = patch_sections(patch.decode())
    # All checks precede copying. Dependency metadata/receipts never enter the lab.
    m3 = {}
    for name, pin in pins['m3_headers'].items():
        raw = lf(REPO / name)
        if sha(raw) != pin:
            raise ValueError('Existing M3 component drift: ' + name)
        m3[name] = raw
    for area in ('base', 'patched'):
        root = output / area
        for name in (*manifest, 'SOURCES.json'):
            dest = root / name
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(lf(source / name))
        for name, raw in m3.items():
            dest = root / name
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(raw)
    for name, hunk in sections.items():
        path = output / 'patched' / name
        pin = identities[name]
        before = path.read_bytes() if path.exists() else b''
        if (sha(before) if path.exists() else None) != pin['before']:
            raise ValueError('Overlay base mismatch: ' + name)
        after = apply_exact(before, hunk)
        if sha(after) != pin['after'] or len(after) != pin['bytes']:
            raise ValueError('Overlay result mismatch: ' + name)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(after)
    for area in ('base', 'patched'):
        root = output / area
        expected = set(manifest) | {'SOURCES.json'} | set(m3)
        if area == 'patched': expected |= TARGETS
        if {p.relative_to(root).as_posix() for p in root.rglob('*') if p.is_file()} != expected:
            raise ValueError('Materialized inventory mismatch')
        for name, pin in manifest.items():
            expected_sha = identities[name]['after'] if area == 'patched' and name in identities else pin['sha256']
            if sha(lf(root/name)) != expected_sha:
                raise ValueError('Materialized source mismatch: ' + name)
    receipt = dict(source_commit=PUBLIC_COMMIT, source_manifest=MANIFEST_SHA,
                   base_files=len(manifest), overlay=identities, m3_headers=pins['m3_headers'],
                   scope='HOST_ONLY_NO_DISPLAY_WRITER_NO_DEVICE_AUTHORITY')
    (output / 'source-receipt.json').write_text(json.dumps(receipt, indent=2))
    return receipt
