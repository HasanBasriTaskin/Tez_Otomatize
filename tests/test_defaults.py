"""0.3.3: installation defaults, operator rename and setting aside a wrong capture."""
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import test_storage as fixtures
from literature import runtime
from literature.exports import delivery_report
from literature.storage import Store, ValidationError, initial_settings

TEAM = {'operator': 'Hasan Basri Taşkın', 'library': 'groups/6718452'}
ROLES = {'candidate': 'BX38VWI6', 'title_abstract': 'VHIBG6RK'}


class InitialSettingsTest(unittest.TestCase):
    def test_defaults_fill_a_new_project(self):
        s = initial_settings({**TEAM, 'collection_mapping': ROLES, 'collection_library': 'groups/6718452',
                              'zotero_data_dir': r'C:\Users\taskin\Zotero'})
        self.assertEqual((s['operator'], s['library']), ('Hasan Basri Taşkın', 'groups/6718452'))
        self.assertEqual(s['collection_mapping'], ROLES)
        self.assertEqual(s['zotero_data_dir'], r'C:\Users\taskin\Zotero')

    def test_roles_of_another_library_and_invalid_values_are_ignored(self):
        with patch.dict(os.environ, {'USERNAME': 'taskin'}):
            s = initial_settings({'operator': '  ', 'library': 'groups/x', 'collection_mapping': ROLES,
                                  'collection_library': 'groups/1'})
        self.assertEqual((s['operator'], s['library'], s['collection_mapping']), ('taskin', 'users/0', {}))
        s = initial_settings({**TEAM, 'collection_mapping': ROLES, 'collection_library': 'groups/1'})
        self.assertEqual(s['collection_mapping'], {})
        self.assertEqual(initial_settings(None)['library'], 'users/0')


class InstallationDefaultsTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        patcher = patch.dict(os.environ, {'LOCALAPPDATA': self.tmp.name})
        patcher.start();self.addCleanup(patcher.stop)
        self.file = Path(self.tmp.name) / 'LiteraturKayit' / 'settings.json'

    def test_saving_merges_with_project_root_and_ignores_unknown_keys(self):
        self.file.parent.mkdir(parents=True)
        self.file.write_text(json.dumps({'project_root': r'D:\Tez', 'defaults': {'operator': 'Esra'}}), encoding='utf-8')
        runtime.save_user_defaults({'library': 'groups/6718452', 'hotkey': 'CTRL+K'})
        config = json.loads(self.file.read_text(encoding='utf-8'))
        self.assertEqual(config['project_root'], r'D:\Tez')
        self.assertEqual(config['defaults'], {'operator': 'Esra', 'library': 'groups/6718452'})
        self.assertEqual(runtime.user_defaults(), {'operator': 'Esra', 'library': 'groups/6718452'})

    def test_missing_or_broken_file_gives_no_defaults(self):
        self.assertEqual(runtime.user_defaults(), {})
        self.file.parent.mkdir(parents=True);self.file.write_text('{bozuk', encoding='utf-8')
        self.assertEqual(runtime.user_defaults(), {})
        runtime.save_user_defaults({'operator': 'Hasan'})
        self.assertEqual(runtime.user_defaults(), {'operator': 'Hasan'})


class InstallerAnswersTest(unittest.TestCase):
    def test_prefill_prefers_this_computer_then_team_default(self):
        product = {'extension_id': 'x', 'defaults': TEAM}
        self.assertEqual(runtime.suggested_defaults({}, product), TEAM)
        mine = {'defaults': {'operator': 'Esra Sultan Doğan'}}
        self.assertEqual(runtime.suggested_defaults(mine, product), {'operator': 'Esra Sultan Doğan', 'library': 'groups/6718452'})
        self.assertEqual(runtime.suggested_defaults({}, {}), {'operator': '', 'library': ''})

    def test_answers_are_validated_and_roles_kept_only_for_the_same_library(self):
        config = {'project_root': r'D:\Tez', 'defaults': {'library': 'groups/6718452', 'collection_mapping': ROLES,
                                                         'collection_library': 'groups/6718452'}}
        same = runtime.merge_installer_defaults(config, ' Hasan Basri Taşkın ', 'groups/6718452')
        self.assertEqual(same['defaults']['operator'], 'Hasan Basri Taşkın')
        self.assertEqual(same['defaults']['collection_mapping'], ROLES)
        self.assertEqual(same['project_root'], r'D:\Tez')
        other = runtime.merge_installer_defaults(config, 'Esra', 'users/0')
        self.assertNotIn('collection_mapping', other['defaults'])
        for operator, library in [('', 'users/0'), ('Esra', 'TEZ'), ('Esra', 'groups/')]:
            with self.assertRaises(ValueError):runtime.merge_installer_defaults(config, operator, library)


class ProjectTest(unittest.TestCase):
    setUp = fixtures.StorageTest.setUp
    tearDown = fixtures.StorageTest.tearDown
    capture = fixtures.StorageTest.capture

    def test_new_project_uses_defaults_existing_project_keeps_its_settings(self):
        root = Path(self.tmp.name) / 'yeni'
        store = Store(root, defaults=TEAM)
        try:self.assertEqual(store.settings()['operator'], 'Hasan Basri Taşkın')
        finally:store.close()
        store = Store(root, defaults={'operator': 'Başkası', 'library': 'groups/1'})
        try:self.assertEqual((store.settings()['operator'], store.settings()['library']), ('Hasan Basri Taşkın', 'groups/6718452'))
        finally:store.close()

    def test_first_real_name_is_carried_to_earlier_records(self):
        self.store.update_settings({'operator': 'taskin'})
        first = self.capture('a')
        self.assertEqual(first['operator'], 'taskin')
        self.store.update_settings({'operator': '  Hasan Basri Taşkın '})
        self.assertEqual(self.store.get_run(first['id'])['operator'], 'Hasan Basri Taşkın')
        events = [r[0] for r in self.store.db.execute("SELECT event FROM audit_events WHERE event='operator_renamed'")]
        self.assertEqual(events, ['operator_renamed'])
        with self.assertRaises(ValidationError):self.store.update_settings({'operator': ''})

    def test_other_names_are_not_touched(self):
        self.store.update_settings({'operator': 'Esra'})
        run = self.capture('a')
        with self.store.db:self.store.db.execute("UPDATE search_runs SET operator='Başka biri' WHERE id=?", (run['id'],))
        self.store.update_settings({'operator': 'Hasan'})
        self.assertEqual(self.store.get_run(run['id'])['operator'], 'Başka biri')


class DiscardTest(unittest.TestCase):
    setUp = fixtures.StorageTest.setUp
    tearDown = fixtures.StorageTest.tearDown

    def pending_capture(self, job='form'):
        context = dict(profile='p', windowId=1, tabId=2, documentId=job, epoch=0)
        self.store.begin_job(job, context)
        self.store.save_capture(job, self.png.read_bytes())
        # Ctrl+M on IEEE Xplore's advanced search form: no executed query, no count.
        result = self.store.complete_job(job, fixtures.fields(database='IEEE Xplore', query_raw='', count_value=None,
                                                              count_qualifier='unknown', status='incomplete'), context)
        self.assertEqual(result['state'], 'incomplete')
        return job

    def test_wrong_capture_leaves_lists_and_delivery_check_but_keeps_png(self):
        job = self.pending_capture()
        self.assertEqual(len(self.store.pending()), 1)
        self.assertIn('Eksik yakalama', ' '.join(i['message'] for i in delivery_report(self.store)['issues']))
        image = self.store.get_job(job)['image_path']
        self.assertEqual(self.store.discard_job(job, 'Gelişmiş arama formu')['state'], 'discarded')
        self.assertEqual(self.store.pending(), [])
        self.assertNotIn('Eksik yakalama', ' '.join(i['message'] for i in delivery_report(self.store)['issues']))
        self.assertTrue(self.store.path(image).exists())
        self.assertEqual(self.store.list_runs(), [])
        audit = self.store.db.execute("SELECT details_json FROM audit_events WHERE event='capture_discarded'").fetchone()[0]
        self.assertIn('Gelişmiş arama formu', audit)
        self.assertEqual(self.store.discard_job(job)['state'], 'discarded')  # idempotent

    def test_discarded_capture_cannot_become_a_record_or_come_back(self):
        job = self.pending_capture()
        self.store.discard_job(job)
        with self.assertRaises(ValidationError):
            self.store.complete_job(job, fixtures.fields(count_value=5, count_raw='5 results'), {}, manual=True, new_run=True)
        self.store.mark_incomplete(job, 'yeniden')
        self.store.close();self.store = Store(self.root)  # recover() runs on open
        self.assertEqual(self.store.get_job(job)['state'], 'discarded')
        self.assertEqual(self.store.pending(), [])

    def test_verified_record_and_unknown_id_cannot_be_discarded(self):
        run = fixtures.StorageTest.capture(self, 'ok')
        with self.assertRaises(ValidationError):self.store.discard_job('ok')
        with self.assertRaises(ValidationError):self.store.discard_job('yok')
        self.assertEqual(self.store.get_run(run['id'])['display_id'], 'S001')


if __name__ == '__main__':
    unittest.main()
