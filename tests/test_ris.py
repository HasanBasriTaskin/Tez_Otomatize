import unittest

from literature.ris import parse_ris
from literature.storage import ValidationError


SAMPLE = '''TY  - JOUR
TI  - Türkçe retrieval study
AU  - Yılmaz, Ayşe
AU  - Research Group
PY  - 2025
JO  - Information Journal
VL  - 12
IS  - 3
SP  - 10
EP  - 18
DO  - 10.1234/Test
AB  - First line
      continued abstract.
KW  - retrieval
KW  - Turkish
UR  - https://www.scopus.com/inward/record.uri?eid=2-s2.0-85200000123&partnerID=40
UR  - https://example.org/article
ER  -
'''


class RISTest(unittest.TestCase):
    def test_preserves_bibliographic_fields_and_stable_scopus_identity(self):
        record, = parse_ris(SAMPLE.encode('utf-8-sig'))
        self.assertEqual(record['eid'], '2-s2.0-85200000123')
        self.assertEqual(record['doi'], '10.1234/test')
        self.assertEqual(record['year'], '2025')
        self.assertEqual(record['item']['title'], 'Türkçe retrieval study')
        self.assertEqual(record['item']['publicationTitle'], 'Information Journal')
        self.assertEqual(record['item']['pages'], '10-18')
        self.assertEqual(record['item']['DOI'], '10.1234/Test')
        self.assertEqual(record['item']['creators'], [
            {'creatorType': 'author', 'lastName': 'Yılmaz', 'firstName': 'Ayşe'},
            {'creatorType': 'author', 'name': 'Research Group'}])
        self.assertEqual(record['item']['abstractNote'], 'First line\ncontinued abstract.')
        self.assertEqual(record['item']['tags'], [{'tag': 'retrieval'}, {'tag': 'Turkish'}])
        self.assertIn('Scopus EID: 2-s2.0-85200000123', record['item']['extra'])
        self.assertIn('https://example.org/article', record['item']['extra'])
        self.assertEqual(record['raw_fields']['UR'][1], 'https://example.org/article')

    def test_keeps_duplicate_rows_for_separate_raw_and_unique_counts(self):
        self.assertEqual(len(parse_ris((SAMPLE + SAMPLE).encode())), 2)

    def test_rejects_html_truncation_missing_identity_and_broken_structure(self):
        for invalid in ['<html>Sign in</html>', SAMPLE.replace('ER  -\n', ''),
                        SAMPLE.replace('2-s2.0-85200000123', 'unknown'),
                        SAMPLE.replace('TI  -', 'TI -'), 'ER  -\n',
                        SAMPLE.replace('ER  -', 'TY  - JOUR'), '']:
            with self.subTest(invalid=invalid[:40]), self.assertRaises(ValidationError):
                parse_ris(invalid.encode())

    def test_accepts_an_identity_and_missing_optional_fields_without_inventing(self):
        item, = parse_ris(b'TY  - CONF\nTI  - Minimal\nAN  - 2-s2.0-123\nER  -\n')
        self.assertEqual(item['item']['itemType'], 'conferencePaper')
        self.assertEqual(item['doi'], '')
        self.assertEqual(item['year'], '')
        self.assertNotIn('date', item['item'])
        self.assertNotIn('DOI', item['item'])

    def test_rejects_conflicting_identities_within_one_record(self):
        with self.assertRaises(ValidationError):
            parse_ris(SAMPLE.replace('ER  -', 'AN  - 2-s2.0-999\nER  -').encode())


if __name__ == '__main__':
    unittest.main()
