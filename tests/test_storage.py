import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PIL import Image
from openpyxl import load_workbook
from literature.storage import Store, ValidationError


def fields(**updates):
    result = dict(database='Scopus', query_raw='TITLE-ABS-KEY("Türkçe" AND RAG)',
                  query_verified=True, fields='TITLE-ABS-KEY', filters=['2022–2026'],
                  count_raw='0 results', count_value=0, count_qualifier='exact',
                  safe_url='https://www.scopus.com/results', status='complete')
    result.update(updates)
    return result


class StorageTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.store = Store(self.root)
        self.png = self.root / 'input.png'
        Image.new('RGB', (320, 200), 'white').save(self.png)

    def tearDown(self):
        self.store.close()
        self.tmp.cleanup()

    def capture(self, job='job-1', context=None):
        context = context or dict(profile='p', windowId=1, tabId=2, documentId='d', epoch=0)
        self.store.begin_job(job, context)
        self.store.save_capture(job, self.png.read_bytes(), captured_at='2026-10-14T21:05:00+00:00')
        return self.store.complete_job(job, fields(), context)

    def test_zero_and_local_capture_date(self):
        result = self.capture()
        self.assertEqual(result['display_id'], 'S001')
        self.assertEqual(result['count_value'], 0)
        cap = self.store.captures(result['id'])[0]
        self.assertIn('S001_20261015_a_sonuc.png', cap['relative_path'])
        self.assertEqual(cap['width'], 320)
        self.assertEqual(len(cap['sha256']), 64)

    def test_retry_is_idempotent_and_extra_capture_keeps_one_run(self):
        first = self.capture()
        self.capture()
        second = self.capture('job-2')
        self.assertEqual(first['id'], second['id'])
        self.assertEqual(len(self.store.list_runs()), 1)
        caps = self.store.captures(first['id'])
        self.assertEqual(len(caps), 2)
        self.assertNotEqual(caps[0]['relative_path'], caps[1]['relative_path'])
        self.assertTrue(any('_v02' in c['relative_path'] for c in caps))

    def test_changed_tab_keeps_image_pending(self):
        a = dict(profile='p', windowId=1, tabId=2, documentId='d', epoch=0)
        b = dict(a, tabId=3)
        self.store.begin_job('changed', a)
        self.store.save_capture('changed', self.png.read_bytes())
        r = self.store.complete_job('changed', fields(), b)
        self.assertEqual(r['state'], 'incomplete')
        self.assertEqual(len(self.store.list_runs()), 0)
        self.assertTrue(self.store.path(r['image_path']).exists())

    def test_unknown_count_does_not_become_zero(self):
        self.store.begin_job('null', {})
        self.store.save_capture('null', self.png.read_bytes())
        r = self.store.complete_job('null', fields(count_value=None), {})
        self.assertEqual(r['state'], 'incomplete')

    def test_different_query_and_new_day_are_new_runs(self):
        first = self.capture()
        c = dict(profile='p', windowId=1, tabId=2, documentId='d', epoch=0)
        self.store.begin_job('new-day', c)
        self.store.save_capture('new-day', self.png.read_bytes(), captured_at='2026-10-16T12:00:00+00:00')
        second = self.store.complete_job('new-day', fields(), c)
        self.assertNotEqual(first['id'], second['id'])

    def test_excel_preserves_text_and_portable_links(self):
        self.capture()
        self.store.update_run('S001', {'notes': '=HYPERLINK("bad")'})
        out = self.store.export_excel()
        w = load_workbook(out['path'])
        self.assertEqual(w.sheetnames, ['Arama_Kaydi', 'Matris', 'Hariç'])
        s = w['Arama_Kaydi']
        self.assertEqual(s['H7'].value, 0)
        self.assertEqual(s['K7'].data_type, 's')
        self.assertTrue(s['J7'].hyperlink.target.startswith('../02_Ekranlar/'))
        w.close()

    def test_excel_user_edits_are_not_overwritten(self):
        self.capture()
        p = Path(self.store.export_excel()['path'])
        p.write_bytes(b'user changed file')
        r = self.store.export_excel()
        self.assertNotEqual(str(p), r['path'])
        self.assertEqual(p.read_bytes(), b'user changed file')

    def test_path_traversal_rejected(self):
        for name in ['../out.png', 'C:/out.png', '/out.png']:
            with self.assertRaises(ValidationError):
                self.store.path(name)

    def test_recovery_after_rename_before_database_commit(self):
        self.store.begin_job('recover', {})
        self.store.save_capture('recover', self.png.read_bytes())
        with patch.object(self.store, '_finish_commit', side_effect=RuntimeError('power loss')):
            with self.assertRaises(RuntimeError):
                self.store.complete_job('recover', fields(), {})
        self.store.close()
        self.store = Store(self.root)
        self.assertEqual(len(self.store.list_runs()), 1)
        self.assertEqual(len(self.store.captures(self.store.list_runs()[0]['id'])), 1)
        self.assertEqual(self.store.get_job('recover')['state'], 'verified')


if __name__ == '__main__':
    unittest.main()
