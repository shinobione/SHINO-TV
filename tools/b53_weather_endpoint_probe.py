"""Public B5.3 endpoint capability probe. GitHub runner only, NO device access.

Probe TLS1.2 MFLN=512, pin the exact committed trust anchor, and measure
an example Open-Meteo HTTP/1.1 response. Never assert native TLS memory.
"""
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import urllib.request

HOST="api.open-meteo.com"
URL=("https://api.open-meteo.com/v1/forecast?"
    "latitude=48.85&longitude=2.35&current=temperature_2m%2Cweather_code"
    "&temperature_unit=celsius&timezone=UTC")
ROOT=Path(__file__).resolve().parents[1]
CA_SOURCE=ROOT/"experiments/b53_autonomous/native/B53WeatherCA.h"
MAX_BODY=768

def pem_from_source():
    text=CA_SOURCE.read_text(encoding="ascii")
    match=re.search(r"-----BEGIN CERTIFICATE-----.*?-----END CERTIFICATE-----",
                    text,re.S)
    if not match: raise ValueError("Committed CA anchor missing")
    return match.group(0)+chr(10)

def probe():
    report={"scope":"PUBLIC_GITHUB_RUNNER_ONLY","host":HOST,
            "tls12_anchor_verified":False,"mfln512":"NON_VERIFIE",
            "http_status":None,"http_content_type":None,
            "http_content_length":None,"http_transfer_encoding":None,
            "body_bytes":None,"body_within_768":False,
            "source":"NO_SMALLTV_NETWORK","verdict":"NON_VERIFIE"}
    with tempfile.TemporaryDirectory() as d:
        ca=Path(d)/"anchor.pem"
        ca.write_text(pem_from_source(),encoding="ascii")
        cmd=["openssl","s_client","-connect",HOST+":443","-servername",HOST,
             "-tls1_2","-maxfraglen","512","-tlsextdebug",
             "-verify_return_error","-verify_hostname",HOST,
             "-CAfile",str(ca)]
        try:
            completed=subprocess.run(cmd,input=chr(10),text=True,capture_output=True,
                                     timeout=22,check=False)
        except (OSError,subprocess.TimeoutExpired) as ex:
            report["openssl_error"]=type(ex).__name__
        else:
            output=completed.stdout+chr(10)+completed.stderr
            report["openssl_exit"]=completed.returncode
            report["tls12_anchor_verified"]=(completed.returncode==0
                and "Verify return code: 0 (ok)" in output)
            # Count only server extension in received ServerHello; client
            # offering the extension is not evidence the server accepted it.
            accepted=re.search(r"TLS server extension.*max fragment length",
                               output,re.I)
            report["mfln512"]=("SUPPORTED" if accepted else "NOT_ADVERTISED"
                              if report["tls12_anchor_verified"] else "NON_VERIFIE")
            for line in output.splitlines():
                if "Verify return code:" in line:
                    report["openssl_verify_line"]=line.strip()[:120]
                    break
        try:
            req=urllib.request.Request(URL,headers={
                "Accept":"application/json","Accept-Encoding":"identity",
                "Connection":"close"},method="GET")
            with urllib.request.urlopen(req,timeout=15) as resp:
                data=resp.read(MAX_BODY+1)
                report["http_status"]=resp.status
                report["http_final_host"]=resp.url.split("/",3)[2]
                report["http_content_type"]=resp.headers.get("Content-Type")
                report["http_content_length"]=resp.headers.get("Content-Length")
                report["http_transfer_encoding"]=resp.headers.get("Transfer-Encoding")
                report["http_content_encoding"]=resp.headers.get("Content-Encoding")
                report["body_bytes"]=len(data)
                report["body_within_768"]=len(data)<=MAX_BODY
                if report["body_within_768"]:
                    payload=json.loads(data)
                    report["json_has_current_fields"]=(
                        "current" in payload and
                        "temperature_2m" in payload["current"] and
                        "weather_code" in payload["current"])
        except Exception as ex:
            report["http_error"]=type(ex).__name__
    chain=report["tls12_anchor_verified"]
    mfln=report["mfln512"]=="SUPPORTED"
    # The exact native build supports bounded fixed-length or strict
    # transfer-encoding: chunked (not both, never arbitrary encodings).
    fixed=(report["http_content_length"] is not None and
           report["http_transfer_encoding"] is None)
    chunked=(report["http_content_length"] is None and
             report["http_transfer_encoding"]=="chunked")
    report["framing"]=("FIXED" if fixed else "CHUNKED" if chunked else "UNSUPPORTED")
    response=(report["http_status"]==200 and
              report.get("http_final_host")==HOST and
              (fixed or chunked) and
              report.get("http_content_encoding") in (None,"identity") and
              bool(report["http_content_type"]) and
              "application/json" in report["http_content_type"] and
              report["body_within_768"] and
              report.get("json_has_current_fields",False))
    report["verdict"]=("PASS_ENDPOINT_PREREQUISITES" if chain and mfln and response
                       else "HOLD_ENDPOINT_PREREQUISITES")
    return report

if __name__=="__main__":
    result=probe()
    print(json.dumps(result,indent=2,sort_keys=True))
    path=os.getenv("GITHUB_STEP_SUMMARY")
    if path:
        with open(path,"a",encoding="utf-8") as f:
            f.write("## B5.3 Open-Meteo public endpoint probe"+chr(10)+chr(10))
            f.write("Result: **"+result["verdict"]+"**"+chr(10)+chr(10))
            f.write("Endpoint qualification does not prove ESP8266 TLS memory."+chr(10))
    sys.exit(0 if result["verdict"]=="PASS_ENDPOINT_PREREQUISITES" else 1)
