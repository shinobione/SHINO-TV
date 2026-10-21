# B5.4 / M3-R native INERT composition

Increment 4: link the actual pinned B5.4 StageA application, HTTP parser,
Updater512, clock, signed weather and M3-C/BearSSL on Xtensa. This is a
**compile/link feasibility laboratory**, never an owner firmware builder.

`prepare_native.py` reuses increment 3's closed public #72 source inventory
and exact six-file overlay. Only explicit HOST guards in derived copies are
mapped to a separate `SHINO_M3R_NATIVE_INERT=1` profile. Original HOST guards,
application sources, upstream Core installation and private artifacts stay intact.
Logger is pinned to the public #85 83a21d0 blobs. Core 3.1.2 package
3.30102.0, espressif8266 4.2.1, GCC 10.3 toolchain 2.100300.220621,
ArduinoJson 7.4.3 (pool 8), GFX 1.6.4 and AnimatedGIF 2.2.0.

The two environments differ only in `SHINO_M3R_NATIVE_HANDOFF=0/1`.
Synthetic identities/keys retain signed-weather crypto in the linked graph;
they convey no owner authority. `setup()` and `loop()` are empty. StageA is
retained only through an **uncalled** linker probe. No Wi-Fi task or production
main is included. The original handoff's unconditional 503 refusal and
single Gate/`httpBusy` remain unchanged: no display writer or command ACK.
The linked clock renderer is historical application code, never an M3 writer.

Device/debug/FS targets and the uploader callable fail closed. Never invoke
them to test: `test_inert_guard.py` executes the real guard against fake SCons.
The postbuild action changes BIN magic E9 to 00 and records before/after hashes.
Raw size is measured in memory, then only a nonbootable BIN is retained.
The ELF and nonbootable BIN are local laboratory artifacts, **not OTA inputs**;
CI publishes only JSON/logs. No hardware API is used by qualification scripts.

Example (fresh output required; compiler packages already installed):

```sh
python -B experiments/link_m3r_b54_native_inert/test_inert_guard.py
python -B experiments/link_m3r_b54_native_inert/prepare_native.py \
  --source-review /path/to/pinned-91969ace/review \
  --core ~/.platformio/packages/framework-arduinoespressif8266 \
  --output experiments/link_m3r_b54_native_inert/.build/fresh
pio run -d experiments/link_m3r_b54_native_inert/.build/fresh/project -e b54_inert_base
pio run -d experiments/link_m3r_b54_native_inert/.build/fresh/project -e b54_inert_handoff
python -B experiments/link_m3r_b54_native_inert/measure_native.py \
  --output experiments/link_m3r_b54_native_inert/.build/fresh
```

Optional `--dependency-cache` reuses public library **sources only**, never
compiled objects. The generated closed input manifest is checked before build.
`measure_native.py` checks actual ELF symbols, empty entry disassembly, RAM/IRAM,
linker boundaries, nonbootable BIN hashes and actual compiler `.su` frames.
No native code is executed. Runtime HTTP/Digest/HMAC/OTA regression evidence is
reused from increment 3's exact unchanged overlay; native builds prove linkage,
not runtime outcomes. Native heap/block/CONT/WDT remain **NON VÉRIFIÉ / HOLD**.

See [dated result](../../docs/B54_M3R_NATIVE_INERT_2026-10-20.md).
