import copy
import json
import tempfile
import unittest
from urllib.parse import parse_qs, urlsplit
from unittest.mock import patch

from literature.ris import parse_ris
from literature.storage import Store, ValidationError, json_text, utcnow
from literature.zotero import ZoteroClient
from literature.zotero_writer import ZoteroWriter, HTTPResponse, WRITER_SCHEMA, LocalZoteroClient


def record(eid='2-s2.0-123', title='Study', doi='10.1/study'):
    return parse_ris(f'TY  - JOUR\nTI  - {title}\nDO  - {doi}\nAN  - {eid}\nER  -\n'.encode())[0]


class FakeLocalAPI:
    """HTTP boundary double with real collection, version and permission semantics."""
    def __init__(self):
        self.server_id = 'server-one'
        self.key = 'a' * 32
        self.remember = True
        self.authorizations = 0
        self.denied = False
        self.version = 1
        self.objects = {'items': {}, 'collections': {}}
        for key, name in [('BX38VWI6', '01_Aday'), ('U8THQFWA', '00_AramaKayitlari')]:
            self.seed('collections', dict(key=key, name=name, parentCollection=False))
        self.requests = []
        self.timeout_after_items = False
        self.reject_titles = set()
        self.conflict_patch = False
        self.on_write = lambda: None

    def seed(self, kind, data):
        self.version += 1
        data = dict(data, version=self.version)
        self.objects[kind][data['key']] = {'key': data['key'], 'version': self.version, 'data': data}
        return self.objects[kind][data['key']]

    def response(self, status, body=None):
        return HTTPResponse(status, copy.deepcopy(body), {
            'Zotero-Server-ID': self.server_id, 'Last-Modified-Version': str(self.version)})

    def request(self, method, path, body=None, headers=None):
        headers = headers or {}
        self.requests.append((method, path, copy.deepcopy(body), dict(headers)))
        if method == 'GET' and path == '/':
            return self.response(200, {})
        if headers.get('Zotero-Server-ID') != self.server_id:
            return self.response(412, {})
        if path == '/local/authorize':
            self.authorizations += 1
            if self.denied:
                return self.response(403, {'denied': True})
            return self.response(200, {'key': self.key, 'remember': self.remember})
        bits = urlsplit(path).path.strip('/').split('/')
        assert bits[:2] == ['groups', '6718452'], bits
        kind = bits[2]
        if method == 'GET':
            if len(bits) == 4:
                obj = self.objects[kind].get(bits[3])
                return self.response(200 if obj else 404, obj)
            params = parse_qs(urlsplit(path).query)
            start = int(params.get('start', [0])[0])
            limit = int(params.get('limit', [100])[0])
            return self.response(200, list(self.objects[kind].values())[start:start + limit])
        self.on_write()
        if headers.get('Zotero-API-Key') != self.key:
            return self.response(401, {})
        if method == 'POST':
            assert len(body) <= 50
            result = {'successful': {}, 'unchanged': {}, 'failed': {}}
            for index, data in enumerate(body):
                index = str(index)
                if data.get('title') in self.reject_titles:
                    result['failed'][index] = {'code': 400, 'message': 'Invalid item', 'key': data['key']}
                elif data['key'] in self.objects[kind]:
                    result['failed'][index] = {'code': 412, 'message': 'Key already exists', 'key': data['key']}
                else:
                    result['successful'][index] = self.seed(kind, data)
            if self.timeout_after_items and kind == 'items':
                self.timeout_after_items = False
                raise TimeoutError('response lost after commit')
            return self.response(200, result)
        assert method == 'PATCH' and kind == 'items'
        current = self.objects[kind][bits[3]]
        if self.conflict_patch:
            self.conflict_patch = False
            self.seed(kind, dict(current['data'], collections=current['data'].get('collections', []) + ['USER2345']))
            return self.response(412, {})
        if str(current['version']) != headers.get('If-Unmodified-Since-Version'):
            return self.response(412, {})
        self.seed(kind, dict(current['data'], **body))
        return self.response(204)


class WriterTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.store = Store(self.tmp.name)
        self.store.db.executescript(WRITER_SCHEMA)
        self.store.update_settings({'library': 'groups/6718452', 'zotero_mode': 'local',
                                    'collection_mapping': {'candidate': 'BX38VWI6'}})
        self.api = FakeLocalAPI()
        self.credentials = {}
        self.patches = [patch('literature.zotero_writer.load_api_key', side_effect=lambda name: self.credentials.get(name, '')),
                        patch('literature.zotero_writer.save_api_key', side_effect=lambda key, name: self.credentials.__setitem__(name, key))]
        for p in self.patches:
            p.start()
        with self.store.db:
            project_id = self.store.db.execute('SELECT id FROM projects').fetchone()[0]
            for i in (1, 2):
                self.store.db.execute('''INSERT INTO search_runs
                    (id,display_id,project_id,database_name,query_raw,query_verified,filters_json,timezone)
                    VALUES(?,?,?,?,?,?,?,?)''', (f'search-{i}', f'S00{i}', project_id, 'Scopus', 'topic', 1, '[]', 'Europe/Istanbul'))
        self.writer = ZoteroWriter(self.store, self.api)

    def tearDown(self):
        for p in self.patches:
            p.stop()
        self.store.close()
        self.tmp.cleanup()

    def authorize(self):
        self.assertTrue(self.writer.preflight(authorize=True)['ready'])

    def test_preflight_is_read_only_unless_explicitly_authorized(self):
        self.assertTrue(self.writer.preflight()['requires_authorization'])
        self.assertEqual(self.api.authorizations, 0)
        self.authorize()
        self.assertEqual(self.api.authorizations, 1)
        self.assertEqual(list(self.credentials.values()), [self.api.key])

    def test_single_use_key_is_never_persisted_and_denial_does_not_write(self):
        self.api.remember = False
        self.authorize()
        self.assertEqual(self.credentials, {})
        self.api.denied = True
        self.writer = ZoteroWriter(self.store, self.api)
        result = self.writer.preflight(authorize=True)
        self.assertFalse(result['ready'])
        self.assertEqual(len(self.api.objects['items']), 0)

    def test_import_repeated_eid_reuses_item_and_preserves_local_decisions(self):
        self.authorize()
        summary = self.writer.import_records([record(), record()], 'session-one', 'search-1')
        self.assertEqual(summary['raw_count'], 2)
        self.assertEqual(summary['unique_count'], 1)
        self.assertEqual(summary['imported'], 1)
        self.assertEqual(summary['failed'], 0)
        with self.store.db:
            self.store.db.execute("UPDATE papers SET state='included',annotation='Keep',verified=1")
        again = self.writer.import_records([record()], 'session-one', 'search-2')
        self.assertEqual(again['reused'], 1)
        self.assertEqual(len(self.api.objects['items']), 1)
        paper = self.store.db.execute('SELECT * FROM papers').fetchone()
        self.assertEqual((paper['state'], paper['annotation'], paper['verified']), ('included', 'Keep', 1))
        self.assertEqual(self.store.db.execute('SELECT count(*) FROM search_paper_links').fetchone()[0], 2)
        data = next(iter(self.api.objects['items'].values()))['data']
        self.assertIn('BX38VWI6', data['collections'])
        self.assertIn(summary['collection_key'], data['collections'])
        self.assertIn(again['collection_key'], data['collections'])

    def test_imported_paper_can_save_draft_without_initial_manual_sync(self):
        self.authorize()
        self.writer.import_records([record()], 'session-one', 'search-1')
        notes=self.store.db.execute('SELECT * FROM reading_notes').fetchone()
        self.assertIsNotNone(notes,'New imported papers need a place for local reading drafts')
        with self.store.db:self.store.db.execute("UPDATE reading_notes SET local_draft='Keep draft'")
        self.writer.import_records([record()], 'session-one', 'search-2')
        self.assertEqual(self.store.db.execute('SELECT local_draft FROM reading_notes').fetchone()[0],'Keep draft')

    def test_timeout_after_commit_then_new_writer_reconciles_persisted_key(self):
        self.authorize()
        self.api.timeout_after_items = True
        first = self.writer.import_records([record()], 'session-one', 'search-1')
        self.assertEqual(first['failed'], 1)
        committed_key = next(iter(self.api.objects['items']))
        self.writer = ZoteroWriter(self.store, self.api)
        again = self.writer.import_records([record()], 'session-one', 'search-1')
        self.assertEqual(again['failed'], 0)
        self.assertEqual(list(self.api.objects['items']), [committed_key])
        self.assertEqual(self.store.db.execute('SELECT count(*) FROM papers').fetchone()[0], 1)
        sends = [r for r in self.api.requests if r[0] == 'POST' and r[1].endswith('/items')]
        self.assertEqual(len(sends), 1)

    def test_partial_failure_is_recorded_per_object_and_retry_keeps_successful_items(self):
        self.authorize()
        self.api.reject_titles.add('Rejected')
        records = [record(), record('2-s2.0-456', 'Rejected', '10.2/other')]
        result = self.writer.import_records(records, 'session-one', 'search-1')
        self.assertEqual((result['imported'], result['failed']), (1, 1))
        self.assertEqual(self.store.db.execute("SELECT count(*) FROM zotero_import_objects WHERE kind='items' AND state='failed'").fetchone()[0], 1)
        self.api.reject_titles.clear()
        result = self.writer.import_records(records, 'session-one', 'search-1')
        self.assertEqual(result['failed'], 0)
        self.assertEqual(len(self.api.objects['items']), 2)

    def test_existing_exact_eid_gets_only_membership_union_with_version_retry(self):
        existing = record()['item']
        existing.update(key='EXIST234', title='User title', collections=['KEEP2345'], extra=existing['extra'] + '\nUser note: keep')
        self.api.seed('items', existing)
        self.authorize()
        self.api.conflict_patch = True
        result = self.writer.import_records([record()], 'session-one', 'search-1')
        self.assertEqual(result['failed'], 0)
        data = self.api.objects['items']['EXIST234']['data']
        self.assertEqual(data['title'], 'User title')
        self.assertIn('User note: keep', data['extra'])
        self.assertEqual(set(data['collections']), {'KEEP2345', 'USER2345', result['collection_key']})
        patches = [r for r in self.api.requests if r[0] == 'PATCH']
        self.assertEqual(len(patches), 2)
        self.assertEqual(set(patches[0][2]), {'collections'})

    def test_doi_or_title_similarity_is_flagged_but_never_merged(self):
        self.api.seed('items', dict(record('2-s2.0-999')['item'], key='SIMIL234', collections=[]))
        self.authorize()
        result = self.writer.import_records([record()], 'session-one', 'search-1')
        self.assertEqual(len(self.api.objects['items']), 2)
        self.assertGreater(result['duplicates'], 0)
        self.assertGreater(self.store.db.execute('SELECT count(*) FROM zotero_duplicate_suspects').fetchone()[0], 0)

    def test_generated_keys_are_durable_before_network_write_and_lock_is_released(self):
        self.authorize()
        def inspect():
            self.assertFalse(self.store.lock._is_owned())
            body = self.api.requests[-1][2]
            if isinstance(body, list):
                for obj in body:
                    self.assertRegex(obj['key'], r'^[23456789ABCDEFGHIJKLMNPQRSTUVWXYZ]{8}$')
                    ledger = self.store.db.execute('SELECT body_json FROM zotero_import_objects WHERE object_key=?', (obj['key'],)).fetchone()
                    self.assertIsNotNone(ledger)
                    self.assertEqual(json.loads(ledger[0]), obj)
        self.api.on_write = inspect
        self.writer.import_records([record()], 'session-one', 'search-1')

    def test_server_change_does_not_reuse_old_key_or_write(self):
        self.authorize()
        self.writer.import_records([record()], 'session-one', 'search-1')
        self.api.server_id = 'server-two'
        self.api.requests.clear()
        result = self.writer.preflight()
        self.assertFalse(result['ready'])
        self.assertTrue(result['requires_authorization'])
        self.assertFalse(any(r[0] in ('POST', 'PATCH') for r in self.api.requests))

    def test_wrong_target_is_rejected_before_network(self):
        self.store.update_settings({'library': 'users/0'})
        with self.assertRaises(ValidationError):
            self.writer.preflight(authorize=True)
        self.assertEqual(self.api.requests, [])

    def test_cancel_prevents_next_write(self):
        self.authorize()
        def cancelled():
            raise InterruptedError('cancelled')
        with self.assertRaises(InterruptedError):
            self.writer.import_records([record()], 'session-one', 'search-1', cancelled)
        self.assertEqual(len(self.api.objects['items']), 0)

    def test_deleted_confirmed_item_is_not_recreated_even_on_repeated_retry(self):
        self.authorize()
        self.writer.import_records([record()], 'session-one', 'search-1')
        self.api.objects['items'].clear()
        for _ in range(2):
            result = self.writer.import_records([record()], 'session-one', 'search-1')
            self.assertEqual(result['failed'], 1)
            self.assertEqual(len(self.api.objects['items']), 0)

    def test_uncertain_key_with_different_content_is_never_patched(self):
        self.authorize()
        self.api.timeout_after_items = True
        self.writer.import_records([record()], 'session-one', 'search-1')
        key = next(iter(self.api.objects['items']))
        self.api.seed('items', dict(self.api.objects['items'][key]['data'], title='Unrelated changed content'))
        self.api.requests.clear()
        result = self.writer.import_records([record()], 'session-one', 'search-1')
        self.assertEqual(result['failed'], 1)
        self.assertEqual(self.api.objects['items'][key]['data']['title'], 'Unrelated changed content')
        self.assertFalse(any(r[0] in ('POST', 'PATCH') for r in self.api.requests))

    def test_incoming_doi_similarity_is_flagged_without_collapsing_records(self):
        self.authorize()
        result = self.writer.import_records([record(), record('2-s2.0-456')], 'session-one', 'search-1')
        self.assertEqual(len(self.api.objects['items']), 2)
        self.assertGreater(result['duplicates'], 0)

    def test_large_import_splits_batches_and_permission_failure_is_durable(self):
        self.authorize()
        records = [record(f'2-s2.0-{i}', f'Study {i}', f'10.1/{i}') for i in range(51)]
        result = self.writer.import_records(records, 'session-one', 'search-1')
        self.assertEqual(result['imported'], 51)
        batches = [r[2] for r in self.api.requests if r[0] == 'POST' and r[1].endswith('/items')]
        self.assertEqual([len(b) for b in batches], [50, 1])
        self.api.key = 'b' * 32
        result = self.writer.import_records([record('2-s2.0-999', 'New')], 'session-one', 'search-1')
        self.assertEqual(result['failed'], 1)
        self.assertEqual(len(self.api.objects['items']), 51)
        self.assertFalse(self.writer.key)

    def test_cancellation_after_intent_prevents_network_write(self):
        self.authorize()
        def cancelled():
            if self.store.db.execute("SELECT 1 FROM zotero_import_objects WHERE state='sending'").fetchone():
                raise InterruptedError('cancelled')
        with self.assertRaises(InterruptedError):
            self.writer.import_records([record()], 'session-one', 'search-1', cancelled)
        self.assertEqual(len(self.api.objects['collections']), 2)
        self.assertFalse(any(r[0] == 'POST' and r[1].endswith('/collections') for r in self.api.requests))

    def test_library_change_between_pages_aborts_before_import(self):
        self.authorize()
        for i in range(101):
            self.api.seed('items', dict(record(f'2-s2.0-{1000+i}')['item'], key=f'{i:08d}', collections=[]))
        original = self.api.request
        def changed(method, path, **kwargs):
            if method == 'GET' and '/items?' in path and 'start=100' in path:
                self.api.version += 1
            return original(method, path, **kwargs)
        with patch.object(self.api, 'request', side_effect=changed), self.assertRaises(ValidationError):
            self.writer.import_records([record()], 'session-one', 'search-1')
        self.assertEqual(len(self.api.objects['items']), 101)

    def test_existing_classification_is_reflected_when_local_paper_is_first_seen(self):
        self.store.update_settings({'collection_mapping': {'candidate': 'BX38VWI6', 'excluded': 'EXCL2345'}})
        self.api.seed('items', dict(record()['item'], key='EXIST234', collections=['EXCL2345']))
        self.authorize()
        self.writer.import_records([record()], 'session-one', 'search-1')
        self.assertEqual(self.store.db.execute('SELECT state FROM papers').fetchone()[0], 'excluded')

    def test_pending_identity_does_not_create_second_item_if_other_key_now_has_eid(self):
        self.authorize()
        self.api.reject_titles.add('Study')
        self.writer.import_records([record()], 'session-one', 'search-1')
        self.api.reject_titles.clear()
        self.api.seed('items', dict(record()['item'], key='OTHER234', collections=[]))
        result = self.writer.import_records([record()], 'session-one', 'search-1')
        self.assertEqual(result['failed'], 1)
        self.assertEqual(len(self.api.objects['items']), 1)


class ClientBoundaryTest(unittest.TestCase):
    def test_writer_rejects_arbitrary_hosts_deletion_and_attachment_routes(self):
        client = LocalZoteroClient()
        for method, path in [('DELETE', '/groups/6718452/items/ABCD2345'),
                             ('GET', 'https://example.com/'), ('GET', '//example.com'),
                             ('POST', '/groups/999/items'),
                             ('POST', '/groups/6718452/items/ABCD2345/file')]:
            with self.subTest(path=path), self.assertRaises(ValidationError):
                client.request(method, path)

    def test_read_client_does_not_stop_at_twenty_thousand_and_detects_repeated_page(self):
        client = ZoteroClient({'zotero_mode': 'local', 'library': 'groups/6718452'})
        def page(kind, params):
            start = params['start']
            return [{'key': str(i), 'data': {}} for i in range(start, min(20103, start + 100))]
        with patch.object(client, '_get', side_effect=page):
            self.assertEqual(len(client.all('items')), 20103)
        with patch.object(client, '_get', return_value=[{'key': str(i)} for i in range(100)]):
            with self.assertRaises(ValidationError):
                client.all('items')

    def test_read_client_rejects_library_version_drift_between_pages(self):
        client = ZoteroClient({'zotero_mode': 'local', 'library': 'groups/6718452'})
        def page(kind, params):
            start = params['start']
            client._last_version = str(start)
            return [{'key': str(i)} for i in range(start, min(102, start + 100))]
        with patch.object(client, '_get', side_effect=page), self.assertRaises(ValidationError):
            client.all('items')


if __name__ == '__main__':
    unittest.main()
