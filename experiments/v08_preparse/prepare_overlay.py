"""PlatformIO pre-build hook for the fingerprinted, local-only core overlay."""
from pathlib import Path
import sys

Import("env")  # supplied by PlatformIO/SCons

repo = Path(env["PROJECT_DIR"]).resolve().parents[1]
sys.path.insert(0, str(repo / "tools"))
from v08_native_overlay import materialize

overlay = Path(env["PROJECT_DIR"]) / ".pio" / "pinned_overlay"
materialize(overlay)
env.Append(CPPPATH=[str(overlay)])
