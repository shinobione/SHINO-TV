"""Exact reviewed B5.2 overlay projection for historical CI audits only.

No firmware mutation or authority. Immutable historical hashes are still checked
against the complete reconstructed predecessor. Unknown current text is refused.
"""
import hashlib
import subprocess

SCENE = "firmware/include/display/SceneEngine.h"
OLD_SCENE_SHA256_LF = 'd22e09b31225bf15ccce69e3753610864d04056a93baadc055f8c60ad8c8d413'
REVIEWED_SCENE_SHA256_LF = '443fee68eeb5841170c20140ba2bed1b4713daf79f5a58781820468d5ebfa8bd'
NEW_FILE_BLOBS = {'firmware/include/display/ClockFoundation.h': '9e6e12d829460e5f2e719076407413e07a5626b0',
 'companion/clock_sync.py': '21c4ab7e89e497aaf163b0c7e12d64fdb9dc9352',
 'companion/test_clock_freshness.py': '85c21b29de70db4772c2dced3d98d84354588381',
 'companion/test_clock_sync.py': 'acff21843767f449c7ff8f1e210e086f34eb1df5',
 'companion/test_clock_sync_deadline.py': '822f7ad563be1657865cfe4808684ee2c85d93b3'}
NEW_FIRMWARE_SHA256_LF = {"firmware/include/display/ClockFoundation.h": '820cbb9b23786550f526c170672de0a4019c664dc412b406ba24dd0731f394f8'}

# Seven inverse diff blocks from the owner-reviewed overlay, not a text wildcard.
SCENE_INVERSE = (('enum class ClockSource : uint8_t { Unknown, PairedPc };\n', ''),
 ('    ClockSource source = ClockSource::Unknown;\n'
  '    int16_t utcOffsetMinutes = 0;\n'
  '    uint32_t syncedMs = 0;\n',
  ''),
 ('    uint32_t revision = 0, stateSince = 0, clockMinute = 0, weatherMinute = 0, clockAgeMinute = '
  '0;\n',
  '    uint32_t revision = 0, stateSince = 0, clockMinute = 0, weatherMinute = 0;\n'),
 ('        const uint32_t clockAge = cf && clock.source == ClockSource::PairedPc ? '
  'uint32_t(now-clock.syncedMs)/60000 : 0;\n'
  '        if (cf != clockWasFresh || wf != weatherWasFresh || minute != clockMinute || weatherAge '
  '!= weatherMinute || clockAge != clockAgeMinute) {\n',
  '        if (cf != clockWasFresh || wf != weatherWasFresh || minute != clockMinute || weatherAge '
  '!= weatherMinute) {\n'),
 ('            clockAgeMinute = clockAge;\n', ''),
 ('            if (clock.synthetic || weather.synthetic) c.text(8,12,"SYNTHETIC PREVIEW '
  'DATA",LABEL);\n'
  '            else if (clock.source == ClockSource::PairedPc) {\n'
  '                char source[24];\n'
  '                const int offset = clock.utcOffsetMinutes;\n'
  '                const unsigned magnitude = unsigned(offset < 0 ? -offset : offset);\n'
  '                snprintf(source,sizeof source,"PC SYNC UTC%c%02u:%02u",offset < 0 ? \'-\' : '
  "'+',magnitude/60,magnitude%60);\n"
  '                c.text(8,12,clockFresh(now) ? source : "PC CLOCK EXPIRED",LABEL);\n'
  '            } else c.text(8,12,scene == Scene::Offline ? "PC OFFLINE" : "SHINO // TV",LABEL);\n',
  '            c.text(8, 12, (clock.synthetic || weather.synthetic) ? "SYNTHETIC PREVIEW DATA" :\n'
  '                   scene == Scene::Offline ? "PC OFFLINE" : "SHINO // TV", LABEL);\n'),
 ('            } else {\n'
  '                c.text(8, 97, weather.valid ? "WEATHER STALE / INVALID" : "WEATHER '
  'UNAVAILABLE", LABEL);\n'
  '                if (clockFresh(now) && clock.source == ClockSource::PairedPc) {\n'
  '                    char age[24];snprintf(age,sizeof age,"PC SYNC %lum",(unsigned '
  'long)(uint32_t(now-clock.syncedMs)/60000));\n'
  '                    c.text(8,109,age,LABEL);\n'
  '                }\n'
  '            }\n',
  '            } else c.text(8, 97, weather.valid ? "WEATHER STALE / INVALID" : "WEATHER '
  'UNAVAILABLE", LABEL);\n'))


class B52SourceDrift(AssertionError, ValueError):
    """Historical and current source checks both fail closed."""


def predecessor(path, text):
    if path != SCENE:
        return text
    current = hashlib.sha256(text.encode()).hexdigest()
    if current == OLD_SCENE_SHA256_LF:
        return text
    if current != REVIEWED_SCENE_SHA256_LF:
        raise B52SourceDrift("Unreviewed B5.2 scene mutation: " + path)
    for added, prior in SCENE_INVERSE:
        if text.count(added) != 1:
            raise B52SourceDrift("B5.2 inverse diff anchor changed")
        text = text.replace(added, prior, 1)
    if hashlib.sha256(text.encode()).hexdigest() != OLD_SCENE_SHA256_LF:
        raise B52SourceDrift("B5.2 predecessor differs from immutable identity")
    return text


def reviewed_new_firmware(root):
    current_scene = (root / SCENE).read_text(encoding="utf-8")
    is_overlay = hashlib.sha256(current_scene.encode()).hexdigest() == REVIEWED_SCENE_SHA256_LF
    found = {}
    for name, expected in NEW_FIRMWARE_SHA256_LF.items():
        path = root / name
        if not path.exists() and not is_overlay:
            continue
        if not path.is_file() or hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest() != expected:
            raise B52SourceDrift("Reviewed B5.2 added firmware source changed: " + name)
        found[name] = expected
    return found


def wifi_firmware_predecessor(root):
    """Prove the old Wi-Fi pair's exact firmware set, plus pinned B5.2 additions."""
    reference = "2b9ef75b4cf650277baae8da871ebe41f3227ddf"
    additions = reviewed_new_firmware(root)
    names = subprocess.check_output(["git", "ls-files", "firmware"], cwd=root, text=True).splitlines()
    checked = 0
    for name in names:
        if name in additions:
            continue  # Exact new header digest was already verified above.
        original = subprocess.check_output(["git", "show", reference + ":" + name], cwd=root)
        actual = (root / name).read_bytes().replace(b"\r\n", b"\n")
        if name == SCENE:
            actual = predecessor(name, actual.decode("utf-8")).encode("utf-8")
        if actual != original.replace(b"\r\n", b"\n"):
            raise B52SourceDrift("Wi-Fi historical firmware mutation: " + name)
        checked += 1
    return dict(reference=reference, historical_firmware_files_checked=checked,
                source_scope="PINNED_PREDECESSOR_PROJECTION_NOT_RAW_CURRENT_EQUALITY",
                reviewed_new_firmware_sha256_lf=additions)
