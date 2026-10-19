"""Exact #83 HOST overlay over immutable PR54 M2 and B5.2 source pins.

Two-way proof: exact Git blob of new files AND invert exact edits to the
unmodified 17 October M2 Git blobs. No wildcard or frozen-gate relaxation.
"""
from link_m2_source_identity import (
    LINK_M2_REVIEWED_BLOB, LINK_M2_FILE_BLOBS,
    LinkSourceIdentityError, git_blob_sha1,
)

LINK83_BLOBS = {
    "companion/link_firmware_identity.py": "e6732b96e26a59253bbca7f45da8c5f6060d3418",
    "companion/test_link_firmware_identity.py": "5ebe31694604ffb68b757254ae5a9292b58dbe6a",
    "companion/link_mode_tray.py": "fa20bc5951f7c21c1d924f64d0052fa983de7e3c",
    "companion/shino_link.py": "d21a5f715b9ad748af3d63ac5a471ebd480c0191",
}

LINK_PATCH = (
    ('    from link_firmware_identity import FirmwareMenuAction, read_firmware_identity\n', '', 1),
    ('    firmware_action = FirmwareMenuAction(lambda: read_firmware_identity(\n'
     '        engine.host, Path(config["credentials_file"]), config_path().parent,\n'
     '    ))\n', '', 1),
    ('        firmware_action.close()\n', '', 2),
    ('        firmware_action=firmware_action,\n', '', 1),
)

TRAY_PATCH = (
    ('                       status_supplier, open_dashboard, quit_app, firmware_action=None):',
     '                       status_supplier, open_dashboard, quit_app):', 1),
    ('    extra = ()\n'
     '    if firmware_action is not None:\n'
     '        from link_firmware_identity import LABEL\n'
     '        def trigger(icon_, item):\n'
     '            firmware_action.start(icon_)\n'
     '        details = tuple(pystray.MenuItem(\n'
     '            lambda item, field=field: firmware_action.line(field),\n'
     '            noop, enabled=False,\n'
     '        ) for field in (\n'
     '            "version", "build", "sha", "bytes", "checked", "ota",\n'
     '            "fs", "last_update",\n'
     '        ))\n'
     '        extra = (\n'
     '            pystray.MenuItem(LABEL, trigger,\n'
     '                enabled=lambda item: firmware_action.snapshot()["state"] != "READING"),\n'
     '            pystray.MenuItem("Identité lue (détails)",\n'
     '                pystray.Menu(*details)),\n'
     '        )\n'
     '\n', '', 1),
    ('        *extra,\n', '', 1),
)


def reviewed_m2_source(current, path):
    if type(current) is not bytes or path not in (
            "companion/link_mode_tray.py", "companion/shino_link.py"):
        raise LinkSourceIdentityError("Invalid #83 overlay input")
    if git_blob_sha1(current) != LINK83_BLOBS[path]:
        raise LinkSourceIdentityError("Unexpected #83 source blob")
    try:
        text = current.decode("utf-8")
    except UnicodeError as exc:
        raise LinkSourceIdentityError("Invalid UTF8 #83 source") from exc
    patches = LINK_PATCH if path.endswith("shino_link.py") else TRAY_PATCH
    for after, before, count in patches:
        if text.count(after) != count:
            raise LinkSourceIdentityError("Issue83 inverse anchor drift")
        text = text.replace(after, before, count)
    recovered = text.encode("utf-8")
    if git_blob_sha1(recovered) != LINK_M2_FILE_BLOBS[path]:
        raise LinkSourceIdentityError("Issue83 does not reproduce frozen M2 source")
    return recovered


def verify_added_blob(current, path):
    if path not in LINK83_BLOBS or git_blob_sha1(current) != LINK83_BLOBS[path]:
        raise LinkSourceIdentityError("Unexpected issue83 file")
    return True
