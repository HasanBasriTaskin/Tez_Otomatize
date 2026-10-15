"""Check packaged tray+bridge with an isolated project and application settings."""
import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT));sys.path.insert(0,str(ROOT/'scripts'))
from installer import ensure_stopped
from literature.protocol import write_frame,read_frame
from literature.runtime import product
import importlib.util
spec=importlib.util.spec_from_file_location('native_smoke',ROOT/'scripts/native-smoke.py')
smoke=importlib.util.module_from_spec(spec);spec.loader.exec_module(smoke)


def main():
    ensure_stopped()
    with tempfile.TemporaryDirectory(dir=ROOT/'.tmp') as folder:
        scratch=Path(folder);env=dict(os.environ,LOCALAPPDATA=str(scratch/'local'))
        package=ROOT/'release/LiteraturKayit-0.3.0/payload'
        project=scratch/'project';project.mkdir()
        tray=subprocess.Popen([str(package/'tray/LiteraturKayit.exe'),'--project',str(project)],env=env)
        bridge=None
        try:
            time.sleep(2)
            assert tray.poll() is None,'Tray exited on startup'
            bridge=subprocess.Popen([str(package/'host/NativeHost.exe'),'chrome-extension://'+product()['extension_id']+'/','--parent-window=0'],
                                    stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,env=env)
            for identity,kind,payload in [('hi','hello',{'role':'worker','profile':'frozen-smoke'}),('status','status',{}),('pause','pause',{}),('excel','export_excel',{}),('backup','backup',{})]:
                write_frame(bridge.stdin,{'v':1,'id':identity,'type':kind,'payload':payload})
                reply=smoke.response(bridge.stdout)
                assert reply and reply['ok'],reply
                if kind=='status':
                    assert reply['payload']['project_root']==str(project)
                    assert reply['payload']['hotkey_error'] is None,reply['payload']['hotkey_error']
                print('PASS: packaged tray + host '+kind,flush=True)
            # Chrome's stdin remains open: pipe EOF alone must terminate the bridge.
            tray.terminate();tray.wait(timeout=10)
            assert bridge.wait(timeout=5)==0
            print('PASS: tray exit closes native host while Chrome stdin stays open',flush=True)
        finally:
            if bridge:
                bridge.stdin.close()
                try:bridge.wait(timeout=3)
                except subprocess.TimeoutExpired:bridge.kill();bridge.wait()
            tray.terminate();tray.wait(timeout=10)
            time.sleep(.2)


if __name__=='__main__':main()
