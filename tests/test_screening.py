import json
import tempfile
import unittest
from pathlib import Path

from literature import screening
from literature.storage import ValidationError


def record(key, title, status, **extra):
    base = {'key': key, 'baslik': title, 'durum': status, 'bakilan': '', 'gerekce_kodu': '', 'kanit_alinti': '', 'tam_metin': ''}
    base.update(extra)
    return base


def sample(**approval):
    return {'sema': 1, 'onay': {'onaylandi': False, 'onaylayan': '', 'tarih': '', **approval}, 'kayitlar': [
        record('A1', 'Video RAG for Lectures', 'Hariç', bakilan='Başlık', gerekce_kodu='H5', gerekce='Bağlam uyuşmuyor',
               kanit_alinti='Video RAG'),
        record('A2', 'Chunking for Turkish QA', 'Geçti', bakilan='Özet', kanit_alinti='chunk sizes', tam_metin='Seçildi'),
        record('A3', 'Hybrid Retrieval', 'Geçti', bakilan='Özet', kanit_alinti='BM25', tam_metin='Yedek'),
        record('A4', 'A Vision Paper', 'Hariç', bakilan='Özet', gerekce_kodu='H2', kanit_alinti='not yet been empirically validated'),
        record('A5', 'Unread', 'Özet okunmadı'),
    ]}


CANDIDATES = {'A1': 'Video RAG for Lectures', 'A2': 'Chunking for Turkish QA', 'A3': 'Hybrid Retrieval',
              'A4': 'A Vision Paper', 'A5': 'Unread'}


class ScreeningTest(unittest.TestCase):
    def test_valid_file_has_no_problems_and_counts_add_up(self):
        data = sample()
        self.assertEqual(screening.check(data, CANDIDATES), [])
        c = screening.counts(data)
        self.assertEqual((c['aday'], c['haric'], c['gecen'], c['ozet_okunmadi']), (5, 2, 2, 1))
        self.assertEqual(c['haric'] + c['gecen'] + c['ozet_okunmadi'], c['aday'])
        self.assertEqual(c['haric_kod'], {'H2': 1, 'H5': 1})
        self.assertEqual((c['tam_metin_secilen'], c['yedek'], c['ozet_incelenen']), (1, 1, 3))

    def test_problems_are_reported(self):
        data = sample()
        data['kayitlar'][0]['kanit_alinti'] = 'Audio RAG'
        data['kayitlar'][1]['tam_metin'] = ''
        data['kayitlar'][3]['gerekce_kodu'] = 'H3'
        data['kayitlar'][4]['gerekce_kodu'] = 'H5'
        data['kayitlar'].append(record('A1', 'Video RAG for Lectures', 'Geçti', tam_metin='Yedek'))
        problems = screening.check(data, dict(CANDIDATES, B9='Missing'))
        text = '\n'.join(problems)
        for part in ('A1: birden çok karar', 'A1: kanıt alıntısı başlıkta geçmiyor', 'A2: tam metin durumu',
                     "A4: başlık-özet aşamasında geçersiz gerekçe kodu 'H3'", 'A5: özeti okunmayan kayıtta karar izi var',
                     'B9: karar dosyasında yok'):
            self.assertIn(part, text)

    def test_plan_writes_no_notes_before_approval(self):
        actions = screening.plan(sample())
        self.assertEqual([a['key'] for a in actions], ['A1', 'A2', 'A3', 'A4'])
        self.assertTrue(all(a['note'] is None for a in actions))
        self.assertEqual((actions[0]['collection'], actions[0]['role']), ('05_Haric_BaslikOzet', 'excluded_title'))
        self.assertEqual(actions[1]['tags'], ['TamMetin-Secildi'])

    def test_plan_after_approval_uses_the_approver(self):
        data = sample(onaylandi=True, onaylayan='Hasan Basri Taşkın', tarih='18.10.2026')
        data['onay']['ozet'] = screening.digest(data)
        notes = [a['note'] for a in screening.plan(data) if a['note']]
        self.assertEqual(len(notes), 2)
        self.assertIn('Aşama: Başlık-özet', notes[0])
        self.assertIn('Karar veren: Hasan Basri Taşkın', notes[0])
        self.assertIn('Karar tarihi: 18.10.2026', notes[0])
        self.assertIn('Kanıt (başlık): "Video RAG"', notes[0])
        self.assertIn('Kanıt (özet): "not yet been empirically validated"', notes[1])

    def test_approval_without_digest_or_after_a_change_does_not_count(self):
        data = sample(onaylandi=True, onaylayan='Hasan Basri Taşkın', tarih='18.10.2026')
        self.assertFalse(screening.approved(data))
        data['onay']['ozet'] = screening.digest(data)
        self.assertTrue(screening.approved(data))
        data['kayitlar'][2]['tam_metin'] = 'Seçildi'
        self.assertFalse(screening.approved(data))
        self.assertIn('değişmiş', screening.approval_state(data))
        self.assertTrue(all(a['note'] is None for a in screening.plan(data)))

    def test_notes_are_read_back_by_the_note_reader_without_unknown_fields(self):
        from literature.zotero import parse_note, UNKNOWN_KEY
        data = sample(onaylandi=True, onaylayan='Hasan Basri Taşkın', tarih='18.10.2026')
        data['onay']['ozet'] = screening.digest(data)
        record = data['kayitlar'][3]
        record['kanit_alinti'] = 'has not: <yet> been validated & tested'
        fields = parse_note(screening.note_html(screening.note_lines(record, data['onay'])))
        self.assertNotIn(UNKNOWN_KEY, fields)
        self.assertEqual((fields['Karar'], fields['Aşama'], fields['Gerekçe kodu']), ('Hariç', 'Başlık-özet', 'H2'))
        self.assertEqual(fields['Karar veren'], 'Hasan Basri Taşkın')
        self.assertEqual(fields['Karar tarihi'], '18.10.2026')
        self.assertIn('has not: <yet> been validated & tested', fields['Dahil/hariç gerekçesi'])

    def test_approve_writes_only_the_approval_and_keeps_the_old_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            path, backups = Path(tmp) / 'eleme_kararlari.json', Path(tmp) / 'Yedekler'
            path.write_text(json.dumps(sample(), ensure_ascii=False), encoding='utf-8')
            with self.assertRaises(ValidationError):
                screening.approve(path, '  ', CANDIDATES, backups)
            with self.assertRaises(ValidationError):
                screening.approve(path, 'Hasan Basri Taşkın', dict(CANDIDATES, B9='Missing'), backups)
            self.assertFalse(screening.approved(screening.load(path)))
            screening.approve(path, 'Hasan Basri Taşkın', CANDIDATES, backups, today='18.10.2026')
            data = screening.load(path)
            self.assertTrue(screening.approved(data))
            self.assertEqual(data['kayitlar'], sample()['kayitlar'])
            self.assertEqual(len(list(backups.glob('eleme_kararlari_onay_oncesi_*.json'))), 1)

    def test_plan_marks_selected_records_whose_access_must_be_checked(self):
        data = sample()
        data['kayitlar'][1]['erisim_on_kontrol'] = 'Kontrol edilecek (DOI yok)'
        data['kayitlar'][2]['erisim_on_kontrol'] = 'Kontrol edilecek'
        actions = {a['key']: a for a in screening.plan(data)}
        self.assertTrue(actions['A2']['access_check'])
        self.assertFalse(actions['A3']['access_check'])  # Yedek
        s = screening.summary(list(actions.values()))
        self.assertEqual(s['koleksiyon'], {'02_BaslikOzet_Gecen': 2, '05_Haric_BaslikOzet': 2})
        self.assertEqual((s['erisim_kontrol'], s['not']), (1, 0))

    def test_load_rejects_unknown_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'k.json'
            path.write_text(json.dumps({'sema': 2}), encoding='utf-8')
            with self.assertRaises(ValidationError):
                screening.load(path)
            path.write_text(json.dumps(sample()), encoding='utf-8')
            self.assertEqual(len(screening.load(path)['kayitlar']), 5)
