import tempfile
import unittest
from pathlib import Path

from PIL import Image
from literature.exports import check_project, delivery_report
from literature.storage import Store
from literature.zotero import import_items


FULL = {'Karar': 'Dahil', 'Yayın türü': 'Konferans bildirisi', 'Kalite sınıfı ve yılı': 'CORE A* (2023)',
        'Okuyan kişi': 'Hasan Basri Taşkın', 'Okuma düzeyi': '2', 'Amaç/problem': 'p', 'Yöntem': 'y',
        'Karşılaştırılan yöntemler': 'b', 'Veri seti ve dil': 'v', 'Deney düzeni': 'd', 'Değerlendirme metrikleri': 'm',
        'Temel bulgu': 'Recall@5 = 0,81 (Tablo 3, s. 6)', 'Kaynak ihtiyacı': 'k', 'Açık kod/veri': 'Hayır',
        'Yazarların sınırlılıkları': 's', 'Benim değerlendirmem': 'e', 'Tema': 'T1', 'Tezle ilişki': 'AS1',
        'Anotasyon': 'Bir. İki. Üç.'}


def paper(key, collections, year='2025'):
    return {'key': key, 'data': {'itemType': 'conferencePaper', 'title': 'Başlık ' + key, 'date': year,
                                 'creators': [{'creatorType': 'author', 'lastName': 'Yazar'}], 'collections': collections}}


def note(parent, fields):
    html = ''.join(f'<p>{k}: {v}</p>' for k, v in fields.items())
    return {'key': 'N' + parent, 'data': {'itemType': 'note', 'parentItem': parent, 'note': html}}


class DeliveryReportTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.store = Store(self.root)
        self.store.update_settings({'operator': 'Hasan Basri Taşkın', 'window_start': 2024})
        png = self.root / 'x.png'
        Image.new('RGB', (40, 30), 'white').save(png)
        self.store.begin_job('a', {})
        self.store.save_capture('a', png.read_bytes(), captured_at='2026-10-16T10:00:00+00:00')
        self.store.complete_job('a', dict(database='Scopus', query_raw='TITLE-ABS-KEY(x)', query_verified=True,
                                          fields='TITLE-ABS-KEY', filters=[], count_raw='6', count_value=6,
                                          count_qualifier='exact', status='complete'), {}, new_run=True)
        self.mapping = {'included': 'IN', 'excluded': 'EX', 'excluded_title': 'ET', 'title_abstract': 'TA'}
        self.collections = {'C1': 'S001', 'C7': 'S007'}

    def tearDown(self):
        self.store.close()
        self.tmp.cleanup()

    def messages(self, report):
        return '\n'.join(i['message'] for i in report['issues'])

    def test_prisma_limits_and_field_issues(self):
        items = [paper('P1', ['C1', 'IN']), note('P1', dict(FULL, **{'Matris ID': 'L001', 'Çekirdek adayı': 'Evet', 'Okuma düzeyi': '3'})),
                 paper('P2', ['C1', 'IN'], '2020'), note('P2', dict(FULL, **{'Matris ID': 'L001', 'Yayın türü': 'Derleme',
                                                                             'Temel bulgu': 'iyi', 'Kalite sınıfı ve yılı': 'Q3'})),
                 paper('P3', ['C1', 'EX']), note('P3', {'Karar': 'Hariç', 'Gerekçe kodu': 'H2', 'Karar veren': 'Esra'}),
                 paper('P4', ['C1', 'EX']), note('P4', {'Karar': 'Hariç'}),
                 paper('P5', ['C1', 'ET']), paper('P6', ['C7', 'TA'])]
        import_items(self.store, 'groups/1', items, self.mapping, self.collections)
        report = delivery_report(self.store)
        prisma = report['prisma']
        self.assertEqual((prisma['aktarilan_kayit'], prisma['benzersiz_kayit'], prisma['cikarilan_tekrar']), (5, 6, None))
        self.assertEqual((prisma['baslik_ozet_haric'], prisma['tam_metni_degerlendirilen'], prisma['tam_metin_haric'],
                          prisma['dahil'], prisma['karar_bekleyen']), (1, 4, 2, 2, 1))
        self.assertEqual(prisma['tam_metin_haric_kodlar'], {'H2': 1, 'kodsuz': 1})
        limits = {l['kural'].split(' (')[0]: (l['deger'], l['tamam']) for l in report['limits']}
        self.assertEqual(limits['Dahil edilen kaynak ≥ 80'], (2, False))
        self.assertEqual(limits['Çekirdek'], (1, False))
        self.assertEqual(limits['Derleme ≤ 10'], (1, True))
        self.assertEqual(limits['Pencere'], (1, True))
        self.assertEqual(limits['Q1–Q2 / CORE A*–A ≥ yarı'], (1, True))
        text = self.messages(report)
        for expected in ['Matris ID iki kaynakta', 'İstisna gerekçesi boş', 'sayfa/tablo numarası yok',
                         'hariç gerekçe kodu (H1–H6) yok', 'Karar veren boş', 'S007 koleksiyonu var',
                         'Zotero\'daki benzersiz kayıttan', 'henüz başlık-özet', 'Literatur_PDF/L001_Yazar_2025_BaslikP1.pdf bulunamadı']:
            self.assertIn(expected, text)
        self.assertTrue(all(m.startswith(('HATA:', 'UYARI:')) for m in check_project(self.store)))

    def test_decision_mismatch_and_unknown_field(self):
        items = [paper('P1', ['C1', 'IN']), note('P1', dict(FULL, **{'Matris ID': 'L001', 'Karar': 'Hariç', 'Gerekce': 'x'}))]
        import_items(self.store, 'groups/1', items, self.mapping, self.collections)
        text = self.messages(delivery_report(self.store))
        self.assertIn('Karar: Hariç yazıyor', text)
        self.assertIn('tanınmayan alan adı — Gerekce', text)

    def test_title_abstract_stage_boxes_follow_zotero_tags_and_the_decisions_file(self):
        import json
        from literature import screening
        def tagged(key, collections, *tags):
            item = paper(key, collections)
            item['data']['tags'] = [{'tag': t} for t in tags]
            return item
        items = [tagged('P1', ['C1', 'ET'], 'H5'), tagged('P2', ['C1', 'ET'], 'H2'), tagged('P3', ['C1', 'ET']),
                 tagged('P4', ['C1', 'TA'], 'TamMetin-Secildi'), tagged('P5', ['C1', 'TA'], 'TamMetin-Yedek'),
                 tagged('P6', ['C1', 'TA'], 'TamMetin-Yedek'), paper('P7', ['C1'])]
        import_items(self.store, 'groups/1', items, self.mapping, self.collections)
        prisma = delivery_report(self.store)['prisma']
        self.assertEqual(prisma['baslik_ozet_haric_kodlar'], {'H2': 1, 'H5': 1, 'kodsuz': 1})
        self.assertEqual((prisma['baslik_ozet_gecen'], prisma['tam_metin_icin_secilen_bekleyen'],
                          prisma['yedek_tam_metni_degerlendirilmeyen'], prisma['karar_bekleyen']), (3, 1, 2, 2))
        self.assertNotIn('baslik_incelenen', prisma)
        rows = [dict(key='P1', baslik='Başlık P1', durum='Hariç', bakilan='Başlık', gerekce_kodu='H5', kanit_alinti='P1'),
                dict(key='P4', baslik='Başlık P4', durum='Geçti', bakilan='Özet', kanit_alinti='x', tam_metin='Seçildi')]
        data = {'sema': 1, 'onay': {}, 'kayitlar': rows}
        data['onay'] = {'onaylandi': True, 'onaylayan': 'Hasan Basri Taşkın', 'tarih': '18.10.2026', 'ozet': screening.digest(data)}
        path = self.store.path(screening.RELATIVE.as_posix())
        path.parent.mkdir(parents=True)
        path.write_text(json.dumps(data, ensure_ascii=False), encoding='utf-8')
        report = delivery_report(self.store)
        self.assertEqual((report['prisma']['baslik_incelenen'], report['prisma']['baslik_haric'], report['prisma']['ozet_haric']), (2, 1, 0))
        rows.append(dict(key='P7', baslik='Başlık P7', durum='Taranmadı'))
        data['onay']['ozet'] = screening.digest(data)
        path.write_text(json.dumps(data, ensure_ascii=False), encoding='utf-8')
        prisma = delivery_report(self.store)['prisma']
        self.assertEqual((prisma['taranmayan'], prisma['karar_bekleyen']), (1, 1))  # P7 is outside the scope, P4 waits for full text
        self.assertIn('eleme karar dosyasında başlık-özet hariç 1 / geçen 1', self.messages(report))

    def test_items_merged_in_zotero_are_no_longer_doi_duplicates(self):
        first, second = paper('P1', ['C1']), paper('P2', ['C1'])
        first['data']['DOI'] = second['data']['DOI'] = '10.1/x'
        self.assertEqual(len(import_items(self.store, 'groups/1', [first, second], self.mapping, self.collections)['duplicates']), 1)
        self.assertEqual(import_items(self.store, 'groups/1', [first], self.mapping, self.collections)['duplicates'], [])

    def test_prisma_pdf_numbers_follow_the_report(self):
        from unittest.mock import patch
        from literature import exports
        font = Path('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf')
        if not exports.FONT.exists() and not font.exists():
            self.skipTest('Türkçe yazı tipi yok')
        def tagged(key, collections, *tags):
            item = paper(key, collections)
            item['data']['tags'] = [{'tag': t} for t in tags]
            return item
        items = [tagged('P1', ['C1', 'ET'], 'H5'), tagged('P2', ['C1', 'TA'], 'TamMetin-Secildi'),
                 tagged('P3', ['C1', 'TA'], 'TamMetin-Yedek'), paper('P4', ['C1', 'IN']), paper('P5', ['C1', 'EX']),
                 note('P5', {'Karar': 'Hariç', 'Gerekçe kodu': 'H3'}), paper('P6', ['C1', 'EX']),
                 note('P6', {'Karar': 'Hariç', 'Gerekçe kodu': 'H2'})]
        import_items(self.store, 'groups/1', items, self.mapping, self.collections)
        with patch.object(exports, 'FONT', exports.FONT if exports.FONT.exists() else font):
            result = exports.export_prisma(self.store)
        b = result['kutular']
        self.assertEqual((b['bulunan'], b['taranan'], b['baslik_ozet_haric'], b['gecen'], b['yedek'], b['istenen']), (6, 6, 1, 5, 1, 4))
        self.assertEqual((b['erisilemeyen'], b['degerlendirilen'], b['tam_metin_haric'], b['tam_metin_kodlar'], b['dahil']),
                         (1, 2, 1, {'H2': 1}, 1))
        self.assertEqual(b['karar_bekleyen'], 1)
        self.assertTrue(Path(result['pdf']).read_bytes().startswith(b'%PDF'))


if __name__ == '__main__':
    unittest.main()
