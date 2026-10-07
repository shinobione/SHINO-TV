"""Fail-closed historical projection for the narrow Phase-N additions.

Historical source pins remain immutable. This proves their reviewed predecessor
text, not raw current-file equality; Phase N separately pins/tests current code.
"""
import hashlib
import json
from pathlib import Path
import re
ROOT = Path(__file__).resolve().parent.parent
class PhaseNDrift(AssertionError, ValueError):
    """Both historical assertion gates and current data audits fail closed."""

def predecessor(path, text):
    pins = json.loads((ROOT/'tools/m9_phase_n_sources.json').read_text(encoding='utf-8'))
    if path not in pins['predecessor_sha256_lf']:
        return text
    digest = hashlib.sha256(text.encode()).hexdigest()
    if digest == pins['predecessor_sha256_lf'][path]:
        return text
    if digest != pins['current_sha256_lf'][path]:
        raise PhaseNDrift('Unreviewed Phase N source mutation: ' + path)
    if path.endswith('M9LittleFsMountProbe.cpp'):
        text = text.replace('#if SHINO_BOOT_PROFILE == 2 || SHINO_M9_NORMAL_QUALIFICATION == 1',
                            '#if SHINO_BOOT_PROFILE == 2')
    elif path.endswith('platformio.ini'):
        text = re.sub(r'\n; M9_PHASE_N_BEGIN\n.*?; M9_PHASE_N_END\n', '', text, flags=re.S)
    else:
        text = re.sub(r'// M9_PHASE_N_BEGIN\n.*?// M9_PHASE_N_END\n', '', text, flags=re.S)
    if hashlib.sha256(text.encode()).hexdigest() != pins['predecessor_sha256_lf'][path]:
        raise PhaseNDrift('Phase N predecessor projection differs: ' + path)
    return text
