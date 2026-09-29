"""Read pinned ESP8266 core source; optionally execute two exact source primitives.

The C++ harness injects the unmodified Stream::readStringUntil and WebServer
readBytesWithTimeout function text. Fake stream/client dependencies make this a
narrow primitive probe, never a full WebServer/parser/authentication test.
"""
from __future__ import annotations

import hashlib
import os
from pathlib import Path
import shutil
import subprocess
import tempfile


EXPECTED = {
    "libraries/ESP8266WebServer/src/Parsing-impl.h": "f8fe756b04222f20c49813ea63f0c8a90a99034255324de84349e32755afe818",
    "libraries/ESP8266WebServer/src/ESP8266WebServer-impl.h": "19934c7352eea30acb6d30ab6314d1b794fa5311d88fd3cdc7edaa6cdb7bb150",
    "libraries/ESP8266WebServer/src/ESP8266WebServer.h": "167b098fa4f964fc92ae9b89d531a69e3984561d4ca0729ab857f8f36d52dd67",
    "cores/esp8266/Stream.cpp": "17e4a13566a9c0fc70ae2cbbb095d4f382a4c02dc6c07d12233aa9385b63c810",
    "cores/esp8266/StreamSend.cpp": "fae1fdcfffbff6deb32741ebce574c579c0518b94afdd89082368ae5a776aba6",
    "cores/esp8266/WString.cpp": "f1138e424d7fa31d8ac14871e9e17aa3668cdef675dcc5c714a47dcabadd3c2d",
}


def core_root() -> Path:
    return Path(os.environ.get("V07_ESP8266_CORE", Path.home() / ".platformio" / "packages" / "framework-arduinoespressif8266"))


def pinned_sources(root: Path | None = None) -> dict[str, str]:
    root = root or core_root()
    if '"version": "3.30102.0"' not in (root / "package.json").read_text(encoding="utf-8"):
        raise ValueError("WRONG_CORE_VERSION")
    out = {}
    for relative, expected in EXPECTED.items():
        data = (root / relative).read_bytes()
        if hashlib.sha256(data).hexdigest() != expected:
            raise ValueError(f"WRONG_PINNED_SOURCE: {relative}")
        out[relative] = data.decode("utf-8")
    out["stream"] = out["cores/esp8266/Stream.cpp"]
    out["stream_send"] = out["cores/esp8266/StreamSend.cpp"]
    return out


def _between(value: str, start: str, end: str) -> str:
    return value[value.index(start):value.index(end, value.index(start))]


def harness(sources: dict[str, str]) -> str:
    stream = _between(sources["stream"], "String Stream::readStringUntil(char terminator) {", "// read what can be read")
    parser = sources["libraries/ESP8266WebServer/src/Parsing-impl.h"]
    helper = _between(parser, "template <typename ServerType>\nstatic bool readBytesWithTimeout", "template <typename ServerType>\ntypename ESP8266WebServerTemplate")
    return """
#include <cstddef>
#include <string>
#include <vector>
using String = std::string;
class Stream {
public:
    std::vector<int> input;
    std::size_t cursor = 0;
    int timedRead() { return cursor < input.size() ? input[cursor++] : -1; }
    String readStringUntil(char terminator);
};
struct S2Stream { explicit S2Stream(String&) {} };
struct FakeClient {
    std::size_t requested = 0;
    int timeout = 0;
    std::size_t sendSize(S2Stream&, std::size_t maxLength, int timeout_ms) {
        requested = maxLength; timeout = timeout_ms; return maxLength;
    }
};
struct FakeServer { using ClientType = FakeClient; };
namespace esp8266webserver {
""" + helper + "\n}\n" + stream + """
int main() {
    Stream line;
    line.input.assign(5000, 'x');
    line.input.push_back('\\r');
    if (line.readStringUntil('\\r').size() != 5000) return 1;
    String target;
    FakeClient client;
    if (!esp8266webserver::readBytesWithTimeout<FakeServer>(client, 1000000, target, 5000)) return 2;
    if (client.requested != 1000000 || client.timeout != 5000) return 3;
    return 0;
}
"""


def run_host_probe(sources: dict[str, str]) -> tuple[str, str]:
    compiler = shutil.which("g++") or shutil.which("clang++")
    if compiler is None:
        return "SKIPPED", "no host C++ compiler on PATH"
    with tempfile.TemporaryDirectory() as directory:
        source = Path(directory) / "v07_probe.cpp"
        binary = Path(directory) / ("v07_probe.exe" if os.name == "nt" else "v07_probe")
        source.write_text(harness(sources), encoding="utf-8")
        compiled = subprocess.run([compiler, "-std=c++17", str(source), "-o", str(binary)],
                                  capture_output=True, text=True, timeout=30)
        if compiled.returncode:
            return "FAILED", compiled.stderr[-1500:]
        executed = subprocess.run([str(binary)], capture_output=True, text=True, timeout=10)
        return ("PASS", "executed pinned source primitives") if executed.returncode == 0 else ("FAILED", f"exit {executed.returncode}: {executed.stderr[-500:]}")


def run_cross_syntax(sources: dict[str, str]) -> tuple[str, str]:
    """Compile syntax only for target ISA; never claim source execution."""
    compiler = Path.home() / ".platformio/packages/toolchain-xtensa/bin/xtensa-lx106-elf-g++.exe"
    if not compiler.is_file():
        return "SKIPPED", "pinned Xtensa cross compiler unavailable"
    with tempfile.TemporaryDirectory() as directory:
        source = Path(directory) / "v07_probe.cpp"
        source.write_text(harness(sources), encoding="utf-8")
        result = subprocess.run([str(compiler), "-std=c++17", "-fsyntax-only", str(source)],
                                capture_output=True, text=True, timeout=30)
        return ("PASS", "cross-compiled syntax only") if result.returncode == 0 else ("FAILED", result.stderr[-1500:])
