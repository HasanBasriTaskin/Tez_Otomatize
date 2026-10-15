import copy
import json
import tempfile
import unittest
from pathlib import Path

from literature.storage import Store, ValidationError
from literature.workflow import WorkflowRecords
from literature.query_package import QueryPackage, validate_package


class QueryPackageTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.store = Store(self.tmp.name)
        self.packages = QueryPackage(self.store)

    def tearDown(self):
        self.store.close()
        self.tmp.cleanup()

    def small(self):
        return {'schema':1,'name':'Küçük deneme','initial':'TITLE-ABS-KEY("specific title")',
                'topics':[{'code':'Q01','label':'Deneme','query':'"specific title"'}]}

    def test_missing_file_creates_editable_default_and_uses_it_next_time(self):
        first=self.packages.load()
        self.assertEqual(len(first['package']['topics']),6)
        path=Path(first['path'])
        self.assertTrue(path.is_file())
        path.write_text(json.dumps(self.small()),encoding='utf-8')
        self.assertEqual(self.packages.load()['package'],self.small())

    def test_ui_save_survives_restart_and_backs_up_previous_file(self):
        original=self.packages.load()
        self.packages.save(self.small(),original['revision'])
        self.assertEqual(QueryPackage(self.store).load()['package'],self.small())
        backup=list(self.store.path('Yedekler').glob('sorgu-paketi_*.json'))
        self.assertEqual(len(backup),1)
        self.assertEqual(json.loads(backup[0].read_text(encoding='utf-8')),original['package'])

    def test_external_edit_cannot_be_silently_overwritten(self):
        opened=self.packages.load()
        Path(opened['path']).write_text(json.dumps(self.small()),encoding='utf-8')
        with self.assertRaisesRegex(ValidationError,'değiş'):
            self.packages.save(opened['package'],opened['revision'])
        self.assertEqual(self.packages.load()['package'],self.small())

    def test_malformed_or_oversized_file_never_falls_back_to_defaults(self):
        path=Path(self.packages.load()['path'])
        for data in ('{broken', ' '*131073):
            path.write_text(data,encoding='utf-8')
            with self.assertRaises(ValidationError): self.packages.load()
            self.assertEqual(path.read_text(encoding='utf-8'),data)

    def test_invalid_query_or_topic_identity_is_rejected_without_overwriting(self):
        current=self.packages.load()
        cases=[]
        for query in ('', '("x"', '"x', 'x) OR TITLE(y)', 'x AND PUBYEAR > 2023', 'x AND DOCTYPE(ar)', 'TITLE-ABS-KEY(x)'):
            value=self.small();value['topics'][0]['query']=query;cases.append(value)
        value=self.small();value['topics']*=2;cases.append(value)
        value=self.small();value['topics'][0]['code']='P00';cases.append(value)
        for value in cases:
            with self.subTest(value=value),self.assertRaises(ValidationError):
                self.packages.save(value,current['revision'])
        self.assertEqual(self.packages.load()['revision'],current['revision'])

    def test_quoted_filter_words_are_search_terms_and_unicode_is_preserved(self):
        p=self.small();p['topics'][0]['query']='("DOCTYPE" OR "Türkçe") AND ("PUBYEAR" OR "mevzuat")'
        self.assertEqual(validate_package(p),p)

    def test_new_session_uses_file_but_existing_session_keeps_its_snapshot(self):
        opened=self.packages.load();small=self.small()
        saved=self.packages.save(small,opened['revision'])
        records=WorkflowRecords(self.store)
        session=records.create({'package_revision':saved['revision']},{})
        changed=copy.deepcopy(small);changed['topics'][0]['query']='"new topic"'
        Path(saved['path']).write_text(json.dumps(changed),encoding='utf-8')
        records.advance(session['id'],2)
        old=records.get(session['id'])
        self.assertIn('specific title',old['steps'][1]['query'])
        self.assertEqual(old['snapshot']['package_name'],'Küçük deneme')
        records.stop(session['id'])
        new=records.create({},{});records.advance(new['id'],2)
        self.assertIn('new topic',records.get(new['id'])['steps'][1]['query'])

    def test_stale_preview_cannot_start_a_new_session(self):
        original=self.packages.load()
        self.packages.save(self.small(),original['revision'])
        with self.assertRaisesRegex(ValidationError,'değiş'):
            WorkflowRecords(self.store).create({'package_revision':original['revision']},{})
        self.assertIsNone(WorkflowRecords(self.store).get())

    def test_editor_cannot_save_during_an_unfinished_session(self):
        original=self.packages.load()
        records=WorkflowRecords(self.store);session=records.create({}, {})
        with self.assertRaisesRegex(ValidationError,'tarama'):
            self.packages.save(self.small(),original['revision'])
        records.stop(session['id'])
        self.packages.save(self.small(),original['revision'])
