"""Fresh public inert baseline from installed B5's Git source; no private files."""
import argparse
import json
import subprocess
from pathlib import Path
from shino_b5_lan_build import ROOT

SOURCE="8de4d4556f26d47b62b1f19a6b03216a12f7e718"


def build(directory):
    def old(path):return subprocess.check_output(["git","show",SOURCE+":"+path],cwd=ROOT).decode()
    namespace={"__file__":str(ROOT/"tools/shino_b5_lan_build.py"),"__name__":"b51_public_baseline"}
    exec(old("tools/shino_b5_lan_build.py"),namespace)
    directory,device,build_id=namespace["prepare"](Path(directory),private=False)
    for origin,target in (("ota/lan/B5Lan.cpp","src/boot/B5Lan.cpp"),("ota/lan/B5Lan.h","include/B5Lan.h")):
        (directory/target).write_text(old(origin),encoding="utf-8")
    namespace["prepare"]=lambda *args,**kwargs:(directory,device,build_id)
    result=namespace["build"](directory,private=False)
    result["baseline_firmware_source"]=SOURCE
    (directory/"report.json").write_text(json.dumps(result,indent=2)+"\n",encoding="utf-8")
    return result


if __name__=="__main__":
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument("directory",type=Path)
    build(parser.parse_args().directory)
