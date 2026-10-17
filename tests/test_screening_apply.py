import tempfile
import unittest
from unittest.mock import patch

from literature import screening
from literature.storage import Store, ValidationError
from literature.zotero import parse_note, UNKNOWN_KEY
from literature.zotero_writer import ZoteroWriter, WRITER_SCHEMA
from tests.test_zotero_writer import FakeLocalAPI

GECEN, HARIC, ADAY = 'VHIBG6RK', 'RR4X8Y8B', 'BX38VWI6'
TITLES = {'AAAA2222': 'Video RAG for Lectures', 'BBBB2222': 'Chunking for Turkish QA',
          'CCCC2222': 'Hybrid Retrieval', 'DDDD2222': 'A Vision Paper'}


def decisions(approved=True):
    rows = [
        dict(key='AAAA2222', baslik=TITLES['AAAA2222'], durum='Hariç', bakilan='Başlık', gerekce_kodu='H5',
             gerekce='Bağlam uyuşmuyor', kanit_alinti='Video RAG', tam_metin='', erisim_on_kontrol=''),
        dict(key='BBBB2222', baslik=TITLES['BBBB2222'], durum='Geçti', bakilan='Özet', gerekce_kodu='', gerekce='',
             kanit_alinti='chunk sizes', tam_metin='Seçildi', erisim_on_kontrol='Kontrol edilecek'),
        dict(key='CCCC2222', baslik=TITLES['CCCC2222'], durum='Geçti', bakilan='Özet', gerekce_kodu='', gerekce='',
             kanit_alinti='BM25', tam_metin='Yedek', erisim_on_kontrol='Kontrol edilecek'),
        dict(key='DDDD2222', baslik=TITLES['DDDD2222'], durum='Hariç', bakilan='Özet', gerekce_kodu='H2',
             gerekce='Deneysel sonuç raporlanmamış', kanit_alinti='not yet validated', tam_metin='', erisim_on_kontrol=''),
    ]
    data = {'sema': 1, 'onay': {'onaylandi': False, 'onaylayan': '', 'tarih': ''}, 'kayitlar': rows}
    if approved:
        data['onay'] = {'onaylandi': True, 'onaylayan': 'Hasan Basri Taşkın', 'tarih': '18.10.2026',
                        'ozet': screening.digest(data)}
    return data


class ScreeningApplyTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.store = Store(self.tmp.name)
        self.store.db.executescript(WRITER_SCHEMA)
        self.store.update_settings({'library': 'groups/6718452', 'zotero_mode': 'local', 'collection_mapping': {
            'candidate': ADAY, 'title_abstract': GECEN, 'excluded_title': HARIC}})
        self.api = FakeLocalAPI()
        self.api.seed('collections', dict(key=GECEN, name='02_BaslikOzet_Gecen', parentCollection=False))
        self.api.seed('collections', dict(key=HARIC, name='05_Haric_BaslikOzet', parentCollection=False))
        for key, title in TITLES.items():
            self.api.seed('items', dict(key=key, itemType='journalArticle', title=title, collections=[ADAY, 'S005KEYS'],
                                        tags=[{'tag': 'kullanıcı'}]))
        self.credentials = {}
        self.patches = [patch('literature.zotero_writer.load_api_key', side_effect=lambda name: self.credentials.get(name, '')),
                        patch('literature.zotero_writer.save_api_key', side_effect=lambda key, name: self.credentials.__setitem__(name, key))]
        for p in self.patches:
            p.start()
        self.writer = ZoteroWriter(self.store, self.api)
        self.assertTrue(self.writer.preflight(authorize=True)['ready'])
        self.api.requests.clear()

    def tearDown(self):
        for p in self.patches:
            p.stop()
        self.store.close()
        self.tmp.cleanup()

    def item(self, key):
        return self.api.objects['items'][key]['data']

    def notes(self):
        return [o['data'] for o in self.api.objects['items'].values() if o['data'].get('itemType') == 'note']

    def writes(self):
        return [r for r in self.api.requests if r[0] in ('POST', 'PATCH')]

    def test_approved_decisions_are_added_without_removing_anything(self):
        result = self.writer.apply_screening(decisions())
        self.assertEqual((result['updated'], result['notes_created'], result['failed']), (4, 2, 0))
        access = [o['data'] for o in self.api.objects['collections'].values() if o['data']['name'] == '06_Erisim_Kontrol']
        self.assertEqual(len(access), 1)
        self.assertIs(access[0]['parentCollection'], False)
        excluded, selected, spare = self.item('AAAA2222'), self.item('BBBB2222'), self.item('CCCC2222')
        self.assertEqual(excluded['collections'], [ADAY, 'S005KEYS', HARIC])
        self.assertEqual(selected['collections'], [ADAY, 'S005KEYS', GECEN, access[0]['key']])
        self.assertEqual(spare['collections'], [ADAY, 'S005KEYS', GECEN])  # Yedek: no access check
        self.assertEqual([t['tag'] for t in excluded['tags']], ['kullanıcı', 'H5'])
        self.assertEqual([t['tag'] for t in selected['tags']], ['kullanıcı', 'TamMetin-Secildi'])
        self.assertEqual([t['tag'] for t in spare['tags']], ['kullanıcı', 'TamMetin-Yedek'])
        notes = {n['parentItem']: parse_note(n['note']) for n in self.notes()}
        self.assertEqual(set(notes), {'AAAA2222', 'DDDD2222'})
        self.assertNotIn(UNKNOWN_KEY, notes['AAAA2222'])
        self.assertEqual((notes['DDDD2222']['Gerekçe kodu'], notes['DDDD2222']['Karar veren'], notes['DDDD2222']['Aşama']),
                         ('H2', 'Hasan Basri Taşkın', 'Başlık-özet'))
        states = dict(self.store.db.execute('SELECT item_key,state FROM screening_applications'))
        self.assertEqual(set(states.values()), {'applied'})

    def test_second_run_sends_nothing_and_writes_no_second_note(self):
        self.writer.apply_screening(decisions())
        self.api.requests.clear()
        again = self.writer.apply_screening(decisions())
        self.assertEqual(self.writes(), [])
        self.assertEqual((again['updated'], again['unchanged'], again['notes_existing']), (0, 4, 2))
        self.assertEqual(len(self.notes()), 2)

    def test_nothing_is_sent_without_approval_or_after_a_change(self):
        with self.assertRaises(ValidationError):
            self.writer.apply_screening(decisions(approved=False))
        changed = decisions()
        changed['kayitlar'][2]['tam_metin'] = 'Seçildi'
        with self.assertRaises(ValidationError):
            self.writer.apply_screening(changed)
        self.assertEqual(self.api.requests, [])

    def test_mismatch_with_01_aday_stops_before_any_write(self):
        self.api.seed('items', dict(self.item('CCCC2222'), title='Hybrid Retrieval (edited)'))
        with self.assertRaises(ValidationError) as caught:
            self.writer.apply_screening(decisions())
        self.assertIn('CCCC2222: başlık Zotero kaydıyla aynı değil', str(caught.exception))
        self.assertEqual(self.writes(), [])

    def test_lost_response_after_notes_were_saved_leaves_one_note_each(self):
        self.api.timeout_after_items = True
        first = self.writer.apply_screening(decisions())
        self.assertEqual(first['notes_created'], 0)
        self.assertEqual(first['failed'], 2)
        self.assertEqual(len(self.notes()), 2)  # Zotero saved them; the reply was lost
        writer = ZoteroWriter(self.store, self.api)
        self.assertTrue(writer.preflight()['ready'])
        again = writer.apply_screening(decisions())
        self.assertEqual((again['failed'], again['notes_existing'], again['notes_created']), (0, 2, 0))
        self.assertEqual(len(self.notes()), 2)

    def test_identical_note_already_in_zotero_is_reused_even_if_html_differs(self):
        lines = screening.note_lines(decisions()['kayitlar'][0], decisions()['onay'])
        self.api.seed('items', dict(key='NNNN2222', itemType='note', parentItem='AAAA2222',
                                    note='<div data-schema-version="9">' + screening.note_html(lines) + '</div>'))
        result = self.writer.apply_screening(decisions())
        self.assertEqual((result['notes_existing'], result['notes_created']), (1, 1))
        self.assertEqual(len(self.notes()), 2)

    def test_concurrent_user_change_is_kept(self):
        self.api.conflict_patch = True
        result = self.writer.apply_screening(decisions())
        self.assertEqual(result['failed'], 0)
        changed = [k for k in TITLES if 'USER2345' in self.item(k)['collections']]
        self.assertEqual(len(changed), 1)
        self.assertTrue({ADAY, 'USER2345'} <= set(self.item(changed[0])['collections']))

    def test_unmapped_or_renamed_target_collection_is_refused(self):
        self.api.seed('collections', dict(key=HARIC, name='05_Baska', parentCollection=False))
        with self.assertRaises(ValidationError):
            self.writer.apply_screening(decisions())
        self.assertEqual(self.writes(), [])


if __name__ == '__main__':
    unittest.main()
