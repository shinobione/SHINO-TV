"""Fail closed on deployment/FS targets; this environment builds applications only."""
from SCons.Script import COMMAND_LINE_TARGETS, Import
Import("env")
if any(target in {"upload", "uploadfs", "buildfs", "erase", "program"}
       or target.startswith("upload") for target in COMMAND_LINE_TARGETS):
    raise RuntimeError("Phase H is application-only OFFLINE; device/FS targets forbidden")
if env.subst("$PIOENV") not in {"esp12e_m9_4m2m_mount_probe",
                              "esp12e_m9_4m2m_mount_probe_resources"}:
    raise RuntimeError("Mount-probe gate attached to an unreviewed environment")
flags = env.GetProjectOption("build_flags")
if isinstance(flags, str):
    flags = flags.split()
instrumented = "-DSHINO_M9_MOUNT_PROBE_RESOURCE_DIAGNOSTICS=1" in flags
if instrumented != (env.subst("$PIOENV") == "esp12e_m9_4m2m_mount_probe_resources"):
    raise RuntimeError("Resource observer flag/environment mismatch")
