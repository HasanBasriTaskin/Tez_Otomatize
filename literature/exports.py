import html
import io
import json
import re
from pathlib import Path

import bibtexparser
from bibtexparser.bibdatabase import BibDatabase
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4,landscape
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import SimpleDocTemplate,Paragraph,Spacer,Image,PageBreak,KeepTogether

from .storage import ValidationError,json_text,utcnow,digest


def styles():
    font=Path('C:/Windows/Fonts/arial.ttf')
    if not font.exists():raise ValidationError('Türkçe PDF için Arial yazı tipi bulunamadı.')
    if 'LKA' not in pdfmetrics.getRegisteredFontNames():pdfmetrics.registerFont(TTFont('LKA',str(font)))
    ss=getSampleStyleSheet()
    for style in ss.byName.values():style.fontName='LKA';style.leading=16
    ss['BodyText'].fontSize=10;ss['BodyText'].spaceAfter=10
    ss['Title'].fontSize=21;ss['Title'].leading=27
    return ss


def check_project(store):
    issues=[]
    for job in store.pending():issues.append(f"Eksik yakalama: {job['id']}")
    for run in store.list_runs():
        caps=store.captures(run['id'])
        if not caps:issues.append(f"{run['display_id']}: ekran görüntüsü yok.")
        for c in caps:
            file=store.path(c['relative_path'])
            if not file.exists():issues.append(f"{run['display_id']}: görsel bulunamadı.")
            elif digest(file.read_bytes())!=c['sha256']:issues.append(f"{run['display_id']}: görsel özeti değişmiş.")
    for p in store.db.execute('SELECT * FROM papers'):
        if p['state']=='conflict':issues.append(f"{p['item_key']}: Zotero koleksiyon/not çelişkisi.")
        if p['state']=='included':
            if not p['verified'] or not p['annotation'].strip():issues.append(f"{p['item_key']}: anotasyon kontrol edilmedi veya boş.")
            if not store.db.execute('SELECT 1 FROM search_paper_links WHERE paper_id=?',(p['id'],)).fetchone():issues.append(f"{p['item_key']}: arama bağlantısı yok.")
        if p['state']=='excluded':
            r=store.db.execute('SELECT reason FROM screening_decisions WHERE paper_id=?',(p['id'],)).fetchone()
            if not r or not r[0]:issues.append(f"{p['item_key']}: dışlama gerekçesi eksik.")
    return issues


def _text(value):return html.escape(str(value or '')).replace('\n','<br/>')


def _bib_value(value):
    return str(value).replace('\\','\\textbackslash{}').replace('{','\\{').replace('}','\\}').replace('\x00','')


def export_sources(store,draft=False):
    with store.lock:
        papers=[dict(r) for r in store.db.execute("SELECT * FROM papers WHERE state='included' ORDER BY library_id,item_key")]
        if not papers:raise ValidationError('Dahil edilmiş kaynak yok. Önce Zotero koleksiyonlarını eşleştirin.')
        bad=[p['item_key'] for p in papers if not p['verified'] or not p['annotation'].strip()]
        if bad and not draft:raise ValidationError('Kontrol edilmemiş anotasyonlar: '+', '.join(bad[:15])+'. Taslak çıktı seçilebilir.')
        settings=store.settings();prefix=settings['team_code']+'_O2'
        suffix='_TASLAK' if draft else ''
        ss=styles();story=[Paragraph('Anotasyonlu kaynak listesi'+(' — TASLAK' if draft else ''),ss['Title']),
                          Paragraph(_text(settings['project_name']),ss['BodyText']),Spacer(1,16)]
        bibliography=BibDatabase();keys=[];ids=[]
        for index,paper in enumerate(papers,1):
            data=json.loads(paper['data_json'])
            key='Z_'+re.sub('[^A-Za-z0-9_]','_',paper['library_id'])+'_'+paper['item_key']
            keys.append(key);ids.append(paper['id'])
            creators=data.get('creators',[])
            authors=['{'+_bib_value(c['name'])+'}' if c.get('name') else _bib_value(c.get('lastName',''))+', '+_bib_value(c.get('firstName','')) for c in creators if c.get('creatorType')=='author']
            entry={'ENTRYTYPE':{'journalArticle':'article','conferencePaper':'inproceedings'}.get(data.get('itemType'),'misc'),
                   'ID':key,'title':_bib_value(data.get('title',''))}
            if authors:entry['author']=' and '.join(authors)
            year=re.search(r'\b(19|20)\d{2}\b',data.get('date',''))
            if year:entry['year']=year[0]
            for source,target in [('DOI','doi'),('url','url'),('volume','volume'),('issue','number'),('pages','pages')]:
                if data.get(source):entry[target]=_bib_value(data[source])
            venue=data.get('publicationTitle') or data.get('proceedingsTitle')
            if venue:entry['booktitle' if entry['ENTRYTYPE']=='inproceedings' else 'journal']=_bib_value(venue)
            bibliography.entries.append(entry)
            citation=data.get('citation')
            if not citation:
                citation=', '.join((c.get('name') or (c.get('firstName','')+' '+c.get('lastName','')).strip()) for c in creators)
                citation+=f'. {data.get("title","")}. {venue or ""}, {data.get("date","")}.'
                if data.get('DOI'):citation+=' DOI: '+data['DOI']
            story.append(Paragraph(f'[{index}] {_text(citation)}',ss['BodyText']))
            story.append(Paragraph(_text(paper['annotation'] or 'Anotasyon eksik.'),ss['BodyText']))
            story.append(Spacer(1,12))
        writer=bibtexparser.bwriter.BibTexWriter();writer.order_entries_by=None
        bib=bibtexparser.dumps(bibliography,writer=writer)
        parsed=bibtexparser.loads(bib)
        if [x['ID'] for x in parsed.entries]!=keys or len(set(keys))!=len(keys):raise ValidationError('BibTeX kaynak kümesi doğrulanamadı.')
        buffer=io.BytesIO()
        SimpleDocTemplate(buffer,pagesize=A4,leftMargin=48,rightMargin=48,topMargin=48,bottomMargin=48,
                          title=prefix+' Kaynak Listesi',author=settings['operator']).build(story)
        files={
          'pdf':(f'05_Teslim/{prefix}_KaynakListesi{suffix}.pdf',buffer.getvalue()),
          'bib':(f'05_Teslim/{prefix}_kaynaklar{suffix}.bib',bib.encode('utf-8')),
          'manifest':(f'05_Teslim/{prefix}_kaynak_manifest{suffix}.json',json_text({'created_at':utcnow(),'draft':draft,'paper_ids':ids,'citekeys':keys,'issues':check_project(store)}).encode('utf-8'))}
        result={}
        for kind,(relative,content) in files.items():
            if store.path(relative).exists():relative=store._version_path(relative)
            store._atomic_write(relative,content);result[kind]=str(store.path(relative))
        return result


def export_evidence(store):
    with store.lock:
        rows=[]
        for run in sorted(store.list_runs(),key=lambda r:int(r['display_id'][1:])):
            for capture in store.captures(run['id']):rows.append((run,capture))
        if not rows:raise ValidationError('Dışa aktarılacak doğrulanmış ekran kaydı yok.')
        ss=styles();story=[];page_width,page_height=landscape(A4)
        for index,(run,cap) in enumerate(rows):
            file=store.path(cap['relative_path'])
            if not file.exists() or digest(file.read_bytes())!=cap['sha256']:raise ValidationError('Eksik veya değişmiş PNG: '+run['display_id'])
            if index:story.append(PageBreak())
            story.append(Paragraph(_text(run['display_id']+' — '+run['database_name']),ss['Heading2']))
            when=cap['captured_at'] or 'Çekim zamanı bilinmiyor (içe aktarılan PNG)'
            story.append(Paragraph(_text('Uygulamanın kayıt bilgisi: '+when),ss['BodyText']))
            image=Image(str(file));image._restrictSize(page_width-64,page_height-135);story.append(image)
        out=io.BytesIO();SimpleDocTemplate(out,pagesize=landscape(A4),leftMargin=32,rightMargin=32,topMargin=24,bottomMargin=24).build(story)
        relative=f"05_Teslim/{store.settings()['team_code']}_O2_AramaEkranlari.pdf"
        if store.path(relative).exists():relative=store._version_path(relative)
        store._atomic_write(relative,out.getvalue())
        return {'pdf':str(store.path(relative))}
