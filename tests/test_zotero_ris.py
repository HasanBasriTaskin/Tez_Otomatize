import os
import time
import unittest
from unittest.mock import patch

import test_storage as fixtures
from test_zotero_writer import FakeLocalAPI
from literature import ham_export, zotero_ris, acm
from literature.zotero_writer import ZoteroWriter

CONTEXT = dict(profile='p', windowId=1, tabId=2, documentId='d', epoch=0)


def ris(*records):
    out = ''
    for r in records:
        out += f"TY  - {r.get('ty', 'CONF')}\nTI  - {r['title']}\nAU  - Yazar, Bir\nPY  - 2025\n"
        if r.get('doi'):
            out += f"DO  - {r['doi']}\n"
        if r.get('eid'):
            out += f"UR  - https://www.scopus.com/inward/record.uri?eid=2-s2.0-{r['eid']}&partnerID=40\n"
        out += 'ER  - \n\n'
    return out


LONG = 'Retrieval augmented generation for Turkish institutional regulations'


class ZoteroRisTest(unittest.TestCase):
    setUp_ = fixtures.StorageTest.setUp
    tearDown = fixtures.StorageTest.tearDown

    def setUp(self):
        self.setUp_()
        self.api = FakeLocalAPI()
        credentials = {}
        for p in (patch('literature.zotero_writer.load_api_key', side_effect=lambda name: credentials.get(name, '')),
                  patch('literature.zotero_writer.save_api_key', side_effect=lambda key, name: credentials.__setitem__(name, key))):
            p.start()
            self.addCleanup(p.stop)
        self.store.update_settings({'zotero_mode': 'local', 'library': 'groups/6718452', 'collection_mapping': {'candidate': 'BX38VWI6'}})
        self.writer = ZoteroWriter(self.store, self.api)
        self.writer.preflight(authorize=True)

    def run_(self, job, count, database):
        self.store.begin_job(job, CONTEXT)
        self.store.save_capture(job, self.png.read_bytes())
        data = fixtures.fields(database=database, count_value=count, count_raw=f'{count} results', query_raw=f'Q {job}')
        return self.store.complete_job(job, data, CONTEXT, new_run=True)

    def export(self, name, text):
        path = self.store.path('01_HamExport/' + name)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding='utf-8')
        old = time.time() - 10
        os.utime(path, (old, old))
        ham_export.scan(self.store)

    def items(self):
        return [o['data'] for o in self.api.objects['items'].values()]

    def collection(self, name):
        return next(c['key'] for c in self.api.objects['collections'].values() if c['data']['name'] == name)

    def test_one_item_per_publication_in_every_search_collection(self):
        self.run_('a', 4, 'Scopus'), self.run_('b', 2, 'IEEE Xplore')
        self.export('S001_Scopus.ris', ris({'title': 'Shared paper about chunking strategies', 'doi': '10.1/shared', 'eid': '1'},
                                           {'title': LONG, 'eid': '2'},
                                           {'title': 'Only in Scopus, a long enough title', 'doi': '10.1/scopus', 'eid': '3'},
                                           {'title': 'Short', 'eid': '4'}))
        self.export('S002_IEEE.ris', ris({'title': 'Shared paper about chunking strategies', 'doi': '10.1/SHARED'},
                                         {'title': LONG.upper() + '.', 'doi': '10.1/with-doi-in-ieee'}))
        text, results = zotero_ris.run(self.store, self.writer)
        self.assertIn('6 kayıt → 4 tekil Zotero öğesi', text)
        self.assertEqual(len(self.items()), 4)
        scopus, ieee = self.collection('S001_Scopus'), self.collection('S002_IEEE')
        root = next(c for c in self.api.objects['collections'].values() if c['data']['name'] == 'S001_Scopus')['data']['parentCollection']
        self.assertEqual(root, 'U8THQFWA')
        members = lambda key: sum(1 for i in self.items() if key in i['collections'])
        self.assertEqual((members(scopus), members(ieee), members('BX38VWI6')), (4, 2, 4))
        self.assertEqual([(r['display_id'], r['created'], r['reused'], len(r['keys'])) for r in results], [('S001', 4, 0, 4), ('S002', 0, 2, 2)])
        rows = {r['display_id']: r for r in zotero_ris.status(self.store)}
        self.assertEqual((rows['S001']['unique_items'], rows['S002']['reused']), (4, 2))
        again, _ = zotero_ris.run(self.store, self.writer)
        self.assertEqual(len(self.items()), 4)
        self.assertIn('Yeni: 0', again)

    def test_items_already_in_the_library_are_reused_including_acm_ones(self):
        acm_run = self.run_('c', 1, acm.DATABASE)
        record = {'doi': '10.1145/acm1', 'type': 'research-article', 'published': '19 July 2026', 'title': 'An ACM paper on retrieval',
                  'authors': ['Rui Qi'], 'venue': 'Proceedings of SIGIR', 'pages': '1–2', 'page': 1, 'position': 1}
        self.writer.import_acm([{'doi': record['doi'], 'item': acm.zotero_item(acm.complete(record, None))}], acm_run['id'])
        self.api.seed('items', dict(key='USERITEM', itemType='journalArticle', title='A paper the user added by hand long title',
                                    DOI='10.1/manual', collections=[]))
        self.run_('a', 2, 'Scopus')
        self.export('S002_Scopus.ris', ris({'title': 'An ACM paper on retrieval', 'doi': '10.1145/ACM1', 'eid': '9'},
                                           {'title': 'A paper the user added by hand long title', 'doi': '10.1/manual', 'eid': '8'}))
        text, results = zotero_ris.run(self.store, self.writer)
        self.assertEqual(len(self.items()), 2)
        self.assertEqual((results[0]['created'], results[0]['reused']), (0, 2))
        scopus = self.collection('S002_Scopus')
        self.assertTrue(all(scopus in i['collections'] and 'BX38VWI6' in i['collections'] for i in self.items()))

    def test_only_scopus_and_ieee_exports_that_are_not_set_aside(self):
        self.run_('a', 1, 'Scopus'), self.run_('b', 1, acm.DATABASE)
        self.export('_aktarilmayacak/S001_Scopus.ris', ris({'title': 'Not exported broad search title', 'doi': '10.1/x', 'eid': '1'}))
        self.export('S002_ACM.ris', ris({'title': 'ACM file is handled by the ACM collection', 'doi': '10.1/y'}))
        self.assertEqual(zotero_ris.plan(self.store), [])
        with self.assertRaises(Exception):
            zotero_ris.run(self.store, self.writer)


if __name__ == '__main__':
    unittest.main()
