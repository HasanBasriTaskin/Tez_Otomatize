import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from urllib.parse import parse_qs, urlsplit
from unittest.mock import patch

from literature import descriptions, fulltext, zotero_fixes
from literature.storage import Store, ValidationError, citation_text, filter_lines, run_status
from literature.zotero_writer import WRITER_SCHEMA, LocalZoteroClient, ZoteroWriter
from tests.test_zotero_writer import FakeLocalAPI


class FileAPI(FakeLocalAPI):
    """Adds the Zotero 10 local file-upload flow, collection sub-listings and collection deletion."""
    def __init__(self):
        super().__init__()
        self.uploads = {}
        self.received = {}

    def request(self, method, path, body=None, headers=None, raw=None):
        headers = headers or {}
        bits = urlsplit(path).path.strip('/').split('/')
        if bits[:2] == ['local', 'uploads']:
            self.requests.append((method, path, None, dict(headers)))
            token = bits[2]
            expected = self.uploads[token]
            if hashlib.md5(raw).hexdigest() != expected['md5']:
                return self.response(400, {})
            self.received[token] = raw
            return self.response(201, None)
        if len(bits) == 5 and bits[2] == 'collections' and method == 'GET':
            self.requests.append((method, path, None, dict(headers)))
            key, sub = bits[3], bits[4]
            if sub == 'items':
                found = [o for o in self.objects['items'].values() if key in o['data'].get('collections', [])]
            else:
                found = [o for o in self.objects['collections'].values() if o['data'].get('parentCollection') == key]
            return self.response(200, found[:1])
        if len(bits) == 5 and bits[4] == 'file' and method == 'POST':
            self.requests.append((method, path, raw, dict(headers)))
            if headers.get('Zotero-API-Key') != self.key:
                return self.response(401, {})
            item = self.objects['items'][bits[3]]
            form = {k: v[0] for k, v in parse_qs(raw.decode('ascii')).items()}
            if 'upload' in form:
                upload = self.uploads.pop(form['upload'])
                if form['upload'] not in self.received:
                    return self.response(400, {})
                self.seed('items', dict(item['data'], md5=upload['md5'], filename=upload['filename']))
                return self.response(204)
            if item['data'].get('md5') == form['md5']:
                return self.response(200, {'exists': 1})
            token = 'u' + str(len(self.uploads) + 1) * 12
            self.uploads[token] = form
            return self.response(200, {'url': f'http://127.0.0.1:23119/api/local/uploads/{token}', 'uploadKey': token,
                                       'contentType': 'application/pdf', 'prefix': '', 'suffix': ''})
        if method == 'DELETE':
            self.requests.append((method, path, None, dict(headers)))
            if headers.get('Zotero-API-Key') != self.key:
                return self.response(401, {})
            obj = self.objects['collections'][bits[3]]
            if str(obj['version']) != headers.get('If-Unmodified-Since-Version'):
                return self.response(412, {})
            del self.objects['collections'][bits[3]]
            return self.response(204)
        return super().request(method, path, body, headers)


class ZoteroFilesTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.store = Store(self.root)
        self.store.update_settings({'library': 'groups/6718452', 'zotero_mode': 'local',
                                    'collection_mapping': {'candidate': 'BX38VWI6'}})
        self.api = FileAPI()
        self.patches = [patch('literature.zotero_writer.load_api_key', return_value=''),
                        patch('literature.zotero_writer.save_api_key')]
        for p in self.patches:
            p.start()
        self.writer = ZoteroWriter(self.store, self.api)
        self.writer.preflight(authorize=True)
        self.api.seed('items', {'key': 'PAPER234', 'itemType': 'conferencePaper', 'title': 'PROVENCE: EFFICIENT',
                                'url': 'https://www.scopus.com/x', 'place': 'Pisa , Italy', 'collections': []})
        self.pdf = self.root / 'Literatur_PDF' / 'L022_Chirkova_2025_PROVENCE.pdf'
        self.pdf.write_bytes(b'%PDF-1.7 test content')

    def tearDown(self):
        for p in self.patches:
            p.stop()
        self.store.close()
        self.tmp.cleanup()

    def entry(self):
        return {'key': 'PAPER234', 'filename': self.pdf.name, 'path': str(self.pdf)}

    def attachments(self):
        return [o for o in self.api.objects['items'].values() if o['data'].get('itemType') == 'attachment']

    def test_pdf_is_uploaded_once_as_stored_file_child(self):
        result = self.writer.attach_pdfs([self.entry()])
        self.assertEqual((result['uploaded'], result['failed']), (1, 0), result)
        [attachment] = self.attachments()
        self.assertEqual(attachment['data']['parentItem'], 'PAPER234')
        self.assertEqual(attachment['data']['linkMode'], 'imported_file')
        self.assertEqual(attachment['data']['md5'], hashlib.md5(self.pdf.read_bytes()).hexdigest())
        upload = [r for r in self.api.requests if r[1].startswith('/local/uploads/')][0]
        self.assertNotIn('Zotero-API-Key', upload[3])
        again = self.writer.attach_pdfs([self.entry()])
        self.assertEqual((again['uploaded'], again['existing']), (0, 1))
        self.assertEqual(len(self.attachments()), 1)

    def test_pdf_attached_by_hand_is_kept_without_second_copy(self):
        self.api.seed('items', {'key': 'ATTACH23', 'itemType': 'attachment', 'parentItem': 'PAPER234', 'linkMode': 'imported_file',
                                'contentType': 'application/pdf', 'filename': 'Chirkova - 2025 - Provence.pdf', 'md5': 'abc'})
        result = self.writer.attach_pdfs([self.entry()])
        self.assertEqual((result['uploaded'], result['existing']), (0, 1))
        self.assertEqual(len(self.attachments()), 1)

    def test_not_a_pdf_is_refused(self):
        self.pdf.write_bytes(b'<html>login page</html>')
        result = self.writer.attach_pdfs([self.entry()])
        self.assertEqual(result['failed'], 1)
        self.assertEqual(self.attachments(), [])

    def test_corrections_need_the_expected_old_value(self):
        result = self.writer.apply_corrections([
            {'key': 'PAPER234', 'alan': 'title', 'eski': 'PROVENCE: EFFICIENT', 'yeni': 'Provence: Efficient'},
            {'key': 'PAPER234', 'alan': 'place', 'eski': 'Pisa , Italy', 'yeni': 'Pisa, Italy'},
            {'key': 'PAPER234', 'alan': 'url', 'eski': 'https://elsewhere', 'yeni': 'https://proceedings.example'},
            {'key': 'PAPER234', 'alan': 'abstractNote', 'eski': 'önceki özet', 'yeni': 'x'},
            {'key': 'PAPER234', 'alan': 'DOI', 'eski': '', 'yeni': '10.1/x'}])
        data = self.api.objects['items']['PAPER234']['data']
        self.assertEqual((data['title'], data['place'], data['url']), ('Provence: Efficient', 'Pisa, Italy', 'https://www.scopus.com/x'))
        self.assertEqual(data['DOI'], '10.1/x')  # empty fields are absent in local API items
        self.assertEqual((result['updated'], result['failed']), (3, 2))
        self.assertEqual(self.writer.apply_corrections([{'key': 'PAPER234', 'alan': 'title', 'eski': 'PROVENCE: EFFICIENT',
                                                         'yeni': 'Provence: Efficient'}])['unchanged'], 1)

    def test_only_empty_listed_collections_are_removed(self):
        self.api.seed('collections', {'key': 'EMPTY234', 'name': 'S003_ACM', 'parentCollection': 'U8THQFWA'})
        self.api.seed('collections', {'key': 'FULL2345', 'name': 'S004_ACM', 'parentCollection': 'U8THQFWA'})
        self.api.seed('items', {'key': 'INSIDE23', 'itemType': 'journalArticle', 'title': 'x', 'collections': ['FULL2345']})
        result = self.writer.remove_empty_collections([{'key': 'EMPTY234', 'ad': 'S003_ACM'}, {'key': 'FULL2345', 'ad': 'S004_ACM'},
                                                       {'key': 'U8THQFWA', 'ad': '00_AramaKayitlari'}])
        self.assertEqual((result['removed'], result['failed']), (1, 2))
        self.assertNotIn('EMPTY234', self.api.objects['collections'])
        self.assertIn('FULL2345', self.api.objects['collections'])
        self.assertIn('U8THQFWA', self.api.objects['collections'])
        self.assertEqual(self.writer.remove_empty_collections([{'key': 'EMPTY234', 'ad': 'S003_ACM'}])['absent'], 1)


class BoundaryAndTextTest(unittest.TestCase):
    def test_client_allows_only_upload_routes_and_empty_collection_deletion(self):
        client = LocalZoteroClient()
        for method, path, raw in [('DELETE', '/groups/6718452/items/ABCD2345', None),
                                  ('POST', '/groups/6718452/items/ABCD2345/file', None),
                                  ('POST', '/local/uploads/abcdefgh12', None),
                                  ('POST', '/local/uploads/../x', b'x'),
                                  ('GET', '/groups/6718452/items/ABCD2345/file', None),
                                  ('DELETE', '/groups/6718452/collections', None)]:
            with self.subTest(path=path), self.assertRaises(ValidationError):
                client.request(method, path, raw=raw)

    def test_reading_note_leaves_out_untouched_template_hints(self):
        lines = ['Matris ID: L001', 'İstisna gerekçesi: (yalnız 2024 öncesi temel çalışmada doldurun)', 'Tema: T1_Parcalama', '']
        self.assertEqual(fulltext.note_lines(lines), ['Matris ID: L001', 'Tema: T1_Parcalama'])
        self.assertNotIn('doldurun', fulltext.note_html(lines))

    def test_workbook_texts_are_plain(self):
        self.assertEqual(citation_text({'citation': '[1]\n\nA. B, “Title x,” 2026.'}), 'A. B, “Title x,” 2026.')
        self.assertEqual(filter_lines(['Tür: Journals', 'Filtre: 2024 - 2026', 'Yıl: 2024–2026']), ['Tür: Journals', 'Yıl: 2024–2026'])
        self.assertEqual(filter_lines(['Filtre: 2023 - 2026', 'Yıl: 2024–2026']), ['Filtre: 2023 - 2026', 'Yıl: 2024–2026'])
        self.assertEqual([run_status(i) for i in ({'effective_count': 5}, {'effective_count': 0, 'child': 'S002'},
                                                   {'effective_count': 0, 'child': None})],
                         ['Dışa aktarıldı', 'Filtre öncesi sonuç', 'Aktarılmadı'])

    def test_fix_file_is_validated(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(zotero_fixes.summary(zotero_fixes.load(tmp)), {'kunye': 0, 'bos_koleksiyon': 0})
            path = Path(tmp) / zotero_fixes.RELATIVE
            path.parent.mkdir(parents=True)
            path.write_text(json.dumps({'sema': 1, 'kunye': [{'key': 'A', 'alan': 'title'}]}), encoding='utf-8')
            with self.assertRaises(ValidationError):
                zotero_fixes.load(tmp)


class DescriptionsTest(unittest.TestCase):
    def test_descriptions_are_applied_once_with_backup(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = Store(tmp)
            try:
                with store.db:
                    project = store.db.execute('SELECT id FROM projects').fetchone()[0]
                    store.db.execute('''INSERT INTO search_runs(id,display_id,project_id,database_name,query_raw,query_verified,
                        filters_json,timezone,notes) VALUES('r1','S001',?,'Scopus','q',1,'[]','Europe/Istanbul','S001 devamı: eski')''', (project,))
                path = store.path(descriptions.RELATIVE.as_posix())
                path.write_text(json.dumps({'sema': 1, 'aciklamalar': {'S001': 'Eşik sorgusu.'}}), encoding='utf-8')
                self.assertEqual(descriptions.apply(store), 1)
                self.assertEqual(store.get_run('S001')['notes'], 'Eşik sorgusu.')
                store.update_run('S001', {'notes': 'Elle düzelttim.'})
                self.assertEqual(descriptions.apply(store), 0)
                self.assertEqual(store.get_run('S001')['notes'], 'Elle düzelttim.')
                [backup] = list(Path(tmp, 'Yedekler').glob('arama_aciklamalari_onceki_*.json'))
                self.assertEqual(json.loads(backup.read_text(encoding='utf-8')), {'S001': 'S001 devamı: eski'})
                path.write_text(json.dumps({'sema': 1, 'aciklamalar': {'S999': 'x'}}), encoding='utf-8')
                with self.assertRaises(ValidationError):
                    descriptions.apply(store)
            finally:
                store.close()


if __name__ == '__main__':
    unittest.main()
