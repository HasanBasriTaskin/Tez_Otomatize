"""Chrome native messaging entry point. stdout must contain frames only."""
import os
import subprocess
import sys
import threading
import time
import msvcrt
import pywintypes

from literature.ipc import connect_pipe
from literature.protocol import read_frame,write_frame
from literature.runtime import product,product_dir


def forward_messages(stream,output,on_disconnect):
    code=0
    try:
        while (message:=read_frame(stream)) is not None:write_frame(output,message)
    except Exception:code=1
    finally:on_disconnect(code)


def main():
    expected='chrome-extension://'+product()['extension_id']+'/'
    if len(sys.argv)<2 or sys.argv[1]!=expected:return 2
    parent=next((int(a.split('=',1)[1]) for a in sys.argv[2:] if a.startswith('--parent-window=') and a.split('=',1)[1].isdigit()),0)
    msvcrt.setmode(sys.stdin.fileno(),os.O_BINARY);msvcrt.setmode(sys.stdout.fileno(),os.O_BINARY)
    stream=None
    for attempt in range(40):
        try:stream=connect_pipe();break
        except (OSError,pywintypes.error):
            if attempt==0:
                base=product_dir()
                command=[str(base/'tray'/'LiteraturKayit.exe')] if getattr(sys,'frozen',False) else [sys.executable,str(base/'run_tray.py')]
                subprocess.Popen(command,cwd=base,creationflags=subprocess.CREATE_NO_WINDOW,
                                 stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
            time.sleep(.2)
    if stream is None:return 3
    # Pipe EOF must close the process even while Chrome keeps stdin open, so Chrome reconnects.
    threading.Thread(target=forward_messages,args=(stream,sys.stdout.buffer,os._exit),daemon=True).start()
    try:
        while (message:=read_frame(sys.stdin.buffer)) is not None:
            if message['type']=='hello':
                message['payload']['origin']=expected
                message['payload']['parentHwnd']=parent
            write_frame(stream,message)
    finally:stream.close()
    return 0


if __name__=='__main__':
    try:raise SystemExit(main())
    except Exception:raise SystemExit(1)
