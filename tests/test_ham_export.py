import os
import time
import unittest

import test_storage as fixtures
from literature import ham_export


def ris(n, bom=False):
    return ('﻿' if bom else '') + ''.join(f'TY  - JOUR\nTI  - Paper {i}\nER  - \n\n' for i in range(n))


class HamExportTest(unittest.TestCase):
    setUp = fixtures.StorageTest.setUp
    tearDown = fixtures.StorageTest.tearDown

    def run_(self, job, count, database='Scopus'):
        context = dict(profile='p', windowId=1, tabId=2, documentId=job, epoch=0)
        self.store.begin_job(job, context)
        self.store.save_capture(job, self.png.read_bytes())
        data = fixtures.fields(database=database, count_value=count, count_raw=f'{count} results')
        return self.store.complete_job(job, data, context)

    def write(self, relative, text):
        path = self.store.path('01_HamExport/' + relative)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding='utf-8')
        old = time.time() - 10
        os.utime(path, (old, old))
        return path

    def test_counts_from_files_skipped_folder_and_narrowing(self):
        parent, child, skipped, other = (self.run_('a', 12), self.run_('b', 3), self.run_('c', 40), self.run_('d', 7))
        self.store.db.execute("INSERT INTO search_refinements VALUES('r',?,?,12,2024,2026,'q',12,'q','x','{}','captured','t',NULL,?)",
                              (parent['id'], parent['display_id'], child['id']))
        self.write('S002_Scopus.ris', ris(3, bom=True))
        self.write('_aktarilmayacak/S003_Scopus.ris', ris(40))
        self.write('notes.ris', ris(1))
        self.assertTrue(ham_export.scan(self.store))
        self.assertFalse(ham_export.scan(self.store))  # unchanged files are not re-read
        info = {r: self.store.export_info(x['id']) for r, x in (('p', parent), ('c', child), ('s', skipped), ('o', other))}
        self.assertEqual((info['p']['effective_count'], info['p']['source']), (0, 'Aktarılmadı: yıl/filtre daraltmasıyla S002 alındı'))
        self.assertEqual((info['c']['effective_count'], info['c']['source']), (3, 'RIS dosyası (01_HamExport): S002_Scopus.ris'))
        self.assertEqual(info['c']['export_files_all'], 'S002_Scopus.ris')
        self.assertEqual(info['s']['effective_count'], 0)
        self.assertIn('_aktarilmayacak: S003_Scopus.ris', info['s']['source'])
        self.assertEqual(info['s']['export_files_all'], '')
        self.assertIsNone(info['o']['effective_count'])

    def test_manual_count_wins_and_differences_are_reported(self):
        run = self.run_('a', 5)
        self.write('S001_Scopus.ris', ris(4))
        ham_export.scan(self.store)
        self.assertIn('ekranda 5 sonuç', self.store.export_info(run['id'])['source'])
        self.store.update_run(run['id'], {'manual_count': '5', 'export_files': 'S001_Scopus.ris'})
        info = self.store.export_info(run['id'])
        self.assertEqual(info['effective_count'], 5)
        self.assertIn('RIS dosyasında 4 kayıt', info['source'])
        self.assertEqual(info['export_files_all'], 'S001_Scopus.ris')

    def test_several_parts_add_up_and_moved_files_are_forgotten(self):
        run = self.run_('a', 5)
        first = self.write('S001_Scopus_001-003.ris', ris(3))
        self.write('S001_Scopus_004-005.ris', ris(2))
        ham_export.scan(self.store)
        info = self.store.export_info(run['id'])
        self.assertEqual(info['effective_count'], 5)
        self.assertEqual(info['export_files_all'], 'S001_Scopus_001-003.ris; S001_Scopus_004-005.ris')
        self.store.path('01_HamExport/_aktarilmayacak').mkdir()
        first.rename(self.store.path('01_HamExport/_aktarilmayacak/S001_Scopus_001-003.ris'))
        self.assertTrue(ham_export.scan(self.store))
        self.assertEqual(self.store.export_info(run['id'])['effective_count'], 2)

    def test_platform_mixups_are_flagged(self):
        scopus, ieee = self.run_('a', 2), self.run_('b', 2, database='IEEE Xplore')
        self.write('S001_IEEE.ris', ris(2))
        self.write('S002_IEEE.ris', ris(2))
        ham_export.scan(self.store)
        self.assertIn('uyuşmuyor', self.store.export_info(scopus['id'])['source'])
        self.assertNotIn('uyuşmuyor', self.store.export_info(ieee['id'])['source'])

    def test_file_still_being_written_waits(self):
        run = self.run_('a', 2)
        self.store.path('01_HamExport/S001_Scopus.ris').write_text(ris(2), encoding='utf-8')
        self.assertFalse(ham_export.scan(self.store))
        self.assertTrue(ham_export.scan(self.store, settle=0))
        self.assertEqual(self.store.export_info(run['id'])['effective_count'], 2)

    def test_excel_shows_counts_source_and_files(self):
        run = self.run_('a', 2)
        self.write('S001_Scopus.ris', ris(2))
        ham_export.scan(self.store)
        self.store.export_excel()
        import openpyxl
        path = next(self.store.path('03_Calisma').glob('*.xlsx'))
        ws = openpyxl.load_workbook(path)['Arama_Kaydi']
        self.assertEqual([ws.cell(2, c).value for c in (9, 12, 13)], [2, 'RIS dosyası (01_HamExport): S001_Scopus.ris', 'S001_Scopus.ris'])
