"""StageA is offline application-only; reject all device/FS target variants."""
from SCons.Script import COMMAND_LINE_TARGETS, Import
Import("env")
for target in COMMAND_LINE_TARGETS:
    lowered = target.lower()
    if any(word in lowered for word in ("upload", "buildfs", "erase", "program")):
        raise RuntimeError("Phase N OFFLINE: device/filesystem targets forbidden")
if env.subst("$PIOENV") != "esp12e_m9_4m2m_normal_qualification":
    raise RuntimeError("Normal qualification environment mismatch")
flags = env.GetProjectOption("build_flags")
if isinstance(flags, str):
    flags = flags.split()
for key, value in (("SHINO_BOOT_PROFILE", "1"), ("SHINO_M9_NORMAL_QUALIFICATION", "1")):
    definitions = [flag for flag in flags if flag.startswith("-D" + key)]
    if definitions != ["-D" + key + "=" + value]:
        raise RuntimeError("Normal qualification exact flag mismatch: " + key)
if env.GetProjectOption("board_build.ldscript") != "eagle.flash.4m2m.ld":
    raise RuntimeError("Normal qualification requires the reviewed 4m2m linker")
