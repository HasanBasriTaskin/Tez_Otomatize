import json
import unittest

import test_storage as fixtures
from literature.refinement import propose, approve, get_proposal, canonical, split_years, project_window, repair_window_notes
from literature.storage import ValidationError

THRESHOLD = ('TITLE-ABS-KEY ( "retrieval augmented generation" OR "retrieval-augmented generation" ) '
             'AND ( DOCTYPE ( ar ) OR DOCTYPE ( cp ) OR DOCTYPE ( re ) )')
TOPIC = ('TITLE-ABS-KEY ( ( "retrieval augmented generation" OR "retrieval-augmented generation" ) '
         'AND ( Turkish OR multilingual ) ) AND ( DOCTYPE ( ar ) OR DOCTYPE ( cp ) )')


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

    def fresh_project(self):
        # A captured chain fixes the project window, so independent threshold cases need their own project.
        self.tearDown()
        self.setUp()

    def threshold_chain(self, first=12818, second=12494, third=12446):
        run, ctx = self.capture_count(first, THRESHOLD, job='threshold')
        p = propose(self.store, run, ctx)
        approve(self.store, p['id'], 'p')
        child, ctx = self.capture_count(second, p['query'], job='threshold-five')
        q = propose(self.store, child, ctx)
        if q is None:
            return [run, child]
        approve(self.store, q['id'], 'p')
        final, ctx = self.capture_count(third, q['query'], job='threshold-three')
        self.assertIsNone(propose(self.store, final, ctx))
        return [run, child, final]

    def test_three_years_requires_large_initial_and_large_five_year_result(self):
        for first, second, wanted in [(1000, 800, False), (1001, 500, False), (1001, 501, True)]:
            self.fresh_project()
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

    def test_topic_query_takes_project_window_in_one_step(self):
        chain = self.threshold_chain()
        self.assertEqual(project_window(self.store), (2024, 'S002 → S003'))
        # Q01 had 589 results (≤ 1000): the per-query rule would stop at 2022–2026; the project window wins.
        topic, ctx = self.capture_count(589, TOPIC, job='q01')
        p = propose(self.store, topic, ctx)
        self.assertEqual((p['year_from'], p['year_to']), (2024, 2026))
        self.assertEqual(p['query'], TOPIC + ' AND PUBYEAR > 2023 AND PUBYEAR < 2027')
        self.assertTrue(p['context']['project_window'])
        self.assertIn('2024–2026', p['reason'])
        self.assertIn('S002 → S003', p['reason'])
        approve(self.store, p['id'], 'p')
        child, ctx = self.capture_count(577, p['query'], job='q01-window')
        self.assertIsNone(propose(self.store, child, ctx))
        self.assertEqual(get_proposal(self.store, p['id'])['child_run_id'], child['id'])
        notes = self.store.db.execute('SELECT notes FROM search_runs WHERE id=?', (child['id'],)).fetchone()[0]
        self.assertIn(topic['display_id'] + ' sorgusunun yıl sınırı uygulanmış hâli', notes)
        self.assertNotIn('öneriliyor', notes)
        self.assertEqual([r['display_id'] for r in chain + [topic, child]], ['S001', 'S002', 'S003', 'S004', 'S005'])

    def topic_chain(self, n, count=600):
        topic, ctx = self.capture_count(count, TOPIC.replace('Turkish', f'Turkish{n}'), job=f'topic-{n}')
        p = propose(self.store, topic, ctx)
        approve(self.store, p['id'], 'p')
        child, ctx = self.capture_count(count - 10, p['query'], job=f'topic-{n}-window')
        self.assertIsNone(propose(self.store, child, ctx))
        return p, child

    def test_later_topics_still_name_the_threshold_chain(self):
        # 0.3.2 bug (16.10.2026): S007's note said "S004 → S005" instead of the deciding "S002 → S003".
        self.threshold_chain()
        for n in range(3):
            p, child = self.topic_chain(n)
            self.assertIn('(S002 → S003 daraltmasıyla belirlendi)', p['reason'])
        self.assertEqual(project_window(self.store), (2024, 'S002 → S003'))

    def test_repair_rewrites_only_the_wrong_chain_and_is_idempotent(self):
        self.threshold_chain()
        p, child = self.topic_chain(0)
        p2, child2 = self.topic_chain(1)
        wrong = 'S006 devamı: Proje yıl penceresi 2024–2026 (S004 → S005 daraltmasıyla belirlendi). Kılavuz…\nKendi notum'
        with self.store.db:
            self.store.db.execute('UPDATE search_runs SET notes=? WHERE id=?', (wrong, child2['id']))
            self.store.db.execute('UPDATE search_refinements SET reason=? WHERE id=?', (wrong.split('\n')[0][13:], p2['id']))
        self.assertEqual(repair_window_notes(self.store), 2)
        notes = self.store.db.execute('SELECT notes FROM search_runs WHERE id=?', (child2['id'],)).fetchone()[0]
        self.assertEqual(notes, wrong.replace('S004 → S005', 'S002 → S003'))
        self.assertIn('S002 → S003', get_proposal(self.store, p2['id'])['reason'])
        self.assertEqual(repair_window_notes(self.store), 0)

    def test_small_topic_still_uses_window_and_empty_topic_does_not(self):
        self.threshold_chain()
        small, ctx = self.capture_count(120, TOPIC, job='small')
        self.assertEqual(propose(self.store, small, ctx)['year_from'], 2024)
        empty, ctx = self.capture_count(0, TOPIC.replace('Turkish', 'Klingon'), job='empty')
        self.assertIsNone(propose(self.store, empty, ctx))

    def test_five_year_project_window_is_not_narrowed_again_for_large_topics(self):
        self.threshold_chain(first=800, second=700)  # 301–1000 → 2022–2026 only
        self.assertEqual(project_window(self.store)[0], 2022)
        topic, ctx = self.capture_count(5000, TOPIC, job='big')
        p = propose(self.store, topic, ctx)
        self.assertEqual(p['year_from'], 2022)
        approve(self.store, p['id'], 'p')
        child, ctx = self.capture_count(4000, p['query'], job='big-five')
        self.assertIsNone(propose(self.store, child, ctx))

    def test_offered_but_uncaptured_narrowing_does_not_fix_the_window(self):
        run, ctx = self.capture_count(12818, THRESHOLD, job='threshold')
        propose(self.store, run, ctx)
        self.assertEqual(project_window(self.store), (None, None))
        topic, ctx = self.capture_count(589, TOPIC, job='q01')
        self.assertEqual(propose(self.store, topic, ctx)['year_from'], 2022)

    def test_year_parser_fails_closed_on_ambiguous_or_incomplete_conditions(self):
        for q in ['TITLE("x") AND PUBYEAR > 2021', 'TITLE("x") OR PUBYEAR > 2021 AND PUBYEAR < 2027',
                  'TITLE("x") AND PUBYEAR > 2027 AND PUBYEAR < 2021']:
            self.assertEqual(split_years(q), (None, None))
        self.assertEqual(split_years('TITLE("PUBYEAR > 2021") AND PUBYEAR < 2027 AND PUBYEAR > 2023'),
                         ('TITLE("PUBYEAR > 2021")', (2024, 2026)))


IEEE_Q = ('( ("Abstract":"retrieval augmented generation" OR "Abstract":"retrieval-augmented generation") '
          'AND ("Abstract":Turkish OR "Abstract":multilingual))')


class IeeeRefinementTest(unittest.TestCase):
    setUp = fixtures.StorageTest.setUp
    tearDown = fixtures.StorageTest.tearDown

    def capture(self, count, filters, job, query=IEEE_Q, tab=3):
        context = dict(profile='p', windowId=1, tabId=tab, documentId=job, epoch=0)
        self.store.begin_job(job, context)
        self.store.save_capture(job, self.png.read_bytes())
        data = fixtures.fields(database='IEEE Xplore', query_raw=query, fields='Abstract', filters=filters,
                               count_value=count, count_raw=f'{count} results',
                               safe_url='https://ieeexplore.ieee.org/search/searchresult.jsp')
        return self.store.complete_job(job, data, context), context

    def scopus_window(self):
        chain = RefinementTest.threshold_chain(self)
        self.assertEqual(project_window(self.store)[0], 2024)
        return chain

    capture_count = RefinementTest.capture_count

    def test_types_and_window_in_one_proposal_then_child_links(self):
        self.scopus_window()
        run, ctx = self.capture(195, ['Yıl (sonuç aralığı): 2019–2026'], 'ieee-1')
        p = propose(self.store, run, ctx)
        self.assertEqual(p['context']['kind'], 'ieee')
        self.assertEqual(p['context']['types'], ['Conferences', 'Journals'])
        self.assertTrue(p['context']['apply_years'])
        self.assertEqual((p['year_from'], p['year_to']), (2024, 2026))
        self.assertEqual(p['query'], IEEE_Q)  # the query never changes on IEEE
        self.assertEqual(p['filters_label'], 'Tür: Conferences, Journals; Yıl: 2024–2026')
        self.assertIn('S002 → S003', p['reason'])
        approve(self.store, p['id'], 'p')
        child, ctx = self.capture(150, ['Tür: Conferences', 'Tür: Journals', 'Yıl: 2024–2026'], 'ieee-1b')
        self.assertIsNone(propose(self.store, child, ctx))
        self.assertEqual(get_proposal(self.store, p['id'])['child_run_id'], child['id'])
        notes = self.store.get_run(child['id'])['notes']
        self.assertIn(run['display_id'] + ' sorgusuna IEEE filtreleri uygulandı (Tür: Conferences, Journals; Yıl: 2024–2026)', notes)
        # The type-only IEEE step must not hide the Scopus window.
        self.assertEqual(project_window(self.store), (2024, 'S002 → S003'))

    def test_results_already_inside_the_window_only_need_types(self):
        self.scopus_window()
        run, ctx = self.capture(195, ['Yıl (sonuç aralığı): 2024–2026'], 'ieee-2')
        p = propose(self.store, run, ctx)
        self.assertFalse(p['context']['apply_years'])
        self.assertEqual((p['year_from'], p['year_to']), (0, 0))
        self.assertEqual(p['filters_label'], 'Tür: Conferences, Journals')
        approve(self.store, p['id'], 'p')
        child, ctx = self.capture(194, ['Tür: Conferences', 'Tür: Journals', 'Yıl (sonuç aralığı): 2024–2026'], 'ieee-2b')
        self.assertIsNone(propose(self.store, child, ctx))
        self.assertEqual(get_proposal(self.store, p['id'])['child_run_id'], child['id'])
        self.assertEqual(project_window(self.store), (2024, 'S002 → S003'))

    def test_correct_page_is_left_alone(self):
        self.scopus_window()
        run, ctx = self.capture(194, ['Tür: Journals', 'Tür: Conferences', 'Yıl: 2024–2026'], 'ieee-3')
        self.assertIsNone(propose(self.store, run, ctx))
        run, ctx = self.capture(194, ['Tür: Conferences', 'Tür: Journals', 'Yıl (sonuç aralığı): 2025–2026'], 'ieee-4')
        self.assertIsNone(propose(self.store, run, ctx))

    def test_unwanted_types_or_unknown_years_are_corrected(self):
        self.scopus_window()
        run, ctx = self.capture(300, ['Tür: Conferences', 'Tür: Journals', 'Tür: Early Access Articles'], 'ieee-5')
        p = propose(self.store, run, ctx)
        self.assertTrue(p['context']['apply_years'])  # years unreadable → apply the window, do not guess
        self.assertIn('Early Access hariç', p['reason'])

    def test_without_window_table_four_uses_the_ieee_count(self):
        run, ctx = self.capture(250, ['Yıl (sonuç aralığı): 2010–2026'], 'small')
        p = propose(self.store, run, ctx)
        self.assertFalse(p['context']['apply_years'])
        self.assertIn('≤ 300', p['reason'])
        self.fresh()
        run, ctx = self.capture(1500, ['Yıl (sonuç aralığı): 2010–2026'], 'large')
        p = propose(self.store, run, ctx)
        self.assertEqual((p['year_from'], p['context']['apply_years']), (2022, True))
        approve(self.store, p['id'], 'p')
        child, ctx = self.capture(800, ['Tür: Conferences', 'Tür: Journals', 'Yıl: 2022–2026'], 'large-5')
        q = propose(self.store, child, ctx)
        self.assertEqual((q['year_from'], q['year_to']), (2024, 2026))
        self.assertEqual(q['initial_count'], 1500)
        approve(self.store, q['id'], 'p')
        final, ctx = self.capture(400, ['Tür: Conferences', 'Tür: Journals', 'Yıl: 2024–2026'], 'large-3')
        self.assertIsNone(propose(self.store, final, ctx))
        self.assertEqual(project_window(self.store)[0], 2024)

    def test_settings_window_and_zero_results(self):
        self.store.update_settings({'window_start': 2023})
        run, ctx = self.capture(50, ['Yıl (sonuç aralığı): 2015–2026'], 'cfg')
        p = propose(self.store, run, ctx)
        self.assertEqual(p['year_from'], 2023)
        self.assertIn("Ayarlar'da", p['reason'])
        run, ctx = self.capture(0, [], 'zero')
        self.assertIsNone(propose(self.store, run, ctx))

    def test_other_tab_or_query_does_not_consume_the_approval(self):
        self.scopus_window()
        run, ctx = self.capture(195, ['Yıl (sonuç aralığı): 2019–2026'], 'ieee-6')
        p = propose(self.store, run, ctx)
        approve(self.store, p['id'], 'p')
        done = ['Tür: Conferences', 'Tür: Journals', 'Yıl: 2024–2026']
        other, ctx = self.capture(150, done, 'ieee-6-tab', tab=9)
        self.assertIsNone(propose(self.store, other, ctx))
        other, ctx = self.capture(150, done, 'ieee-6-q', query=IEEE_Q.replace('Turkish', 'Arabic'))
        self.assertIsNone(propose(self.store, other, ctx))
        self.assertEqual(get_proposal(self.store, p['id'])['state'], 'approved')

    def fresh(self):
        self.tearDown()
        self.setUp()
