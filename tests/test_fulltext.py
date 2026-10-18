import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from literature import fulltext, fulltext_job, screening_job
from literature.pdf_archive import build_archive
from literature.storage import Store, ValidationError
from literature.zotero import UNKNOWN_KEY, import_items, parse_note
from literature.zotero_writer import WRITER_SCHEMA, ZoteroWriter
from tests.test_zotero_writer import FakeLocalAPI

ADAY, GECEN, DAHIL, HARIC_TM, HARIC_BO = 'BX38VWI6', 'VHIBG6RK', 'VAH7RFJV', 'SNNEQK8F', 'RR4X8Y8B'
MAPPING = {
    'candidate': ADAY,
    'title_abstract': GECEN,
    'included': DAHIL,
    'excluded': HARIC_TM,
    'excluded_title': HARIC_BO,
}

TITLES = {
    'ITEM0001': 'Benchmarking Retrieval-Augmented Generation in Turkish',
    'ITEM0002': 'Promoted Spare Legal RAG Paper',
    'ITEM0003': 'Proceeding Preface Without Method Details',
    'ITEM0004': 'Unused Spare Paper Kept in Pool',
}


def sample_note_text(matrix_id='L001', pdf_name='L001_Aksoy_2026_Benchmarking.pdf',
                     reader='Hasan Basri Taşkın', level='3', date_str='14.10.2026', core='Evet'):
    return '\n'.join([
        f'Matris ID: {matrix_id}',
        'Karar: Dahil',
        'Yayın türü: Dergi makalesi',
        'Kalite sınıfı ve yılı: Q1 (SJR 2025; Engineering Applications of Artificial Intelligence)',
        'Kalite kaynağı: https://www.scimagojr.com/journalsearch.php?q=24082&tip=sid',
        f'Okuyan kişi: {reader}',
        f'Okuma düzeyi: {level}',
        f'Okuma tarihi: {date_str}',
        f'Çekirdek adayı: {core}',
        'Amaç/problem: Türkçe kurumsal belgelerde RAG erişim ve üretim kalitesini ölçmek.',
        'Yöntem: Hibrit BM25 + yoğun erişim ve yeniden sıralama hattı.',
        'Karşılaştırılan yöntemler: Yalnız BM25, yalnız yoğun erişim ve hibrit RAG.',
        'Veri seti ve dil: Türkçe soru-cevap veri seti (1.200 soru).',
        'Deney düzeni: 5 katlı çapraz doğrulama, k=5 erişim parçası.',
        'Değerlendirme metrikleri: Recall@5, MRR@10 ve F1.',
        'Temel bulgu: Hibrit erişim Recall@5 değerini 0,72\'den 0,86\'ya yükseltmiştir (Tablo 2, s. 5).',
        'Kaynak ihtiyacı: Tek RTX 4090 GPU üzerinde ortalama 1,4 sn gecikme (Tablo 4, s. 7).',
        'Açık kod/veri: Evet (https://github.com/example/turkish-rag)',
        'Yazarların sınırlılıkları: Yalnız tek kurumsal alanda değerlendirilmiştir (s. 9).',
        'Benim değerlendirmem: Tezdeki Türkçe mevzuat erişim hattı için doğrudan karşılaştırma tabanı sağlar.',
        'Tema: T2_Erisim',
        'Tezle ilişki: AS1',
        'Kanıt sayfaları: s. 4-7, Tablo 2 ve Tablo 4',
        'İstisna gerekçesi: ',
        f'Yerel PDF: {pdf_name}',
        'PDF bağlantısı: https://doi.org/10.1016/j.engappai.2026.100001',
        'Anotasyon: Türkçe RAG sistemlerinde hibrit erişimin etkisini inceleyen kapsamlı bir çalışmadır. '
        'Deneylerde Recall@5 = 0,86 elde edilmiştir (Tablo 2, s. 5). Tezimizin AS1 araştırma sorusuyla doğrudan ilişkilidir.',
    ])


def sample_decisions(root=None, approved=False):
    rows = [
        {
            'key': 'ITEM0001',
            'baslik': TITLES['ITEM0001'],
            'durum': 'Dahil',
            'matris_id': 'L001',
            'sorumlu': 'Hasan Basri Taşkın',
            'not_dosyasi': '03_Calisma/Okuma_Taslaklari/L001.txt',
            'yerel_pdf': 'L001_Aksoy_2026_Benchmarking.pdf',
            'gerekce_kodu': '',
            'gerekce': '',
            'karar_veren': 'Hasan Basri Taşkın',
            'karar_tarihi': '14.10.2026',
        },
        {
            'key': 'ITEM0002',
            'baslik': TITLES['ITEM0002'],
            'durum': 'Dahil',
            'matris_id': 'L101',
            'sorumlu': 'Esra Sultan Doğan',
            'not_dosyasi': '03_Calisma/Okuma_Taslaklari/L101.txt',
            'yerel_pdf': 'L101_Dogan_2025_LegalRAG.pdf',
            'gerekce_kodu': '',
            'gerekce': '',
            'karar_veren': 'Esra Sultan Doğan',
            'karar_tarihi': '15.10.2026',
        },
        {
            'key': 'ITEM0003',
            'baslik': TITLES['ITEM0003'],
            'durum': 'Hariç',
            'matris_id': '',
            'sorumlu': 'Hasan Basri Taşkın',
            'not_dosyasi': '',
            'yerel_pdf': '',
            'gerekce_kodu': 'H3',
            'gerekce': 'Tam metin incelendiğinde hakemli araştırma makalesi olmadığı (derleme/önsöz) görüldü.',
            'karar_veren': 'Hasan Basri Taşkın',
            'karar_tarihi': '18.10.2026',
        },
        {
            'key': 'ITEM0004',
            'baslik': TITLES['ITEM0004'],
            'durum': 'Yedek',
            'matris_id': '',
            'sorumlu': 'Esra Sultan Doğan',
            'not_dosyasi': '',
            'yerel_pdf': '',
            'gerekce_kodu': '',
            'gerekce': 'Tam metin hedef kotası (83 makale) dolduğu için kullanılmayan yedek aday olarak 02_BaslikOzet_Gecen altında bırakıldı.',
            'karar_veren': 'Esra Sultan Doğan',
            'karar_tarihi': '18.10.2026',
        },
    ]
    data = {'sema': 1, 'onay': {'onaylandi': False, 'onaylayan': '', 'tarih': ''}, 'kayitlar': rows}
    if approved:
        data['onay'] = {
            'onaylandi': True,
            'onaylayan': 'Hasan Basri Taşkın',
            'tarih': '18.10.2026',
            'ozet': fulltext.digest(data, root),
        }
    return data


def write_project_files(root):
    root = Path(root)
    notes_dir = root / '03_Calisma' / 'Okuma_Taslaklari'
    notes_dir.mkdir(parents=True, exist_ok=True)
    (notes_dir / 'L001.txt').write_text(
        sample_note_text('L001', 'L001_Aksoy_2026_Benchmarking.pdf', 'Hasan Basri Taşkın', '3', '14.10.2026', 'Evet'),
        encoding='utf-8',
    )
    (notes_dir / 'L101.txt').write_text(
        sample_note_text('L101', 'L101_Dogan_2025_LegalRAG.pdf', 'Esra Sultan Doğan', '2', '15.10.2026', 'Hayır'),
        encoding='utf-8',
    )
    cand_dir = root / '04_PDF_Aday'
    cand_dir.mkdir(parents=True, exist_ok=True)
    (cand_dir / 'L001_Aksoy_2026_Benchmarking.pdf').write_bytes(b'%PDF-1.7 L001')
    (cand_dir / 'L101_Dogan_2025_LegalRAG.pdf').write_bytes(b'%PDF-1.7 L101')


class FulltextUnitTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        write_project_files(self.root)

    def tearDown(self):
        self.tmp.cleanup()

    def test_valid_decisions_and_notes_pass_check_and_counts(self):
        data = sample_decisions(self.root)
        self.assertEqual(fulltext.check(data, TITLES, self.root), [])
        c = fulltext.counts(data, self.root)
        self.assertEqual((c['toplam'], c['dahil'], c['haric'], c['yedek_iade']), (4, 2, 1, 1))
        self.assertEqual(c['haric_kod'], {'H3': 1})
        self.assertEqual(c['okuyanlar'], {'Hasan Basri Taşkın': 1, 'Esra Sultan Doğan': 1})
        self.assertEqual((c['cekirdek'], c['kaliteli']), (1, 2))

    def test_editing_a_reading_note_invalidates_approval_digest(self):
        path = self.root / fulltext.RELATIVE
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(sample_decisions(self.root), ensure_ascii=False), encoding='utf-8')
        backups = self.root / 'Yedekler'
        fulltext.approve(path, 'Hasan Basri Taşkın', TITLES, backups, root=self.root, today='18.10.2026')
        loaded = fulltext.load(path)
        self.assertTrue(fulltext.approved(loaded, self.root))
        self.assertEqual(len(list(backups.glob('tam_metin_kararlari_onay_oncesi_*.json'))), 1)
        # Modify L001.txt after approval -> digest changes and invalidates approval
        note_file = self.root / '03_Calisma' / 'Okuma_Taslaklari' / 'L001.txt'
        note_file.write_text(note_file.read_text(encoding='utf-8').replace('0,86', '0,87'), encoding='utf-8')
        self.assertFalse(fulltext.approved(loaded, self.root))
        self.assertIn('değişmiş', fulltext.approval_state(loaded, self.root))

    def test_missing_pdf_or_missing_page_evidence_is_reported(self):
        (self.root / '04_PDF_Aday' / 'L101_Dogan_2025_LegalRAG.pdf').unlink()
        note_file = self.root / '03_Calisma' / 'Okuma_Taslaklari' / 'L001.txt'
        note_file.write_text(
            note_file.read_text(encoding='utf-8').replace('(Tablo 2, s. 5)', 'kanıt yazılmadı'),
            encoding='utf-8',
        )
        problems = fulltext.check(sample_decisions(self.root), TITLES, self.root)
        text = '\n'.join(problems)
        self.assertIn('L001: Temel bulgu alanında sayfa/tablo kanıtı yok', text)
        self.assertIn('L101: yerel PDF bulunamadı', text)


class FulltextApplyAndArchiveTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        write_project_files(self.root)
        self.store = Store(self.root)
        self.store.db.executescript(WRITER_SCHEMA)
        self.store.update_settings({
            'library': 'groups/6718452',
            'zotero_mode': 'local',
            'operator': 'Hasan Basri Taşkın',
            'collection_mapping': MAPPING,
            'zotero_data_dir': str(self.root / 'MissingZoteroStorage'),
        })
        self.api = FakeLocalAPI()
        self.api.seed('collections', dict(key=ADAY, name='01_Aday', parentCollection=False))
        self.api.seed('collections', dict(key=GECEN, name='02_BaslikOzet_Gecen', parentCollection=False))
        self.api.seed('collections', dict(key=DAHIL, name='03_TamMetin_Dahil', parentCollection=False))
        self.api.seed('collections', dict(key=HARIC_TM, name='04_Haric_TamMetin', parentCollection=False))
        self.api.seed('collections', dict(key=HARIC_BO, name='05_Haric_BaslikOzet', parentCollection=False))
        # ITEM0001 was initially selected, ITEM0002 was initially spare (promoted), ITEM0003 selected (now H3), ITEM0004 selected (now spare)
        initial_tags = {
            'ITEM0001': ['TamMetin-Secildi'],
            'ITEM0002': ['TamMetin-Yedek'],
            'ITEM0003': ['TamMetin-Secildi'],
            'ITEM0004': ['TamMetin-Secildi'],
        }
        for key, title in TITLES.items():
            self.api.seed('items', dict(
                key=key,
                itemType='journalArticle',
                title=title,
                date='2026',
                collections=[ADAY, GECEN],
                tags=[{'tag': t} for t in initial_tags[key]],
            ))
        self.credentials = {}
        self.patches = [
            patch('literature.zotero_writer.load_api_key', side_effect=lambda name: self.credentials.get(name, '')),
            patch('literature.zotero_writer.save_api_key', side_effect=lambda key, name: self.credentials.__setitem__(name, key)),
        ]
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

    def test_apply_fulltext_reconciles_collections_tags_notes_and_updates_on_edit(self):
        data = sample_decisions(self.root, approved=True)
        result = self.writer.apply_fulltext(data, root=self.root)
        self.assertEqual((result['included'], result['excluded'], result['notes_created'], result['failed']), (2, 1, 3, 0))

        # Promoted spare ITEM0002 now has TamMetin-Secildi and NOT TamMetin-Yedek, and is in 03_TamMetin_Dahil
        self.assertIn(DAHIL, self.item('ITEM0002')['collections'])
        self.assertEqual([t['tag'] for t in self.item('ITEM0002')['tags']], ['TamMetin-Secildi'])

        # Excluded ITEM0003 is in 04_Haric_TamMetin with H3 + TamMetin-Secildi
        self.assertIn(HARIC_TM, self.item('ITEM0003')['collections'])
        self.assertEqual(set(t['tag'] for t in self.item('ITEM0003')['tags']), {'TamMetin-Secildi', 'H3'})

        # Demoted/unused spare ITEM0004 stays in 02_BaslikOzet_Gecen and switches tag to TamMetin-Yedek
        self.assertEqual(self.item('ITEM0004')['collections'], [ADAY, GECEN])
        self.assertEqual([t['tag'] for t in self.item('ITEM0004')['tags']], ['TamMetin-Yedek'])

        # Notes parse cleanly without unknown fields
        notes_by_parent = {n['parentItem']: parse_note(n['note']) for n in self.notes()}
        self.assertEqual(set(notes_by_parent), {'ITEM0001', 'ITEM0002', 'ITEM0003'})
        for parsed in notes_by_parent.values():
            self.assertNotIn(UNKNOWN_KEY, parsed)
        self.assertEqual(notes_by_parent['ITEM0001']['Matris ID'], 'L001')
        self.assertEqual(notes_by_parent['ITEM0003']['Gerekçe kodu'], 'H3')

        # Second run is a no-op
        self.api.requests.clear()
        again = self.writer.apply_fulltext(data, root=self.root)
        self.assertEqual(self.writes(), [])
        self.assertEqual((again['updated'], again['unchanged'], again['notes_existing']), (0, 4, 3))

        # Editing L001.txt, re-approving, and re-running updates the existing note in place
        note_file = self.root / '03_Calisma' / 'Okuma_Taslaklari' / 'L001.txt'
        note_file.write_text(note_file.read_text(encoding='utf-8').replace('0,86', '0,89'), encoding='utf-8')
        updated_data = sample_decisions(self.root, approved=True)
        self.api.requests.clear()
        third = self.writer.apply_fulltext(updated_data, root=self.root)
        self.assertEqual((third['notes_existing'], third['notes_created'], len(self.notes())), (3, 0, 3))
        notes_by_parent = {n['parentItem']: parse_note(n['note']) for n in self.notes()}
        self.assertIn('0,89', notes_by_parent['ITEM0001']['Temel bulgu'])

        # Mirroring back from Zotero marks applied included items as verified=1 and allows PDF archive from 04_PDF_Aday
        import_items(self.store, 'groups/6718452', list(self.api.objects['items'].values()), MAPPING, {})
        rows = dict(self.store.db.execute('SELECT item_key, verified FROM papers').fetchall())
        self.assertEqual((rows['ITEM0001'], rows['ITEM0002'], rows['ITEM0003']), (1, 1, 0))

        archive_report = build_archive(self.store)
        self.assertEqual(sorted(archive_report['copied']), [
            'L001_Aksoy_2026_Benchmarking.pdf',
            'L101_Dogan_2025_LegalRAG.pdf',
        ])
        self.assertEqual(archive_report['missing_pdf'], [])


if __name__ == '__main__':
    unittest.main()
