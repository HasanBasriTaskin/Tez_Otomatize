import os
import tempfile
import time
import unittest
from pathlib import Path

import test_storage as fixtures
from literature import downloads, ham_export, ieee_csv
from literature.storage import ValidationError

CONTEXT = dict(profile='p', windowId=1, tabId=2, documentId='d', epoch=0)


def scopus_ris(n, start=0):
    return ''.join(f'TY  - JOUR\nTI  - Paper {i}\nUR  - https://www.scopus.com/inward/record.uri?eid=2-s2.0-{850000 + i}&partnerID=40\n'
                   f'DB  - Scopus\nER  - \n\n' for i in range(start, start + n))


def ieee_csv_text(n):
    head = ','.join(f'"{h}"' for h in ieee_csv.REQUIRED)
    rows = [','.join(f'"{h} {i}"' for h in ieee_csv.REQUIRED) for i in range(n)]
    return '\n'.join([head] + rows) + '\n'


class DownloadsTest(unittest.TestCase):
    setUp_ = fixtures.StorageTest.setUp

    def setUp(self):
        self.setUp_()
        self.downloads = self.root / 'Downloads'
        self.downloads.mkdir()
        self.store.update_settings({'downloads_dir': str(self.downloads), 'downloads_watch': True})

    tearDown = fixtures.StorageTest.tearDown

    def run_(self, job, count, database='Scopus'):
        self.store.begin_job(job, CONTEXT)
        self.store.save_capture(job, self.png.read_bytes())
        data = fixtures.fields(database=database, count_value=count, count_raw=f'{count} results',
                               query_raw=f'TITLE-ABS-KEY("{job}")')
        return self.store.complete_job(job, data, CONTEXT, new_run=True)

    def put(self, name, text, age=0):
        path = self.downloads / name
        path.write_text(text, encoding='utf-8')
        if age:
            old = time.time() - age
            os.utime(path, (old, old))
        return path

    def watch(self):
        watcher = downloads.DownloadsWatcher(lambda: self.store, lambda *a: None)
        watcher._poll(self.store)  # first round only notes the size of new files
        return watcher._poll(self.store)

    def test_scopus_and_ieee_exports_are_matched_and_moved(self):
        scopus, ieee = self.run_('a', 3), self.run_('b', 2, 'IEEE Xplore')
        self.put('export_00d33b40-fccb-46c8-8a76-67642fe1b8a9_2026-10-16T152453.505746615.ris', scopus_ris(3))
        self.put('export2026.10.16-13.03.49.csv', ieee_csv_text(2))
        self.put('rapor.pdf', 'x')
        results = {r['kind']: r for r in self.watch()}
        self.assertEqual((results['scopus_ris']['run'], results['scopus_ris']['target']), (scopus['display_id'], 'S001_Scopus.ris'))
        self.assertEqual((results['ieee_csv']['run'], results['ieee_csv']['target']), (ieee['display_id'], 'S002_IEEE.csv'))
        self.assertEqual(sorted(p.name for p in self.downloads.iterdir()), ['rapor.pdf'])
        self.assertEqual(ham_export.count_records(self.store.path('01_HamExport/S001_Scopus.ris')), 3)
        self.assertEqual(self.store.export_info(scopus['id'])['export_files'], 'S001_Scopus.ris')
        # the existing CSV watcher turns the named CSV into RIS for that search
        result = ieee_csv.process_file(self.store, self.store.path('01_HamExport/S002_IEEE.csv'))
        self.assertEqual((result['run'], result['ris'], result['rows']), ('S002', 'S002_IEEE.ris', 2))

    def test_uncertain_files_are_left_in_place_and_listed(self):
        self.run_('a', 3), self.run_('b', 3)
        self.put('export_x.ris', scopus_ris(3))
        self.put('export_y.ris', scopus_ris(5, 10))
        results = sorted(self.watch(), key=lambda r: r['file'])
        self.assertEqual([r['state'] for r in results], ['needs_run', 'needs_run'])
        self.assertEqual(results[0]['candidates'], ['S002', 'S001'])
        self.assertEqual(results[1]['candidates'], [])
        self.assertEqual(sorted(p.name for p in self.downloads.iterdir()), ['export_x.ris', 'export_y.ris'])
        listed = {r['original_name']: r for r in downloads.list_entries(self.store)}
        self.assertEqual(listed['export_x.ris']['runs'], ['S001', 'S002'])
        moved = downloads.assign(self.store, listed['export_x.ris']['id'], 'S001')
        self.assertEqual(moved['target'], 'S001_Scopus.ris')
        self.assertFalse((self.downloads / 'export_x.ris').exists())
        with self.assertRaises(ValidationError):
            downloads.assign(self.store, listed['export_x.ris']['id'], 'S002')
        warned = downloads.assign(self.store, listed['export_y.ris']['id'], 'S002')
        self.assertIn('5 kayıt var', warned['warning'])

    def test_searches_with_files_or_a_narrowing_step_are_not_candidates(self):
        done, parent, child = self.run_('a', 3), self.run_('b', 4), self.run_('c', 2)
        path = self.store.path('01_HamExport/S001_Scopus.ris')
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(scopus_ris(3, 50), encoding='utf-8')
        old = time.time() - 10
        os.utime(path, (old, old))
        ham_export.scan(self.store)
        self.store.db.execute("INSERT INTO search_refinements VALUES('r',?,?,4,2024,2026,'q',4,'q','x','{}','captured','t',NULL,?)",
                              (parent['id'], parent['display_id'], child['id']))
        self.assertEqual(downloads.candidates(self.store, 'scopus_ris', 3), [])
        self.assertEqual(downloads.candidates(self.store, 'scopus_ris', 4), [])
        self.assertEqual([r['display_id'] for r in downloads.candidates(self.store, 'scopus_ris', 2)], ['S003'])

    def test_a_copy_already_in_hamexport_old_files_and_partial_downloads_are_not_touched(self):
        self.run_('a', 3)
        path = self.store.path('01_HamExport/S009_Scopus.ris')
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(scopus_ris(3), encoding='utf-8')
        self.put('export_same.ris', scopus_ris(3))
        self.put('export_old.ris', scopus_ris(3, 20), age=3 * 24 * 3600)
        self.put('export_half.ris.crdownload', scopus_ris(3, 30))
        self.assertEqual(self.watch(), [])
        self.assertEqual(sorted(p.name for p in self.downloads.iterdir()), ['export_half.ris.crdownload', 'export_old.ris', 'export_same.ris'])

    def test_nothing_happens_while_the_setting_is_off(self):
        self.store.update_settings({'downloads_watch': False})
        self.run_('a', 3)
        self.put('export_x.ris', scopus_ris(3))
        self.assertEqual(self.watch(), [])
        self.assertTrue((self.downloads / 'export_x.ris').exists())
        with self.assertRaises(ValidationError):
            self.store.update_settings({'downloads_watch': 'evet'})

    def test_recognition(self):
        self.assertEqual(downloads.classify('a.ris', scopus_ris(2).encode()), ('scopus_ris', 2))
        self.assertEqual(downloads.classify('b.ris', b'TY  - CONF\nUR  - https://ieeexplore.ieee.org/document/1\nER  - \n'), ('ieee_ris', 1))
        self.assertEqual(downloads.classify('c.csv', ieee_csv_text(4).encode('utf-8-sig')), ('ieee_csv', 4))
        self.assertEqual(downloads.classify('d.csv', b'a,b\n1,2\n'), (None, 0))
        self.assertEqual(downloads.classify('e.ris', b'TY  - JOUR\nTI  - x\nER  - \n'), (None, 0))


if __name__ == '__main__':
    unittest.main()
