import json
import tempfile
import unittest
import zipfile
from pathlib import Path

import bibtexparser
from literature.storage import Store, ValidationError
from literature.zotero import parse_note, import_items
from literature.exports import export_sources, _bib_title, _bib_given, _bib_text
from literature.backup import create_backup, restore_backup


class OutputsTest(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)/'project';self.store=Store(self.root)
    def tearDown(self):self.store.close();self.tmp.cleanup()
    def items(self):
        return [{'key':'ABCD1234','data':{'itemType':'journalArticle','title':'Türkçe RAG','creators':[{'creatorType':'author','firstName':'Ali','lastName':'Çelik'}],'date':'2026','DOI':'10.1234/test','collections':['IN']}},
                {'key':'NOTE1234','data':{'itemType':'note','parentItem':'ABCD1234','note':'<p>Amaç/problem: Türkçe soru-cevap.</p><p>Anotasyon: Birinci cümle. İkinci cümle. Üçüncü cümle.</p><p>Okuma düzeyi: 2. geçiş</p>'}}]
    def test_note_fields_and_library_identity(self):
        note=parse_note('<p>Amaç/problem: Deneme</p><p>Temel bulgu: Raporlanmadı</p>')
        self.assertEqual(note['Amaç/problem'],'Deneme')
        self.assertEqual(note['Temel bulgu'],'Raporlanmadı')
        import_items(self.store,'users/1',self.items(),{'included':'IN'})
        import_items(self.store,'users/1',self.items(),{'included':'IN'})
        self.assertEqual(self.store.db.execute('SELECT COUNT(*) FROM papers').fetchone()[0],1)
        import_items(self.store,'groups/1',self.items(),{'included':'IN'})
        self.assertEqual(self.store.db.execute('SELECT COUNT(*) FROM papers').fetchone()[0],2)
    def test_unreviewed_annotation_blocks_final_export(self):
        import_items(self.store,'users/1',self.items(),{'included':'IN'})
        with self.assertRaises(ValidationError):export_sources(self.store)

    def test_removed_zotero_item_stops_being_included(self):
        import_items(self.store,'users/1',self.items(),{'included':'IN'})
        with self.store.db:self.store.db.execute('UPDATE papers SET verified=1')
        import_items(self.store,'users/1',[],{'included':'IN'})
        row=self.store.db.execute('SELECT state,verified FROM papers').fetchone()
        self.assertEqual(row['state'],'unavailable')
        self.assertEqual(row['verified'],0)
    def test_pdf_bib_manifest_same_source_set(self):
        import_items(self.store,'users/1',self.items(),{'included':'IN'})
        with self.store.db:self.store.db.execute('UPDATE papers SET verified=1')
        result=export_sources(self.store)
        bib=bibtexparser.loads(Path(result['bib']).read_text(encoding='utf-8'))
        manifest=json.loads(Path(result['manifest']).read_text(encoding='utf-8'))
        self.assertEqual([e['ID'] for e in bib.entries],manifest['citekeys'])
        self.assertEqual(len(bib.entries),1)
        self.assertGreater(Path(result['pdf']).stat().st_size,1000)
    def test_bib_values_survive_latex_and_case_changing_styles(self):
        self.assertEqual(_bib_title('Development of a Turkish Embedding Model for RAG Applications'),
                         'Development of a {Turkish} Embedding Model for {RAG} Applications')
        self.assertEqual(_bib_title('FaithEval: Tool-Calling LLMs with BM25 and RAG-Based Retrieval-Augmented QA'),
                         '{FaithEval}: Tool-Calling {LLMs} with {BM25} and {RAG}-Based Retrieval-Augmented {QA}')
        self.assertEqual(_bib_title('A Study of Best Practices'), 'A Study of Best Practices')
        self.assertEqual(_bib_text('IEEE Power & Energy 100% #1 a_b $5'), 'IEEE Power \\& Energy 100\\% \\#1 a\\_b \\$5')
        self.assertEqual(_bib_text('\\& {x}'), '\\textbackslash{}\\& \\{x\\}')
        self.assertEqual(_bib_given('Şule Gündüz'), '{\\c{S}}ule Gündüz')
        self.assertEqual(_bib_given('Ș.'), '{\\textcommabelow{S}}.')
        self.assertEqual(_bib_given('Á.'), "{\\'A}.")
        self.assertEqual(_bib_given('Ö. Ç.'), '{\\"O}. {\\c{C}}.')
        self.assertEqual(_bib_given('S.-V.'), 'S.-V.')
        self.assertEqual(_bib_given('Ali'), 'Ali')

    def test_backup_restore_and_reject_zip_traversal(self):
        archive=create_backup(self.store)
        destination=Path(self.tmp.name)/'restored'
        restore_backup(archive,destination)
        restored=Store(destination)
        self.assertEqual(restored.settings(),self.store.settings());restored.close()
        evil=Path(self.tmp.name)/'evil.zip'
        with zipfile.ZipFile(evil,'w') as z:z.writestr('../outside.txt','evil')
        with self.assertRaises(ValidationError):restore_backup(evil,Path(self.tmp.name)/'bad')
        self.assertFalse((Path(self.tmp.name)/'outside.txt').exists())


if __name__=='__main__':unittest.main()
