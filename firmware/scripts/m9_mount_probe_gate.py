"""Fail closed on deployment/FS targets; this environment builds applications only."""
from SCons.Script import COMMAND_LINE_TARGETS, Import
Import("env")
if any(target in {"upload", "uploadfs", "buildfs", "erase", "program"}
       or target.startswith("upload") for target in COMMAND_LINE_TARGETS):
    raise RuntimeError("Phase H is application-only OFFLINE; device/FS targets forbidden")
if env.subst("$PIOENV") != "esp12e_m9_4m2m_mount_probe":
    raise RuntimeError("Mount-probe gate attached to an unreviewed environment")
