"""Closed inventory of public source bytes; no private Git history or artifact needed."""
import hashlib,json
from pathlib import Path
ROOT=Path(__file__).resolve().parent
FORBIDDEN={'.bin','.elf','.exe','.dll','.o','.obj','.a','.zip','.pem','.key','.attempt'}
def verify(root=ROOT):
 root=Path(root);manifest=json.loads((root/'SOURCES.json').read_text(encoding='utf-8'))
 expected=manifest['files'];actual={p.relative_to(root).as_posix() for p in root.rglob('*') if p.is_file() and '.build' not in p.relative_to(root).parts and '__pycache__' not in p.relative_to(root).parts and p.name!='SOURCES.json'}
 if actual!=set(expected):raise ValueError('Public source inventory mismatch')
 for name,pin in expected.items():
  p=root/name
  if p.is_symlink() or p.suffix.lower() in FORBIDDEN:raise ValueError('Disallowed public artifact')
  raw=p.read_bytes().replace(b'\r\n',b'\n')
  if len(raw)!=pin['bytes'] or hashlib.sha256(raw).hexdigest()!=pin['sha256']:raise ValueError('Public source content drift: '+name)
 return manifest
if __name__=='__main__':print(json.dumps(dict(status='PASS_PUBLIC_SOURCE_INVENTORY',files=len(verify()['files']))))
