import json
import unittest

import test_storage as fixtures
from literature.refinement import propose, approve, get_proposal, canonical, split_years
from literature.storage import ValidationError


class RefinementTest(unittest.TestCase):
    setUp = fixtures.StorageTest.setUp
    tearDown = fixtures.StorageTest.tearDown
    def capture_count(self, count, query=None, job='job-1', tab=2):
        context = dict(profile='p', windowId=1, tabId=tab, documentId=job, epoch=0)
        self.store.begin_job(job, context)
        self.store.save_capture(job, self.png.read_bytes())
        data = fixtures.fields(count_value=count, count_raw=f'{count} results')
        if query: data['query_raw'] = query
        run = self.store.complete_job(job, data, context)
        return run, context

    def test_initial_thresholds(self):
        for count, wanted in [(0, False), (300, False), (301, True), (1000, True), (1001, True)]:
            run, ctx = self.capture_count(count, job=f'count-{count}')
            p = propose(self.store, run, ctx)
            self.assertEqual(bool(p), wanted)
            if p:
                self.assertEqual(p['year_from'], 2022)
                self.assertEqual(p['year_to'], 2026)
                self.assertEqual(p['query'], run['query_raw'] + ' AND PUBYEAR > 2021 AND PUBYEAR < 2027')

    def test_three_years_requires_large_initial_and_large_five_year_result(self):
        for first, second, wanted in [(1000, 800, False), (1001, 500, False), (1001, 501, True)]:
            run, ctx = self.capture_count(first, job=f'initial-{first}-{second}')
            p = propose(self.store, run, ctx)
            approve(self.store, p['id'], 'p')
            child, child_ctx = self.capture_count(second, p['query'], job=f'child-{first}-{second}')
            next_step = propose(self.store, child, child_ctx)
            self.assertEqual(bool(next_step), wanted)
            self.assertEqual(get_proposal(self.store, p['id'])['child_run_id'], child['id'])
            if next_step:
                self.assertEqual(next_step['year_from'], 2024)
                self.assertEqual(next_step['query'].count('PUBYEAR >'), 1)
                self.assertIn('PUBYEAR > 2023', next_step['query'])

    def test_no_approval_no_chain_and_other_tab_cannot_consume_approval(self):
        run, ctx = self.capture_count(12000)
        p = propose(self.store, run, ctx)
        child, child_ctx = self.capture_count(900, p['query'], 'no-approval')
        self.assertIsNone(propose(self.store, child, child_ctx))
        approve(self.store, p['id'], 'p')
        child, child_ctx = self.capture_count(900, p['query'], 'wrong-tab', tab=3)
        self.assertIsNone(propose(self.store, child, child_ctx))
        self.assertIsNone(get_proposal(self.store, p['id'])['child_run_id'])

    def test_approval_is_scoped_and_idempotency_preserves_history(self):
        run, ctx = self.capture_count(12000)
        p = propose(self.store, run, ctx)
        self.assertIsNone(propose(self.store, run, ctx))
        with self.assertRaises(ValidationError): approve(self.store, p['id'], 'another-profile')
        approve(self.store, p['id'], 'p')
        with self.assertRaises(ValidationError): approve(self.store, p['id'], 'p')
        self.store.close()
        from literature.storage import Store
        self.store = Store(self.root)
        self.assertEqual(get_proposal(self.store, p['id'])['state'], 'approved')

    def test_existing_unknown_year_and_approximate_results_are_not_guessed(self):
        run, ctx = self.capture_count(12000, 'TITLE("test") AND PUBYEAR = 2025')
        self.assertIsNone(propose(self.store, run, ctx))
        run, ctx = self.capture_count(12000, job='approximate')
        run['count_qualifier'] = 'approximate'
        self.assertIsNone(propose(self.store, run, ctx))
        self.assertNotEqual(canonical('TITLE("a b")'), canonical('TITLE("ab")'))

    def test_scopus_repeated_year_clauses_keep_the_same_chain(self):
        run, ctx = self.capture_count(12000)
        first = propose(self.store, run, ctx)
        approve(self.store, first['id'], 'p')
        child, ctx = self.capture_count(800, first['query'], 'five-year')
        second = propose(self.store, child, ctx)
        approve(self.store, second['id'], 'p')
        actual = first['query'] + ' AND PUBYEAR > 2023 AND PUBYEAR < 2027'
        final, ctx = self.capture_count(600, actual, 'three-year')
        self.assertIsNone(propose(self.store, final, ctx))
        self.assertEqual(get_proposal(self.store, second['id'])['child_run_id'], final['id'])

    def test_year_parser_fails_closed_on_ambiguous_or_incomplete_conditions(self):
        for q in ['TITLE("x") AND PUBYEAR > 2021', 'TITLE("x") OR PUBYEAR > 2021 AND PUBYEAR < 2027',
                  'TITLE("x") AND PUBYEAR > 2027 AND PUBYEAR < 2021']:
            self.assertEqual(split_years(q), (None, None))
        self.assertEqual(split_years('TITLE("PUBYEAR > 2021") AND PUBYEAR < 2027 AND PUBYEAR > 2023'),
                         ('TITLE("PUBYEAR > 2021")', (2024, 2026)))
