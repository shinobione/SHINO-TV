"""Exact-source closure for LINK M1/M2, with immutable B5.2 LINK predecessor.

This module is imported ONLY by offline source-identity audits. It neither
relaxes historical guards nor carries any firmware/device/OTA authority.
Changing a single byte in a reviewed current blob fails closed. The change
to the pre-existing LINK worker is inverted and its *whole previous blob*
must match the owner-reviewed B5.2/PR49 Git identity.
"""

import hashlib

LINK_PATH = "companion/shino_link.py"
LINK_B52_PREDECESSOR_BLOB = "9552087d872ac838c12ac8924062d9f8da488183"
LINK_M2_REVIEWED_BLOB = "6ad2c4323df52132151a6a70ee2f86391efdff75"

# Only these explicitly reviewed PC-only files postdate Mission 9's historic
# source freeze. Every item is an exact Git blob, never a path/glob exemption.
LINK_M2_FILE_BLOBS = {
    "companion/link_display_modes.py": "a96caa150b642f8fecdc4c6d136bdafcb89b091a",
    "companion/test_link_display_modes.py": "5805bff7200d7364eeded0699a83e0dfc66741ca",
    "companion/link_mode_tray.py": "512d9dd603f604dda9b902dc84ceef5761399579",
    "companion/test_link_mode_tray.py": "4048018beab56dde9e220829b0e1753fb5935d06",
    LINK_PATH: LINK_M2_REVIEWED_BLOB,
}

# The two and ONLY two reviewed inverse diff blocks on shino_link.py.
# They were compared byte-for-byte against the exact PR49 predecessor
# on 17 October 2026. No code outside these two blocks may differ.
_LINK_INVERSE = (
    (
        '    from link_mode_tray import ModeTrayController, build_preview_menu, passive_link_signals\n'
        '    engine = make_engine(config, diagnostics=observe is not None, clock_b52_host=clock_b52_host)\n'
        '    # M2 is a HOST preview only. Do not add a second sender or device POST.\n'
        '    mode_controller = ModeTrayController(\n'
        '        lambda: passive_link_signals(engine, ttl_ms=METRICS_TTL_MS)\n'
        '    )\n',
        '    engine = make_engine(config, diagnostics=observe is not None, clock_b52_host=clock_b52_host)\n',
    ),
    (
        '    menu = build_preview_menu(\n'
        '        pystray, mode_controller, status_supplier=lambda: status["value"],\n'
        '        open_dashboard=open_dashboard, quit_app=quit_app,\n'
        '    )\n',
        '    menu = pystray.Menu(\n'
        '        pystray.MenuItem(lambda item: "State: " + status["value"],\n'
        '                         lambda icon_, item: None, enabled=False),\n'
        '        pystray.MenuItem("Open SHINO // TV", open_dashboard),\n'
        '        pystray.MenuItem("Exit SHINO // LINK", quit_app),\n'
        '    )\n',
    ),
)


class LinkSourceIdentityError(AssertionError):
    """Fail closed for unexpected current, added, or old LINK source bytes."""


def git_blob_sha1(data: bytes) -> str:
    """Compute exact Git blob object ID; no shell, external Git or network."""
    if type(data) is not bytes:
        raise TypeError("expected raw file bytes")
    return hashlib.sha1(
        b"blob " + str(len(data)).encode("ascii") + b"\0" + data
    ).hexdigest()


def reviewed_link_predecessor(current: bytes) -> bytes:
    """Accept ONLY reviewed current M2 LINK bytes and prove exact B5.2 base."""
    if type(current) is not bytes:
        raise TypeError("expected raw file bytes")
    if git_blob_sha1(current) != LINK_M2_REVIEWED_BLOB:
        raise LinkSourceIdentityError("Unreviewed M2 LINK current source")
    try:
        text = current.decode("utf-8")
    except UnicodeError as exc:
        raise LinkSourceIdentityError("Non-UTF8 M2 LINK source") from exc
    for addition, prior in _LINK_INVERSE:
        if text.count(addition) != 1:
            raise LinkSourceIdentityError("M2 LINK inverse anchor mismatch")
        text = text.replace(addition, prior, 1)
    previous = text.encode("utf-8")
    if git_blob_sha1(previous) != LINK_B52_PREDECESSOR_BLOB:
        raise LinkSourceIdentityError("M2 LINK does not preserve B5.2 predecessor")
    return previous
