import io
import json
import random
import tempfile
import threading
import unittest
from pathlib import Path
from PIL import Image
from literature.application import Application
from literature.protocol import write_frame
from literature.storage import ValidationError


class ApplicationTest(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.app=Application(self.tmp.name)
    def tearDown(self):self.app.store.close();self.tmp.cleanup()

    def test_failed_command_cannot_rollback_capture_transaction(self):
        store=self.app.store;entered=threading.Event();release=threading.Event();finished=threading.Event()
        def capture_transaction():
            with store.lock,store.db:
                store.audit('capture-test','kept')
                entered.set();release.wait(3)
        def command():
            try:self.app.command('link_paper',{'paper_id':'missing','search_ids':[]})
            except ValidationError:pass
            finally:finished.set()
        capture=threading.Thread(target=capture_transaction);capture.start();self.assertTrue(entered.wait(2))
        worker=threading.Thread(target=command);worker.start()
        try:self.assertFalse(finished.wait(.15),'Command entered another thread\'s transaction')
        finally:release.set();capture.join(3);worker.join(3)
        self.assertEqual(store.db.execute("SELECT COUNT(*) FROM audit_events WHERE event='capture-test'").fetchone()[0],1)

    def test_high_entropy_thumbnail_fits_protocol(self):
        data=random.Random(7).randbytes(1000*650*3)
        image=Image.frombytes('RGB',(1000,650),data);out=io.BytesIO();image.save(out,'PNG')
        self.app.store.begin_job('noise',{})
        self.app.store.save_capture('noise',out.getvalue())
        preview=self.app.command('thumbnail',{'jobId':'noise'})
        self.assertTrue(preview['data'].startswith('data:image/jpeg;base64,'))
        wire=io.BytesIO()
        write_frame(wire,{'v':1,'id':'thumbnail','type':'reply','ok':True,'payload':preview})
        self.assertLess(len(wire.getvalue()),256*1024)


if __name__=='__main__':unittest.main()


class CsvCommandTest(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.app=Application(self.tmp.name)
    def tearDown(self):self.app.store.close();self.tmp.cleanup()

    def test_watcher_uses_the_current_store_and_commands_list_waiting_files(self):
        import shutil
        self.assertFalse(self.app.csv_watcher.is_alive())
        folder=self.app.store.path('01_HamExport');self.assertTrue(folder.is_dir())
        shutil.copy(Path(__file__).parent/'fixtures'/'ieee_results.csv',folder/'export.csv')
        self.app.csv_watcher.poll();result,=self.app.csv_watcher.poll()
        self.assertEqual(result['state'],'needs_run')
        rows=self.app.command('list_csv_imports',{})['rows']
        self.assertEqual(rows[0]['original_name'],'export.csv')
        with self.assertRaises(ValidationError):self.app.command('assign_csv_import',{'id':rows[0]['id'],'run':'S001'})
