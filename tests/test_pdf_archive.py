import tempfile
import unittest
from pathlib import Path

from literature.pdf_archive import archive_name, build_archive, clean_name, standard_name
from literature.storage import Store, ValidationError
from literature.zotero import import_items


def paper(key, title, last='Köse', date='2026-03-01'):
    return {'key': key, 'data': {'itemType': 'conferencePaper', 'title': title, 'date': date,
                                 'creators': [{'creatorType': 'author', 'firstName': 'A', 'lastName': last}],
                                 'collections': ['IN']}}


def note(parent, key, matrix_id, extra=''):
    return {'key': key, 'data': {'itemType': 'note', 'parentItem': parent,
                                 'note': f'<p>Matris ID: {matrix_id}</p><p>Karar: Dahil</p>{extra}'}}


def pdf(parent, key, filename):
    return {'key': key, 'data': {'itemType': 'attachment', 'parentItem': parent, 'contentType': 'application/pdf',
                                 'linkMode': 'imported_url', 'filename': filename}}


class NamingTest(unittest.TestCase):
    def test_standard_names_are_ascii(self):
        data = {'title': 'RAGTurk: Best Practices for Retrieval Augmented Generation in Turkish', 'date': '2026',
                'creators': [{'creatorType': 'author', 'lastName': 'Köse'}]}
        self.assertEqual(standard_name('L001', data), 'L001_Kose_2026_RAGTurk.pdf')
        data = {'title': 'Is Semantic Chunking Worth the Computational Cost?', 'date': '2025-04',
                'creators': [{'creatorType': 'author', 'lastName': 'Qu'}]}
        self.assertEqual(standard_name('L025', data), 'L025_Qu_2025_SemanticChunkingWorthComputational.pdf')
        self.assertEqual(clean_name(r'C:\Belgeler\Türkçe RAG.pdf'), 'Turkce_RAG.pdf')
        self.assertEqual(archive_name({'Matris ID': 'L7'}, data), '')


class ArchiveTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        base = Path(self.tmp.name)
        self.store = Store(base / 'project')
        self.zotero = base / 'Zotero'
        self.store.update_settings({'zotero_data_dir': str(self.zotero)})

    def tearDown(self):
        self.store.close()
        self.tmp.cleanup()

    def stored(self, key, filename, body=b'%PDF-1.7 test'):
        folder = self.zotero / 'storage' / key
        folder.mkdir(parents=True, exist_ok=True)
        (folder / filename).write_bytes(body)

    def test_missing_data_directory_is_explained(self):
        with self.assertRaisesRegex(ValidationError, 'Zotero veri klasörü'):
            build_archive(self.store)

    def test_copy_report_and_never_overwrite(self):
        self.stored('AAAA1111', 'Kose 2026.pdf')
        self.stored('BBBB2222', 'other.pdf', b'not a pdf')
        items = [paper('P1', 'RAGTurk: Best Practices'), note('P1', 'N1', 'L001'), pdf('P1', 'AAAA1111', 'Kose 2026.pdf'),
                 paper('P2', 'No file here', 'Doğan'), note('P2', 'N2', 'L002'),
                 paper('P3', 'Broken file', 'Taşkın'), note('P3', 'N3', 'L003'), pdf('P3', 'BBBB2222', 'other.pdf'),
                 paper('P4', 'Without matrix id')]
        import_items(self.store, 'groups/1', items, {'included': 'IN'}, {})
        archive = self.store.path('Literatur_PDF')
        archive.mkdir(parents=True, exist_ok=True)
        (archive / 'eski_dosya.pdf').write_bytes(b'%PDF old')
        report = build_archive(self.store)
        self.assertEqual(report['copied'], ['L001_Kose_2026_RAGTurk.pdf'])
        self.assertEqual((archive / 'L001_Kose_2026_RAGTurk.pdf').read_bytes(), b'%PDF-1.7 test')
        self.assertEqual(len(report['missing_pdf']), 2)
        self.assertEqual(len(report['missing_id']), 1)
        self.assertEqual(report['extra_files'], ['eski_dosya.pdf'])
        self.assertTrue((self.zotero / 'storage' / 'AAAA1111' / 'Kose 2026.pdf').exists())
        again = build_archive(self.store)
        self.assertEqual(again['unchanged'], ['L001_Kose_2026_RAGTurk.pdf'])
        (archive / 'L001_Kose_2026_RAGTurk.pdf').write_bytes(b'%PDF changed by user')
        third = build_archive(self.store)
        self.assertEqual(len(third['conflicts']), 1)
        self.assertEqual((archive / 'L001_Kose_2026_RAGTurk.pdf').read_bytes(), b'%PDF changed by user')

    def test_note_file_name_wins_and_duplicate_names_reported(self):
        self.stored('AAAA1111', 'a.pdf')
        self.stored('CCCC3333', 'c.pdf')
        items = [paper('P1', 'First'), note('P1', 'N1', 'L001', '<p>Yerel PDF: Benim_Adim.pdf</p>'), pdf('P1', 'AAAA1111', 'a.pdf'),
                 paper('P2', 'Second'), note('P2', 'N2', 'L002', '<p>Yerel PDF: Benim_Adim.pdf</p>'), pdf('P2', 'CCCC3333', 'c.pdf')]
        import_items(self.store, 'groups/1', items, {'included': 'IN'}, {})
        report = build_archive(self.store)
        self.assertEqual(report['copied'], ['Benim_Adim.pdf'])
        self.assertEqual(len(report['conflicts']), 1)


if __name__ == '__main__':
    unittest.main()
