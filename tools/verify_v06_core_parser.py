"""Verify exact pinned upstream ESP8266 Core 3.1.2 parser ordering (public SOURCE ONLY).

Expects a separate CI checkout of esp8266/Arduino tag 3.1.2 dereferenced to
commit 210897ef83305496947c4e73c937bab52a33cb48. Does not fetch/network,
touch a firmware binary, instantiate WebServer or access device/credentials.
"""
from pathlib import Path
import sys

PINNED_COMMIT = "210897ef83305496947c4e73c937bab52a33cb48"


def require(ok: bool, description: str) -> None:
    if not ok:
        raise AssertionError("PINNED_CORE_PARSER_GATE: " + description)


def verify(folder: Path) -> None:
    source = folder / "libraries" / "ESP8266WebServer" / "src"
    parsing = (source / "Parsing-impl.h").read_text(encoding="utf-8")
    impl = (source / "ESP8266WebServer-impl.h").read_text(encoding="utf-8")
    header = (source / "ESP8266WebServer.h").read_text(encoding="utf-8")
    handling = impl[impl.index("void ESP8266WebServerTemplate<ServerType>::handleClient()"):]
    require(handling.index("_parseRequest(_currentClient)") < handling.index("_handleRequest();"),
            "route handler must be after _parseRequest")
    request = parsing[parsing.index("::_parseRequest(ClientType& client)"):
                      parsing.index("void ESP8266WebServerTemplate<ServerType>::_parseArguments(")]
    require("contentLength = headerValue.toInt();" in request, "Content-Length parse changed")
    require('String plainBuf;' in request, "plain buffer missing")
    require("readBytesWithTimeout<ServerType>(client, contentLength, plainBuf, HTTP_MAX_POST_WAIT)" in request,
            "full advertised non-form POST read path changed")
    require(request.index("String plainBuf;") < request.index("readBytesWithTimeout<ServerType>") <
            request.index("arg.value = plainBuf;"),
            "plain body stored before later request dispatch")
    require("S2Stream dataStream(data);" in parsing and
            "client.sendSize(dataStream, maxLength, timeout_ms)" in parsing,
            "body reader memory path changed")
    require("HTTP_MAX_POST_WAIT 5000" in header, "POST wait bound changed")
    form = parsing[parsing.index("::_parseForm(ClientType& client"):
                   parsing.index("::_parseFormUploadAborted()")]
    require("new RequestArgument[WEBSERVER_MAX_POST_ARGS]" in form,
            "multipart arg allocation changed")
    require("_currentHandler->upload(*this, _currentUri, *_currentUpload)" in form,
            "upload callback path changed")
    print("PINNED CORE 3.1.2 PARSER GATE: PASS")
    print("Non-multipart POST body String is filled in _parseRequest BEFORE route _handleRequest.")
    print("Native music HTTP/media ingress remains NOT IMPLEMENTED and NOT INSTALL-APPROVED.")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("Usage: python tools/verify_v06_core_parser.py <pinned-source-checkout>")
    verify(Path(sys.argv[1]))
