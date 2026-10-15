import io
import tempfile
import unittest
from unittest.mock import patch
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
        self.assertNotIn('offer_refinement',self.peer.calls)

    def test_refinement_opens_only_after_capture_is_saved_and_released(self):
        request=self.peer.request
        observed={}
        def large_result(kind,payload,timeout=5):
            result=request(kind,payload,timeout)
            if kind=='extract_capture':result['data']=fields(count_value=12000,count_raw='12,000 results')
            if kind=='offer_refinement':
                observed['busy']=self.app.busy.locked()
                observed['previous']=self.peer.calls[-2]
                run=self.store.list_runs()[0]
                observed['saved']=self.store.path(self.store.captures(run['id'])[0]['relative_path']).exists()
            return result
        self.peer.request=large_result
        self.app.capture()
        self.assertEqual(observed,dict(busy=False,previous='release_capture',saved=True))
        self.assertEqual(self.peer.calls[-1],'offer_refinement')
        self.assertEqual(self.store.db.execute('SELECT state FROM search_refinements').fetchone()[0],'offered')
    def test_foreign_foreground_and_busy_do_not_capture(self):
        self.desktop.hwnd=101
        self.app.capture()
        self.assertEqual(self.peer.calls,[])
        self.desktop.hwnd=100
        self.app.busy.acquire()
        self.app.capture()
        self.app.busy.release()
        self.assertEqual(self.peer.calls,[])

    def test_automatic_capture_is_quiet_and_returns_saved_run(self):
        run=self.app.capture(automatic={'job_id':'auto-1','context':{'profile':'p','windowId':7,'tabId':9},'query':fields()['query_raw']})
        self.assertEqual(run['display_id'],'S001')
        self.assertEqual(self.messages,[])
        self.assertNotIn('offer_refinement',self.peer.calls)

    def test_automatic_capture_always_uses_the_scopus_monitor(self):
        self.store.update_settings({'monitor':'2'})
        grab=self.desktop.grab
        with patch.object(self.desktop,'grab',side_effect=grab) as observed:
            self.app.capture(automatic={'job_id':'active-screen','context':{'profile':'p','windowId':7,'tabId':9},'query':fields()['query_raw']})
        self.assertEqual(observed.call_args.args,(100,'active'))

    def test_automatic_capture_checks_expected_query_before_committing(self):
        with self.assertRaises(ValueError):
            self.app.capture(automatic={'job_id':'auto-1','context':{'profile':'p','windowId':7,'tabId':9},'query':'TITLE("other")'})
        self.assertEqual(self.store.list_runs(),[])
        self.assertEqual(len(self.store.pending()),1)

    def test_manual_shortcut_cannot_run_while_automation_owns_capture(self):
        self.app.automation_active=True
        self.app.capture()
        self.assertEqual(self.peer.calls,[])

    def test_gallery_error_cannot_demote_or_move_committed_evidence(self):
        with patch.object(self.store,'_write_gallery',side_effect=PermissionError('gallery locked')):
            self.app.capture()
        run=self.store.list_runs()[0]
        cap=self.store.captures(run['id'])[0]
        self.assertEqual(self.store.get_job(cap['job_id'])['state'],'verified')
        retry=self.store.complete_job(cap['job_id'],fields(),{},manual=True,new_run=True)
        self.assertEqual(retry['id'],run['id'])
        self.assertTrue(self.store.path(cap['relative_path']).exists())
        self.assertEqual(len(self.store.list_runs()),1)


if __name__=='__main__':unittest.main()
