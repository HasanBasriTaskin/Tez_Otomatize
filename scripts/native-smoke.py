"""Opt-in Windows smoke checks. Uses an isolated project; never imports thesis rows."""
import io
import json
import os
import subprocess
import sys
import tempfile
import threading
import time
import uuid
import pywintypes
import queue
import faulthandler
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from literature.application import Application
from literature.ipc import PipeServer,connect_pipe,pipe_name
from literature.protocol import read_frame,write_frame
from literature.windows import Desktop,parse_hotkey
from literature.runtime import product


def response(stream):
    mailbox=queue.Queue()
    def receive():
        try:mailbox.put(read_frame(stream))
        except Exception as e:mailbox.put(e)
    threading.Thread(target=receive,daemon=True).start()
    try:result=mailbox.get(timeout=12)
    except queue.Empty:
        faulthandler.dump_traceback()
        raise TimeoutError('Native response exceeded 12 seconds')
    if isinstance(result,Exception):raise result
    return result


def main():
    desktop=Desktop()
    assert parse_hotkey('CTRL+M')[0]&0x4000  # MOD_NOREPEAT is used in the native registration.
    desktop.start('CTRL+ALT+9',lambda:None,lambda hwnd:None)
    try:
        assert desktop.hotkey_error is None,desktop.hotkey_error
        print('PASS: native RegisterHotKey and message loop',flush=True)
    finally:desktop.stop()
    name=pipe_name('-qa-'+uuid.uuid4().hex)
    server=PipeServer(lambda peer,msg:{'echo':msg['payload']},lambda peer:None,name)
    threading.Thread(target=server.run,daemon=True).start()
    stream=None
    for _ in range(100):
        try:stream=connect_pipe(name);break
        except (OSError,pywintypes.error):time.sleep(.02)
    assert stream
    try:
        payload={'text':'Türkçe ğışİöç '*6000}
        write_frame(stream,{'v':1,'id':'roundtrip','type':'status','payload':payload})
        reply=response(stream)
        assert reply['ok'] and reply['payload']['echo']==payload
        print('PASS: actual user-session named pipe, framed Turkish payload >64KB',flush=True)
    finally:stream.close()
    if '--packaged' not in sys.argv:return
    with tempfile.TemporaryDirectory(dir=ROOT/'.tmp') as folder:
        app=Application(folder)
        def handle(peer,message):
            print('server request:',message['type'],flush=True)
            return app.handle(peer,message)
        native_server=PipeServer(handle,app.disconnect)
        threading.Thread(target=native_server.run,daemon=True).start()
        executable=ROOT/'release/LiteraturKayit-0.3.0/payload/host/NativeHost.exe'
        origin='chrome-extension://'+product()['extension_id']+'/'
        command=[sys.executable,str(ROOT/'run_host.py')] if '--source' in sys.argv else [str(executable)]
        process=subprocess.Popen(command+[origin,'--parent-window=0'],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
        try:
            write_frame(process.stdin,{'v':1,'id':'hi','type':'hello','payload':{'role':'worker','profile':'native-smoke'}})
            reply=response(process.stdout)
            assert reply and reply['ok'],reply
            write_frame(process.stdin,{'v':1,'id':'status','type':'status','payload':{}})
            reply=response(process.stdout)
            assert reply['ok'] and reply['payload']['run_count']==0,reply
            assert reply['payload']['project_root']==str(Path(folder).resolve())
            print('PASS: '+('source host' if '--source' in sys.argv else 'packaged NativeHost.exe')+' binary stdin/stdout -> pipe -> Application status')
        finally:
            process.stdin.close()
            try:process.wait(timeout=3)
            except subprocess.TimeoutExpired:process.kill();process.wait()
            print('host exit',process.returncode,process.stderr.read().decode(errors='replace'),flush=True)
            time.sleep(.2);app.store.close()


if __name__=='__main__':main()
