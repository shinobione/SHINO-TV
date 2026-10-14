"""Exact reviewed B5.2 overlay projection for historical CI audits only.

No firmware mutation or authority. Immutable historical hashes are still checked
against the complete reconstructed predecessor. Unknown current text is refused.
"""
import hashlib
import json
import subprocess

SCENE = "firmware/include/display/SceneEngine.h"
OLD_SCENE_SHA256_LF = 'd22e09b31225bf15ccce69e3753610864d04056a93baadc055f8c60ad8c8d413'
WIFI_MANIFEST_SHA256_LF = "dd7cf647ba1e26ab4aa1986fd1f2cc3c7d4d25d43f05e9de1aa67de9b0b1f995"
REVIEWED_SCENE_SHA256_LF = '443fee68eeb5841170c20140ba2bed1b4713daf79f5a58781820468d5ebfa8bd'
NEW_FILE_BLOBS = {'firmware/include/display/ClockFoundation.h': '9e6e12d829460e5f2e719076407413e07a5626b0',
 'companion/clock_sync.py': 'cb58144a7147c59a57c93a23b39f7833f7166361',
 'companion/test_clock_freshness.py': '85c21b29de70db4772c2dced3d98d84354588381',
 'companion/test_clock_sync.py': 'acff21843767f449c7ff8f1e210e086f34eb1df5',
 'companion/test_clock_sync_deadline.py': '822f7ad563be1657865cfe4808684ee2c85d93b3',
 # B5.2 LINK publisher: exact reviewed PR49 PC-only blobs, no source wildcard.
 'companion/link_clock.py': 'fa2e05e6b06146536f7e27a04723743966ff044a',
 'companion/shino_link.py': '9552087d872ac838c12ac8924062d9f8da488183',
 'companion/test_link_clock.py': 'a9c501b74a524ee0610b33af8463e4b54785576c',
 'companion/test_link_clock_loopback.py': 'e5b8d50f74f75a6aa1db2b509bd732c7f41c593d'}
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
    # The unchanged Phase O table was compared against every file at reference:
    # all 113 LF digests are identical. Pin the table itself so shallow-clone
    # operation never substitutes an unverified or edited historical manifest.
    raw = (root / "tools/m9_phase_o_sources.json").read_bytes().replace(b"\r\n", b"\n")
    if hashlib.sha256(raw).hexdigest() != WIFI_MANIFEST_SHA256_LF:
        raise B52SourceDrift("Immutable Wi-Fi historical pin manifest changed")
    historical = json.loads(raw)["firmware_sha256_lf"]
    names = subprocess.check_output(["git", "ls-files", "firmware"], cwd=root, text=True).splitlines()
    if set(names) != set(historical) | set(additions):
        raise B52SourceDrift("Unreviewed Wi-Fi firmware source set")
    for name, expected in historical.items():
        actual = (root / name).read_bytes().replace(b"\r\n", b"\n")
        if name == SCENE:
            actual = predecessor(name, actual.decode("utf-8")).encode("utf-8")
        if hashlib.sha256(actual).hexdigest() != expected:
            raise B52SourceDrift("Wi-Fi historical firmware mutation: " + name)
    return dict(reference=reference, historical_firmware_files_checked=len(historical),
                source_scope="PINNED_PREDECESSOR_PROJECTION_NOT_RAW_CURRENT_EQUALITY",
                reviewed_new_firmware_sha256_lf=additions)
