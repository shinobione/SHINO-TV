# PCB photo assessment 01 — owner SmallTV-Ultra (2026-09-26)

**Evidence:** four owner-provided exterior/open-board photographs in the SHINO-TV conversation. **Do not copy original photos into public Git** (they contain a visible board sticker/contact detail); this file records only nonidentifying technical observations. This is a visual inspection, not a continuity measurement or pinout certification.

## Observable on the unit

- Purple PCB, screen/display assembly connected with a flat flexible cable and white FPC connector.
- Back side has a shielded Wi-Fi module visibly of the ESP-12/ESP8266 class with PCB antenna; actual sub-model/flash-chip capacity and module marking are not yet read confidently.
- Six through-hole pads in a horizontal row beside the screen/module area, visible from both faces. **No TX/RX/GND/3V3/BOOT labels readable** in supplied photos. This is a candidate manufacturing/programming header, not yet identified as UART.
- USB-C socket mounted on the lower end; whether it exposes USB data/serial or is for power only has not been established.
- Three-pin regulator package near module on reverse, visually consistent with AMS1117-class package; marking and actual output voltage still to verify.
- PCB silkscreen `0229`; possible manufacturing/revision marker, but its meaning is unknown.
- Display flex and back label are visible. No determination of its exact model/pinout from these photographs alone.
- Factory firmware was previously reported by the running device as `SmallTV-Ultra / Ultra-V9.0.44` through read-only `/v.json`.

## Do NOT infer from photos

- Exact order of the six pads, whether every pad is connected, or whether they provide 3V3/GND/TX/RX/EN/GPIO0.
- Flash capacity: 4 MiB is a community-board assumption, not verified on this actual chip.
- Whether the USB-C connector provides USB-UART or data lines.
- That regulator input/output/pad numbering can be safely identified without tracing/measurements.
- That the owner already has a suitable 3.3V TTL converter or multimeter.

## Safe next evidence

1. With USB unplugged, take one sharply focused, high-resolution straight-on close-up of the **six holes on each face**, and a close-up of the module/regulator markings. Do not move/remove the FPC latch just for a photograph.
2. Ask owner whether a USB-C connection to Windows ever creates a new COM/serial device; this is observational only. If testing, insulate and secure the exposed PCB first, with the flat cable unstressed.
3. Record available multimeter and the precise USB-UART adapter model/voltage-jumper arrangement. A multimeter **with power disconnected** can identify a likely common ground by continuity (e.g., ground plane/USB shield), but a candidate must be independently cross-checked; one photo alone is not a wiring diagram.
4. Review Times-Z's original pinout photo and compare only after pad orientation is clear; its author's board/revision may differ.
5. Only after ground, boot signal, RX/TX, logic voltage, and power topology are positively identified should the owner be given tailored serial/read-flash instructions.

## Safety posture

**NO-GO** for wiring or flashing right now. No evidence of ROM bootloader access or full flash backup yet. Do not attach 5V UART outputs, use two power supplies concurrently, or probe bare exposed PCB while energized with unsecured leads. The six-pad row is a *candidate* programming interface, not a proven one.

Sources:
- Owner's photographs (conversation, not reproduced).
- Times-Z readback guide: https://github.com/Times-Z/GeekMagic-Open-Firmware/blob/a0c2ddcef4e76fa6eb040f6f544124763a2d85f5/backup/readme.md
- Espressif ESP8266 serial and boot mode reference: https://docs.espressif.com/projects/esptool/en/latest/esp8266/esptool/serial-connection.html
