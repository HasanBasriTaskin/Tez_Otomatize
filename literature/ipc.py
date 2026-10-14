import hashlib
import queue
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor

import pywintypes
import win32api
import win32con
import win32file
import win32pipe
import win32security
import win32ts

from .protocol import read_frame, write_frame, ProtocolError


def user_sid():
    token=win32security.OpenProcessToken(win32api.GetCurrentProcess(),win32con.TOKEN_QUERY)
    try:return win32security.ConvertSidToStringSid(win32security.GetTokenInformation(token,win32security.TokenUser)[0])
    finally:token.Close()


def pipe_name(suffix=''):
    sid=user_sid()
    session=win32ts.ProcessIdToSessionId(win32api.GetCurrentProcessId())
    return '\\\\.\\pipe\\LiteraturKayit-'+hashlib.sha256(sid.encode()).hexdigest()[:20]+f'-{session}'+suffix


class PipeStream:
    def __init__(self,handle):self.handle=handle;self.write_lock=threading.Lock()
    def read(self,n):
        try:return win32file.ReadFile(self.handle,n)[1]
        except pywintypes.error as e:
            if e.winerror in (109,232,233,6):return b''
            raise
    def write(self,data):
        with self.write_lock:win32file.WriteFile(self.handle,data)
    def flush(self):pass
    def close(self):
        try:win32file.CloseHandle(self.handle)
        except pywintypes.error:pass


def connect_pipe(name=None):
    return PipeStream(win32file.CreateFile(name or pipe_name(),win32con.GENERIC_READ|win32con.GENERIC_WRITE,
                                          0,None,win32con.OPEN_EXISTING,0,None))


class Peer:
    def __init__(self,stream,handler,disconnect):
        self.stream,self.handler,self.on_disconnect=stream,handler,disconnect
        self.pending={};self.lock=threading.Lock();self.connected=True
        self.profile=None;self.role=None
        self.pool=ThreadPoolExecutor(max_workers=4,thread_name_prefix='native-command')
        self.capacity=threading.BoundedSemaphore(12)

    def send(self,message):write_frame(self.stream,message)

    def request(self,kind,payload,timeout=5):
        identity=str(uuid.uuid4());mailbox=queue.Queue(maxsize=1)
        with self.lock:self.pending[identity]=mailbox
        try:
            if not self.connected:raise ConnectionError('Chrome bağlantısı kapalı.')
            self.send({'v':1,'id':identity,'type':kind,'payload':payload})
            try:reply=mailbox.get(timeout=timeout)
            except queue.Empty as e:raise TimeoutError('Chrome yanıt vermedi.') from e
            if not reply.get('ok'):raise RuntimeError(reply.get('error','Chrome işlemi tamamlanamadı.'))
            return reply.get('payload',{})
        finally:
            with self.lock:self.pending.pop(identity,None)

    def _dispatch(self,message):
        try:
            try:
                result=self.handler(self,message)
                response={'v':1,'id':message['id'],'type':'reply','ok':True,'payload':result or {}}
            except (ValueError,ProtocolError) as e:
                response={'v':1,'id':message['id'],'type':'reply','ok':False,'error':str(e),'payload':{}}
            except Exception:
                response={'v':1,'id':message['id'],'type':'reply','ok':False,
                          'error':'İşlem tamamlanamadı. Dosya/bağlantı durumunu kontrol edip yeniden deneyin.','payload':{}}
            self.send(response)
        except Exception:pass
        finally:self.capacity.release()

    def run(self):
        try:
            while (message:=read_frame(self.stream)) is not None:
                if message['type']=='reply':
                    with self.lock:mailbox=self.pending.get(message['id'])
                    if mailbox:
                        try:mailbox.put_nowait(message)
                        except queue.Full:pass
                elif self.capacity.acquire(blocking=False):
                    # Hello is synchronous: subsequent requests cannot outrun authentication.
                    if message['type']=='hello':self._dispatch(message)
                    else:self.pool.submit(self._dispatch,message)
                else:
                    self.send({'v':1,'id':message['id'],'type':'reply','ok':False,'error':'Uygulama meşgul.','payload':{}})
        except Exception:pass
        finally:
            self.connected=False
            with self.lock:
                for mailbox in self.pending.values():
                    try:mailbox.put_nowait({'ok':False,'error':'Chrome bağlantısı kapandı.'})
                    except queue.Full:pass
            self.on_disconnect(self)
            self.stream.close()
            self.pool.shutdown(wait=False,cancel_futures=True)


class PipeServer:
    def __init__(self,handler,disconnect,name=None):
        self.handler,self.disconnect,self.name=handler,disconnect,name or pipe_name()
        self.running=True
    def run(self):
        sd=win32security.ConvertStringSecurityDescriptorToSecurityDescriptor(
            f'D:P(A;;GA;;;{user_sid()})(A;;GA;;;SY)',win32security.SDDL_REVISION_1)
        security=pywintypes.SECURITY_ATTRIBUTES();security.SECURITY_DESCRIPTOR=sd
        while self.running:
            handle=win32pipe.CreateNamedPipe(self.name,win32pipe.PIPE_ACCESS_DUPLEX,
                win32pipe.PIPE_TYPE_BYTE|win32pipe.PIPE_READMODE_BYTE|win32pipe.PIPE_WAIT|8,
                32,262148,262148,5000,security)
            try:win32pipe.ConnectNamedPipe(handle,None)
            except pywintypes.error as e:
                if e.winerror!=535:
                    win32file.CloseHandle(handle)
                    continue
            peer=Peer(PipeStream(handle),self.handler,self.disconnect)
            threading.Thread(target=peer.run,daemon=True,name='pipe-peer').start()
