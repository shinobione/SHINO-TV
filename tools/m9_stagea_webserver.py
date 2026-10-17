"""Isolated Phase T raw-line handoff; ordinary StageA materialization unchanged."""
from pathlib import Path
import importlib.util
ROOT=Path(__file__).resolve().parents[1]

def materialize(core,destination):
    spec=importlib.util.spec_from_file_location('normal',ROOT/'firmware/scripts/m9_normal_webserver.py')
    normal=importlib.util.module_from_spec(spec);spec.loader.exec_module(normal)
    headers=normal.materialize(core,destination)
    header=headers/'ESP8266WebServer.h';text=header.read_text()
    text=normal.once(text,'  void handleClient();',
        '  void setStageARawHook(std::function<ClientFuture(const String&,ClientType*,uint32_t)> fn) { _stageARawHook=fn; }\n  void handleClient();')
    text=normal.once(text,'  HookFunction     _hook;',
        '  std::function<ClientFuture(const String&,ClientType*,uint32_t)> _stageARawHook;\n  HookFunction     _hook;')
    header.write_text(text,encoding='utf-8',newline='\n')
    parser=headers/'Parsing-impl.h';text=parser.read_text()
    text=normal.once(text,'  //reset header value',
        '  if(_stageARawHook) { auto result=_stageARawHook(req,&client,_stageAStarted);\n'
        '    if(result!=CLIENT_REQUEST_CAN_CONTINUE)return result; }\n  //reset header value')
    parser.write_text(text,encoding='utf-8',newline='\n')
    return headers
