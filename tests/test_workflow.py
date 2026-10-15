import json
import tempfile
import unittest
import io
from PIL import Image
from pathlib import Path

from literature.storage import Store, ValidationError


class WorkflowTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.store = Store(self.tmp.name)

    def tearDown(self):
        self.store.close()
        self.tmp.cleanup()

    def workflow(self):
        from literature.workflow import WorkflowRecords
        return WorkflowRecords(self.store)

    def test_new_session_snapshots_package_without_reusing_old_runs(self):
        records = self.workflow()
        session = records.create({'include_review': False}, {'profile':'p','windowId':7,'tabId':9})
        self.assertEqual(session['state'], 'paused')
        self.assertEqual([s['code'] for s in session['steps']], ['P00'])
        self.assertNotIn('PUBYEAR', session['steps'][0]['query'])
        self.assertNotIn('DOCTYPE', session['steps'][0]['query'])
        self.assertEqual(session['snapshot']['types'], ['ar', 'cp'])
        self.assertEqual(len(session['snapshot']['topics']), 6)

    def test_thresholds_and_shared_year_for_all_topics(self):
        for first, second, expected in [(0,None,None),(300,None,None),(301,None,2022),(1000,None,2022),(1001,500,2022),(1001,501,2024)]:
            with self.subTest(first=first,second=second):
                records=self.workflow()
                session=records.create({}, {'profile':'p','windowId':7,'tabId':9})
                records.advance(session['id'], first)
                if first>300:
                    records.advance(session['id'], second if second is not None else 900)
                if expected==2024:records.advance(session['id'], 700)
                current=records.get(session['id'])
                topics=[s for s in current['steps'] if s['code'].startswith('Q')]
                self.assertEqual(len(topics),6)
                for step in topics:
                    self.assertEqual('PUBYEAR' in step['query'],expected is not None)
                    if expected:
                        self.assertIn(f'PUBYEAR > {expected-1}',step['query'])
                        self.assertLess(step['query'].index('DOCTYPE'),step['query'].index('PUBYEAR'),'Scopus year facet adapter expects the final query clause')
                    self.assertIn('DOCTYPE(ar) OR DOCTYPE(cp)',step['query'])
                records.stop(session['id'])

    def test_advance_idempotent_and_incomplete_session_cannot_be_replaced(self):
        records=self.workflow();s=records.create({}, {'profile':'p','windowId':7,'tabId':9})
        with self.assertRaises(ValidationError):records.create({}, {})
        records.advance(s['id'],100)
        records.advance(s['id'],100,code='P00')
        self.assertEqual(len(records.get(s['id'])['steps']),7)

    def test_restart_pauses_and_preserves_step_state(self):
        records=self.workflow();s=records.create({}, {'profile':'p','windowId':7,'tabId':9})
        records.set_session(s['id'],state='running')
        records.update_step(s['steps'][0]['id'],state='waiting')
        self.store.close();self.store=Store(self.tmp.name)
        restored=self.workflow().get(s['id'])
        self.assertEqual(restored['state'],'paused')
        self.assertEqual(restored['steps'][0]['state'],'waiting')

    def test_schema_upgrade_keeps_old_rows_and_creates_backup(self):
        self.assertEqual(self.store.db.execute('PRAGMA user_version').fetchone()[0],2)
        self.store.db.execute('PRAGMA user_version=1');self.store.db.commit();self.store.close()
        self.store=Store(self.tmp.name)
        self.assertEqual(self.store.db.execute('PRAGMA user_version').fetchone()[0],2)
        self.assertTrue(list(Path(self.tmp.name,'Yedekler').glob('schema1_*.sqlite3')))

    def test_clock_guard_uses_elapsed_time_and_detects_clock_jump(self):
        from literature.workflow import ClockGuard
        clock=ClockGuard(wall=100,monotonic=20)
        self.assertEqual(clock.elapsed(wall=103,monotonic=23),3)
        with self.assertRaises(ValidationError):clock.elapsed(wall=130,monotonic=24)

    def test_stability_requires_exact_same_query_count_and_filters(self):
        from literature.workflow import StableResult
        stable=StableResult('TITLE("x")')
        data=dict(database='Scopus',query_raw='TITLE("x")',query_verified=True,status='complete',count_qualifier='exact',count_value=0,filters=[])
        self.assertFalse(stable.observe(data,0))
        self.assertFalse(stable.observe(data,1))
        self.assertTrue(stable.observe(data,2))
        self.assertFalse(stable.observe(dict(data,count_value=1),3))
        self.assertFalse(stable.observe(dict(data,count_qualifier='approximate'),10))

    def test_export_rejects_foreign_path_and_wrong_record_count(self):
        from literature.workflow import validate_download
        root=Path(self.tmp.name);file=root/'sample.ris';file.write_bytes(b'TY  - JOUR\nTI  - test\nER  -\n')
        with self.assertRaises(ValidationError):validate_download(file,root/'other',1,lambda b:[{}])
        with self.assertRaises(ValidationError):validate_download(file,root,2,lambda b:[{}])

    def test_complete_zero_result_topics_capture_all_steps_without_export(self):
        from literature.workflow import WorkflowEngine
        from test_storage import fields
        store=self.store
        class Desktop:
            epoch=0
            def foreground(self):return 100
            def chrome_window(self, hwnd):return hwnd==100
        class Peer:
            profile='p';connected=True;query='old';stage='results'
            def request(self,kind,p,timeout=10):
                if kind=='workflow_guard':return {'ready':True}
                if kind=='workflow_release':return {}
                action=p['action']
                if action=='open_search':self.stage='search'
                if action=='fill_search':self.query=p['query']
                if action=='submit_search':self.stage='results'
                if action=='inspect':return {'stage':self.stage,'data':fields(query_raw=self.query,count_value=0,count_raw='0 results')}
                if action=='prepare_evidence':return {'ready':True,'evidence':{'requiresExtraViewport':False}}
                return {'stage':self.stage}
        peer=Peer()
        class Capture:
            paused=False;automation_active=False;next_action={};desktop=Desktop()
            bindings={100:(7,peer)};binding_lock=__import__('threading').Lock()
            busy=__import__('threading').Lock()
            def capture(self,automatic):
                ctx=dict(automatic['context'],documentId='doc',epoch=0)
                store.begin_job(automatic['job_id'],ctx)
                png=io.BytesIO();Image.new('RGB',(10,10)).save(png,'PNG')
                store.save_capture(automatic['job_id'],png.getvalue())
                return store.complete_job(automatic['job_id'],fields(query_raw=automatic['query'],count_value=0,count_raw='0 results'),ctx,new_run=True)
        class Writer:
            def preflight(self,authorize=False):return {'ready':True,'authorized':True}
            def import_records(self,*args,**kwargs):raise AssertionError('zero results must not import')
        engine=WorkflowEngine(store,Capture(),writer=Writer(),downloads_root=self.tmp.name)
        engine.stable_seconds=0
        session=engine.records.create({},dict(profile='p',windowId=7,tabId=9))
        engine.records.set_session(session['id'],state='running')
        engine.run(session['id'],peer)
        done=engine.records.get(session['id'])
        self.assertEqual(done['state'],'completed',done['error'])
        self.assertEqual(len(store.list_runs()),7)
        self.assertTrue(all(s['state']=='done' for s in done['steps']))


if __name__=='__main__':unittest.main()
