import json
import tempfile
import unittest

from literature import screening, screening_job
from literature.storage import Store, ValidationError
from literature.zotero import import_items
from tests.test_screening_apply import ADAY, GECEN, HARIC, TITLES, decisions

MAPPING = {'candidate': ADAY, 'title_abstract': GECEN, 'excluded_title': HARIC}


def items(applied=False):
    data = decisions(approved=False)['kayitlar']
    out = []
    for row in data:
        collections = [ADAY]
        if applied:
            collections.append(HARIC if row['durum'] == 'Hariç' else GECEN)
        out.append({'key': row['key'], 'data': {'itemType': 'journalArticle', 'title': TITLES[row['key']],
                                                'collections': collections, 'tags': []}})
    return out


class ScreeningJobTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.store = Store(self.tmp.name)
        self.store.update_settings({'library': 'groups/6718452', 'collection_mapping': MAPPING,
                                    'operator': 'Hasan Basri Taşkın'})
        path = self.store.path(screening_job.RELATIVE)
        path.parent.mkdir(parents=True)
        path.write_text(json.dumps(decisions(approved=False), ensure_ascii=False), encoding='utf-8')

    def tearDown(self):
        self.store.close()
        self.tmp.cleanup()

    def test_missing_file_is_reported(self):
        self.store.path(screening_job.RELATIVE).unlink()
        self.assertEqual(screening_job.status(self.store)['exists'], False)

    def test_status_asks_for_a_zotero_read_before_checking(self):
        status = screening_job.status(self.store)
        self.assertEqual(status['problem_count'], 1)
        self.assertIn("Zotero'dan oku", status['problems'][0])
        with self.assertRaises(ValidationError):
            screening_job.approve(self.store, True)

    def test_approval_needs_the_confirmation_and_is_given_once(self):
        import_items(self.store, 'groups/6718452', items(), MAPPING, {})
        status = screening_job.status(self.store)
        self.assertEqual((status['problem_count'], status['approved'], status['plan']['erisim_kontrol']), (0, False, 1))
        with self.assertRaises(ValidationError):
            screening_job.approve(self.store, False)
        screening_job.approve(self.store, True)
        status = screening_job.status(self.store)
        self.assertTrue(status['approved'])
        self.assertIn('Hasan Basri Taşkın', status['approval'])
        self.assertEqual(status['plan']['not'], 2)
        self.assertEqual(len(list(self.store.path('Yedekler').glob('eleme_kararlari_onay_oncesi_*.json'))), 1)
        with self.assertRaises(ValidationError):
            screening_job.approve(self.store, True)

    def test_zotero_state_after_application_is_recognised(self):
        import_items(self.store, 'groups/6718452', items(applied=True), MAPPING, {})
        status = screening_job.status(self.store)
        self.assertTrue(status['in_zotero'])
        self.assertEqual(status['zotero']['durumlar'], {'excluded_title': 2, 'title_passed': 2})

    def test_apply_job_refuses_unapproved_decisions(self):
        job = screening_job.ApplyJob(lambda *args: None)
        with self.assertRaises(ValidationError):
            job.start(self.store, writer=None)
        self.assertFalse(job.running)


if __name__ == '__main__':
    unittest.main()
