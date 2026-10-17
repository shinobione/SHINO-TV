# SHINO // INSTALL (issue43)

**Offline delivery; NO-GO for installation.** The current StageA has no Wi-Fi
receiver. The small receiver prototype links, but its simultaneous native memory
floor is not established. The GUI Install/consent controls are disabled. Even
`--live` fails before a credential prompt or socket. No command bypass exists.

Windows: Python3.12+ with Tkinter, no third-party PC dependency. Double-click
`SHINO-INSTALL.cmd`, or run `py -3 companion/shino_install.py --gui` from the repo.
Choose BIN, choose its manifest, Verify offline. The GUI shows size, exact SHA256,
compatibility and the disabled installation result. The CLI fallback is:

```
py -3 companion/shino_install.py --bin <public-candidate.bin> --manifest <build.json>
```

This reads only the two selected files. It neither discovers devices nor reads
LINK config, stored credentials, backups or other BINs. Do not select private
files for agent/CI testing. The bundled tests generate public nonbootable images
and ephemeral maintenance credentials; no test secret is in a firmware graph.

Exact manifest schema (from an independently reviewed 4m2m build):

```
{"schema":1,"family":"SHINO-StageA","layout":"4m2m",
 "protocol":"shino-install-1","bytes":<exact integer>,
 "sha256":"<64 lowercase hex>","build_id":"<64 lowercase hex>"}
```

The BIN is validated for segment/checksum/CRC/length/DIO4MiB framing and exact
hash; the manifest states linker compatibility. A BIN by itself does not prove
the linker or production provenance. A local manifest plus password is not a
vendor RSA signature. Stock espota/ArduinoOTA senders are incompatible: this
small adaptation uses authenticated capabilities and fixed bounded TCP framing.

The future sender checks an expected16hex device identity, fresh client/server
nonces, HMAC-SHA256 and APP_ONLY/4m2m capability before AUTH/U_FLASH. The strong
distinct maintenance password is entered interactively, never stored or echoed.
There is one transfer, no automatic retry, and exact512B acknowledgements.
STAGED is **pending boot confirmation**, not success; only an authenticated
postboot build identity would confirm success. This delivery cannot run that
path because its release gate is false.

No physical candidate or initial installation is authorized. The first receiver
transition would require a separately approved exact image and proven method;
StageA cannot receive it over Wi-Fi today. Power loss during eboot copy has no
atomic rollback guarantee. See [qualification receipt](../docs/SHINO_WIFI_INSTALL_RESULT.md).
