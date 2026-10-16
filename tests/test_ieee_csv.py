import json
import re
import shutil
import unittest
from pathlib import Path

import test_storage as fixtures
from literature import ieee_csv
from literature.storage import ValidationError

FIX = Path(__file__).parent / 'fixtures'
QUERY = '("Abstract":"retrieval augmented generation") AND ("Abstract":Turkish)'


def parse(text):
    records = []
    for block in text.split('ER  - '):
        tags = {}
        for tag, value in re.findall(r'^([A-Z][A-Z0-9])  - ?(.*)$', block, re.M):
            tags.setdefault(tag, []).append(value)
        if tags:
            records.append(tags)
    return records


class ConversionTest(unittest.TestCase):
    def test_matches_ieee_own_ris_export_tag_by_tag(self):
        rows = ieee_csv.read_rows((FIX / 'ieee_results.csv').read_bytes())
        self.assertEqual(len(rows), 6)
        ours = {r['DO'][0]: r for r in parse(ieee_csv.to_ris(rows))}
        theirs = parse((FIX / 'ieee_citations.ris').read_text(encoding='utf-8'))
        self.assertEqual(len(theirs), 4)
        for record in theirs:
            mine = ours[record['DO'][0]]
            for tag, values in record.items():
                self.assertEqual(mine.get(tag), values, tag)
            self.assertEqual(set(mine) - set(record), {'PB'})

    def test_types_and_program_parser(self):
        rows = ieee_csv.read_rows((FIX / 'ieee_results.csv').read_bytes())
        self.assertEqual([ieee_csv.ris_type(r['Document Identifier']) for r in rows],
                         ['CONF', 'CONF', 'CONF', 'JOUR', 'JOUR', 'CONF'])
        self.assertEqual(ieee_csv.ris_type('IEEE Standards'), 'STAND')
        self.assertEqual(ieee_csv.ris_type('Wiley-IEEE Press eBook Chapters'), 'BOOK')
        text = ieee_csv.to_ris(rows)
        blocks = [b for b in text.split('\n\n') if b.strip()]
        self.assertEqual(len(blocks), 6)
        self.assertTrue(all(b.startswith('TY  - ') and b.rstrip('\n').endswith('ER  - ') for b in blocks))
        self.assertTrue(all(re.fullmatch(r'[A-Z][A-Z0-9]  - .*', line) for b in blocks for line in b.strip('\n').split('\n')))

    def test_other_csv_files_are_not_ieee(self):
        self.assertIsNone(ieee_csv.read_rows(b'Authors,Title,Year\nA,B,2025\n'))
        self.assertIsNone(ieee_csv.read_rows(b''))

    def test_line_breaks_inside_fields_do_not_break_records(self):
        raw = (FIX / 'ieee_results.csv').read_bytes().decode('utf-8')
        header = raw.split('\n', 1)[0]
        cols = next(iter(__import__('csv').reader([header])))
        values = ['x'] * len(cols)
        values[cols.index('Abstract')] = 'line one\nline two'
        values[cols.index('Publication Year')] = '2025'
        import csv, io
        out = io.StringIO(); csv.writer(out).writerows([cols, values])
        rows = ieee_csv.read_rows(out.getvalue().encode('cp1254'))
        self.assertIn('AB  - line one line two\n', ieee_csv.to_ris(rows))


class WatcherTest(unittest.TestCase):
    setUp = fixtures.StorageTest.setUp
    tearDown = fixtures.StorageTest.tearDown

    def ieee_run(self, count, job, filters=('Tür: Conferences', 'Tür: Journals', 'Yıl: 2024–2026')):
        context = dict(profile='p', windowId=1, tabId=3, documentId=job, epoch=0)
        self.store.begin_job(job, context)
        self.store.save_capture(job, self.png.read_bytes())
        data = fixtures.fields(database='IEEE Xplore', query_raw=QUERY, fields='Abstract', filters=list(filters),
                               count_value=count, count_raw=f'{count} results',
                               safe_url='https://ieeexplore.ieee.org/search/searchresult.jsp')
        return self.store.complete_job(job, data, context)

    def drop(self, name='export2026.10.16-13.03.49.csv'):
        target = self.store.path('01_HamExport') / name
        shutil.copy(FIX / 'ieee_results.csv', target)
        return target

    def watcher(self):
        self.notes = []
        return ieee_csv.CsvWatcher(lambda: self.store, lambda *a: self.notes.append(a), interval=0)

    def test_unrenamed_csv_is_matched_renamed_and_converted(self):
        self.ieee_run(195, 'other-count')
        run = self.ieee_run(6, 'six')
        self.drop()
        w = self.watcher()
        self.assertEqual(w.poll(), [])  # first sighting: wait until the file is stable
        result, = w.poll()
        self.assertEqual(result['state'], 'converted')
        code = run['display_id']
        folder = self.store.path('01_HamExport')
        self.assertEqual(sorted(p.name for p in folder.iterdir()), [f'{code}_IEEE.csv', f'{code}_IEEE.ris'])
        self.assertEqual(len(parse((folder / f'{code}_IEEE.ris').read_text(encoding='utf-8'))), 6)
        self.assertEqual(self.store.export_info(run['id'])['export_files'], f'{code}_IEEE.csv; {code}_IEEE.ris')
        self.assertIn(f'{code}_IEEE.ris', self.notes[0][0])
        self.assertEqual(w.poll(), []); self.assertEqual(w.poll(), [])  # renamed file is known
        # A second download of the same file is ignored instead of creating another RIS.
        self.drop('export2026.10.16-13.05.00.csv'); w.poll(); self.assertEqual(w.poll(), [])
        self.assertEqual(len(list(folder.glob('*.ris'))), 1)

    def test_superseded_parent_and_wrong_years_are_not_candidates(self):
        parent = self.ieee_run(6, 'parent', filters=('Yıl (sonuç aralığı): 2019–2026',))
        old = self.ieee_run(6, 'old-years', filters=('Tür: Conferences', 'Tür: Journals', 'Yıl: 2010–2020'))
        child = self.ieee_run(6, 'child')
        self.store.db.execute("INSERT INTO search_refinements VALUES('r1',?,?,6,2024,2026,'q',6,'q','x','{}','captured','t',NULL,?)",
                              (parent['id'], parent['display_id'], child['id']))
        rows = ieee_csv.read_rows((FIX / 'ieee_results.csv').read_bytes())
        self.assertEqual([r['display_id'] for r in ieee_csv.candidates(self.store, rows)], [child['display_id']])

    def test_ambiguous_csv_waits_for_the_user_and_never_overwrites(self):
        a = self.ieee_run(6, 'a'); b = self.ieee_run(6, 'b')
        folder = self.store.path('01_HamExport')
        (folder / f"{b['display_id']}_IEEE.ris").write_text('user file', encoding='utf-8')
        self.drop()
        w = self.watcher(); w.poll()
        result, = w.poll()
        self.assertEqual(result['state'], 'needs_run')
        self.assertEqual(result['candidates'], [a['display_id'], b['display_id']])
        item, = ieee_csv.list_imports(self.store)
        self.assertEqual(item['candidates'], [a['display_id'], b['display_id']])
        with self.assertRaises(ValidationError):
            ieee_csv.assign(self.store, item['id'], 'S999')
        done = ieee_csv.assign(self.store, item['id'], b['display_id'])
        self.assertEqual(done['ris'], f"{b['display_id']}_IEEE_2.ris")
        self.assertEqual((folder / f"{b['display_id']}_IEEE.ris").read_text(encoding='utf-8'), 'user file')
        with self.assertRaises(ValidationError):
            ieee_csv.assign(self.store, item['id'], a['display_id'])

    def test_user_named_file_and_unmatched_count(self):
        run = self.ieee_run(2000, 'big')
        self.drop(f"{run['display_id']}_IEEE.csv")
        w = self.watcher(); w.poll()
        result, = w.poll()
        self.assertEqual((result['state'], result['run'], result['csv']), ('converted', run['display_id'], f"{run['display_id']}_IEEE.csv"))
        self.drop('export-unmatched.csv')
        (self.store.path('01_HamExport') / 'export-unmatched.csv').write_text(
            (FIX / 'ieee_results.csv').read_text(encoding='utf-8') + '\n', encoding='utf-8')  # different hash
        w.poll(); result, = w.poll()
        self.assertEqual(result['state'], 'needs_run')
        self.assertIn('eşleşmedi', result['message'])
        other = self.ieee_run(2100, 'bigger')
        item = [i for i in ieee_csv.list_imports(self.store) if i['state'] == 'needs_run'][0]
        done = ieee_csv.assign(self.store, item['id'], other['display_id'])
        self.assertIn('dışa aktarım sınırı', done['warning'])

    def test_non_ieee_csv_is_left_untouched(self):
        file = self.store.path('01_HamExport') / 'scopus.csv'
        file.write_text('Authors,Title,Year\nA,B,2025\n', encoding='utf-8')
        w = self.watcher(); w.poll(); self.assertEqual(w.poll(), [])
        self.assertTrue(file.exists()); self.assertEqual(self.notes, [])
        self.assertEqual(ieee_csv.list_imports(self.store), [])
