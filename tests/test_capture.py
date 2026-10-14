import io
import tempfile
import unittest
from PIL import Image
from literature.capture import CaptureController
from literature.storage import Store
from test_storage import fields


class Desktop:
    epoch=1
    hwnd=100
    def foreground(self): return self.hwnd
    def chrome_window(self,hwnd): return hwnd==100
    def grab(self,hwnd,monitor):
        out=io.BytesIO();Image.new('RGB',(30,20),'white').save(out,'PNG');return out.getvalue()


class Peer:
    profile='p'
    def __init__(self,desktop): self.desktop=desktop;self.change=False;self.calls=[]
    def request(self,kind,payload,timeout=5):
        self.calls.append(kind)
        context=dict(profile='p',windowId=7,tabId=9,documentId='doc',epoch=0)
        if kind=='prepare_capture': return {'context':context,'ready':True}
        if kind=='extract_capture':
            if self.change: self.desktop.epoch+=1
            return {'context':context,'data':fields()}
        return {}


class CaptureTest(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.store=Store(self.tmp.name)
        self.desktop=Desktop();self.peer=Peer(self.desktop)
        self.messages=[]
        self.app=CaptureController(self.store,self.desktop,lambda *x:self.messages.append(x))
        self.app.bind(100,7,self.peer)
    def tearDown(self): self.store.close();self.tmp.cleanup()
    def test_capture_before_extract(self):
        original=self.desktop.grab
        def grab(*args):
            self.assertEqual(self.peer.calls,['prepare_capture'])
            return original(*args)
        self.desktop.grab=grab
        self.app.capture()
        self.assertEqual(len(self.store.list_runs()),1)
    def test_focus_change_prevents_automatic_record(self):
        self.peer.change=True
        self.app.capture()
        self.assertEqual(self.store.list_runs(),[])
        self.assertEqual(self.store.pending()[0]['state'],'incomplete')
    def test_foreign_foreground_and_busy_do_not_capture(self):
        self.desktop.hwnd=101
        self.app.capture()
        self.assertEqual(self.peer.calls,[])
        self.desktop.hwnd=100
        self.app.busy.acquire()
        self.app.capture()
        self.app.busy.release()
        self.assertEqual(self.peer.calls,[])


if __name__=='__main__':unittest.main()
