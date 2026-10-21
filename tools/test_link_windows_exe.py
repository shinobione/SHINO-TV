"""Run the actual Windows EXE with no Python on PATH; isolated profiles only.

python tools/test_link_windows_exe.py --exe <path> --output <new folder>
No live configuration, registry writes, SmallTV or VM. Native dialogs are
inspected/dismissed only for the exact child process tree created by this test.
"""
import argparse
import ctypes
from ctypes import wintypes
import hashlib
import json
import os
from pathlib import Path
import struct
import subprocess
import sys
import time


def close_own_dialog(process, expected, timeout=20):
    import psutil
    api=ctypes.windll.user32
    api.GetWindowTextW.argtypes=[wintypes.HWND,wintypes.LPWSTR,ctypes.c_int]
    api.GetWindowTextLengthW.argtypes=[wintypes.HWND]
    api.GetWindowThreadProcessId.argtypes=[wintypes.HWND,ctypes.POINTER(wintypes.DWORD)]
    api.GetDlgItem.argtypes=[wintypes.HWND,ctypes.c_int]
    api.GetDlgItem.restype=wintypes.HWND
    api.SendMessageW.argtypes=[wintypes.HWND,wintypes.UINT,wintypes.WPARAM,wintypes.LPARAM]
    api.PostMessageW.argtypes=[wintypes.HWND,wintypes.UINT,wintypes.WPARAM,wintypes.LPARAM]
    api.EnumChildWindows.argtypes=[wintypes.HWND,ctypes.c_void_p,wintypes.LPARAM]
    callback_type=ctypes.WINFUNCTYPE(wintypes.BOOL,wintypes.HWND,wintypes.LPARAM)
    found=[]
    def text(hwnd):
        size=api.GetWindowTextLengthW(hwnd)
        buffer=ctypes.create_unicode_buffer(size+1)
        api.GetWindowTextW(hwnd,buffer,size+1)
        return buffer.value
    deadline=time.monotonic()+timeout
    while time.monotonic()<deadline:
        try: pids={process.pid,*[p.pid for p in psutil.Process(process.pid).children(recursive=True)]}
        except psutil.NoSuchProcess: pids={process.pid}
        def inspect(hwnd,_):
            pid=wintypes.DWORD()
            api.GetWindowThreadProcessId(hwnd,ctypes.byref(pid))
            if pid.value not in pids or text(hwnd)!='SHINO // LINK V1': return True
            contents=[]
            def child(child_hwnd,_):
                contents.append(text(child_hwnd)); return True
            callback=callback_type(child)
            api.EnumChildWindows(hwnd,callback,0)
            contents='\n'.join(contents)
            if expected in contents:
                found.append(contents)
                api.PostMessageW(hwnd,0x10,0,0)  # WM_CLOSE, this child only.
            return True
        callback=callback_type(inspect)
        api.EnumWindows(callback,0)
        if found: return True
        if process.poll() is not None: break
        time.sleep(.05)
    raise AssertionError('Expected child dialog did not appear')


def main():
    parser=argparse.ArgumentParser(__doc__)
    parser.add_argument('--exe',required=True,type=Path)
    parser.add_argument('--output',required=True,type=Path)
    args=parser.parse_args()
    exe=args.exe.resolve()
    output=args.output.resolve()
    output.mkdir(parents=True,exist_ok=False)
    checks={}
    data=exe.read_bytes()
    pe=struct.unpack_from('<I',data,0x3c)[0]
    checks['pe_windows_gui_subsystem']=struct.unpack_from('<H',data,pe+24+68)[0]==2
    checks['pe_x64']=struct.unpack_from('<H',data,pe+4)[0]==0x8664
    # A copied standalone EXE in a path with spaces, no sibling library/source.
    copied=output/'Standalone with spaces'
    copied.mkdir()
    standalone=copied/'SHINO-LINK.exe'
    standalone.write_bytes(data)
    environment=dict(os.environ)
    environment['PATH']=os.environ['SystemRoot']+'\\System32'
    for key in ('PYTHONPATH','PYTHONHOME','VIRTUAL_ENV'):
        environment.pop(key,None)
    environment['PYINSTALLER_RESET_ENVIRONMENT']='1'

    smoke=output/'FROZEN-SMOKE.json'
    run=subprocess.run([str(standalone),'--self-test',str(smoke)],cwd=copied,env=environment,
                       timeout=65,creationflags=subprocess.CREATE_NO_WINDOW)
    checks['real_frozen_smoke']=run.returncode==0 and json.loads(smoke.read_text())['verdict']=='PASS'

    for name,arguments,expected in (
        ('missing-config',[],'configuration locale'),
        ('bad-options',['--not-an-option'],'Options invalides'),
        ('missing-credentials',[],'configuration locale'),
    ):
        profile=output/name
        profile.mkdir()
        environment['LOCALAPPDATA']=str(profile)
        if name=='missing-credentials':
            cfg=profile/'SHINO-TV'
            cfg.mkdir()
            (cfg/'link.json').write_text(json.dumps(dict(schema=1,host='192.168.1.70',
                credentials_file=str(profile/'not-present.txt'))))
        process=subprocess.Popen([str(standalone),*arguments],env=environment,cwd=copied,
                                  creationflags=subprocess.CREATE_NO_WINDOW)
        try:
            checks[name+'_native_dialog']=close_own_dialog(process,expected)
            checks[name+'_exit']=process.wait(timeout=15)==(2 if name=='bad-options' else 1)
        finally:
            if process.poll() is None:
                # Terminate only a failing test process started above.
                import psutil
                for child in psutil.Process(process.pid).children(recursive=True): child.terminate()
                process.terminate()
                process.wait(timeout=10)
    result=dict(verdict='PASS' if all(checks.values()) else 'FAIL',checks=checks,
                sha256=hashlib.sha256(data).hexdigest(),bytes=len(data),
                scope='REAL_WINDOWS_EXE_OFFLINE_ONLY',owner_desktop_smoke='NOT_RUN')
    (output/'EXE-TESTS.json').write_text(json.dumps(result,indent=2))
    print(json.dumps(result,indent=2))
    return 0 if result['verdict']=='PASS' else 1


if __name__=='__main__': raise SystemExit(main())
