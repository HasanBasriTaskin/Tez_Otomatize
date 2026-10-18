import html
import io
import json
import re
from pathlib import Path

import bibtexparser
from bibtexparser.bibdatabase import BibDatabase
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4,landscape
from reportlab.lib.styles import getSampleStyleSheet,ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import SimpleDocTemplate,Paragraph,Spacer,Image,PageBreak,KeepTogether
from reportlab.pdfgen import canvas as pdf_canvas

from datetime import datetime
from zoneinfo import ZoneInfo

from .storage import ValidationError,json_text,utcnow,digest,citation_text,local_time,plain_text


FONT=Path('C:/Windows/Fonts/arial.ttf')


def register_font():
    if not FONT.exists():raise ValidationError('Türkçe PDF için Arial yazı tipi bulunamadı.')
    if 'LKA' not in pdfmetrics.getRegisteredFontNames():pdfmetrics.registerFont(TTFont('LKA',str(FONT)))
    return 'LKA'


def styles():
    register_font()
    ss=getSampleStyleSheet()
    for style in ss.byName.values():style.fontName='LKA';style.leading=16
    ss['BodyText'].fontSize=10;ss['BodyText'].spaceAfter=10
    ss['Title'].fontSize=21;ss['Title'].leading=27
    return ss


# Kılavuz K1, K2, K5, K6, K8 limits.
MIN_INCLUDED, MIN_CORE, MAX_PREPRINT, MAX_REVIEW, MAX_OUTSIDE_WINDOW = 80, 20, 8, 10, 8
REQUIRED_FIELDS = ['Yayın türü', 'Kalite sınıfı ve yılı', 'Okuyan kişi', 'Okuma düzeyi', 'Amaç/problem', 'Yöntem',
                   'Karşılaştırılan yöntemler', 'Veri seti ve dil', 'Deney düzeni', 'Değerlendirme metrikleri',
                   'Temel bulgu', 'Kaynak ihtiyacı', 'Açık kod/veri', 'Yazarların sınırlılıkları',
                   'Benim değerlendirmem', 'Tema', 'Tezle ilişki']
PAGE_EVIDENCE = re.compile(r'(?i)(\bs\.\s*\d|sayfa|tablo|table|şekil|fig|\bp\.\s*\d|pdf)')
GOOD_QUALITY = re.compile(r'\bQ[12]\b|\bA\*|\bCORE\s+A\b')
EXCLUSION_CODE = re.compile(r'\bH[1-6]\b')


def _note_date(text):
    try:
        return datetime.strptime(str(text).strip(), '%d.%m.%Y').date()
    except ValueError:
        return None


def _window_start(store):
    configured = store.settings().get('window_start')
    if isinstance(configured, int):
        return configured
    row = store.db.execute("SELECT year_from FROM search_refinements WHERE state IN ('captured','approved') AND year_from >= 1990 "
                           "ORDER BY created_at DESC LIMIT 1").fetchone()
    return row[0] if row else None


def _year(data):
    match = re.search(r'\b(19|20)\d{2}\b', str(data.get('date', '')))
    return int(match.group(0)) if match else None


def _kind(fields, data):
    text = (fields.get('Yayın türü', '') or data.get('itemType', '')).casefold()
    if 'ön baskı' in text or 'preprint' in text or 'arxiv' in text:
        return 'preprint'
    if 'derleme' in text or 'survey' in text or 'review' in text:
        return 'review'
    return 'other'


def _screening_stage(store):
    """Title/abstract stage as read from Zotero (stage tags) and, when present, the decisions file's box counts."""
    from . import screening
    codes, selected, spare = {}, 0, 0
    for state, raw in store.db.execute("SELECT state,data_json FROM papers WHERE state IN ('title_passed','excluded_title')"):
        tags = {t.get('tag') for t in json.loads(raw).get('tags', []) if isinstance(t, dict)}
        if state == 'excluded_title':
            found = sorted(t for t in tags if t and EXCLUSION_CODE.fullmatch(t))
            code = found[0] if found else 'kodsuz'
            codes[code] = codes.get(code, 0) + 1
        elif screening.TAGS['Yedek'] in tags:
            spare += 1
        elif screening.TAGS['Seçildi'] in tags:
            selected += 1
    stage = {'haric_kodlar': dict(sorted(codes.items())), 'secilen': selected, 'yedek': spare, 'dosya': None, 'onayli': False}
    path = store.path(screening.RELATIVE.as_posix())
    if path.is_file():
        try:
            data = screening.load(path)
            stage.update(dosya=screening.counts(data), onayli=screening.approved(data))
        except ValidationError:
            pass
    return stage


def delivery_report(store):
    """Read-only check of the Kısım I package: counts, PRISMA numbers, guide limits and missing fields."""
    from .pdf_archive import ARCHIVE_DIR, MATRIX_ID, archive_name
    issues = []
    def add(level, message):
        issues.append({'level': level, 'message': message})
    with store.lock:
        for job in store.pending():
            add('hata', f"Eksik yakalama: {job['id']}")
        runs = sorted(store.list_runs(), key=lambda r: r['display_id'])
        transferred = 0
        for run in runs:
            caps = store.captures(run['id'])
            if not caps:
                add('hata', f"{run['display_id']}: ekran görüntüsü yok.")
            for c in caps:
                file = store.path(c['relative_path'])
                if not file.exists():
                    add('hata', f"{run['display_id']}: görsel bulunamadı.")
                elif digest(file.read_bytes()) != c['sha256']:
                    add('hata', f"{run['display_id']}: görsel özeti değişmiş.")
            info = store.export_info(run['id'])
            if info['effective_count'] is None:
                add('uyarı', f"{run['display_id']}: aktarılan kayıt sayısı yok. Yalnız eşik aramasıysa 0 girin; "
                             f"değilse RIS'i Zotero'da {run['display_id']} koleksiyonuna aktarıp Zotero'dan okuyun.")
            else:
                transferred += info['effective_count']
            if not (run['operator'] or '').strip():
                add('uyarı', f"{run['display_id']}: işlemi yapan boş (Ayarlar → Kaydı yapan kişi).")
            for warning in info.get('uyarilar', []):
                add('uyarı', f"{run['display_id']}: {warning}.")
        known_codes = {r['display_id'] for r in runs}
        search_dates = {}
        for r in runs:
            try:
                search_dates[r['display_id']] = datetime.fromisoformat(str(r['observed_at_utc']).replace('Z', '+00:00')).astimezone(ZoneInfo('Europe/Istanbul')).date()
            except (TypeError, ValueError):
                pass
        states = {}
        for row in store.db.execute("SELECT state,COUNT(*) FROM papers GROUP BY state"):
            states[row[0]] = row[1]
        for code in sorted({r[0] for r in store.db.execute('SELECT code FROM paper_search_codes')} - known_codes):
            add('uyarı', f"Zotero'da {code} koleksiyonu var ama bu adla bir arama kaydı yok.")
        for row in store.db.execute("SELECT item_key FROM papers WHERE state='conflict'"):
            add('hata', f"{row[0]}: Zotero koleksiyon/not çelişkisi (aynı kayıt iki aşamada ya da iki not çelişiyor).")

        included = store.paper_rows('included')
        ids, readers, core, preprints, reviews, outside, good = {}, {}, 0, 0, 0, 0, 0
        window = _window_start(store)
        archive = store.path(ARCHIVE_DIR)
        for paper, data, fields in included:
            mid = fields.get('Matris ID', '').strip()
            label = mid or paper['item_key']
            if not mid:
                add('hata', f"{paper['item_key']} ({str(data.get('title', ''))[:60]}): Matris ID yok.")
            elif not MATRIX_ID.fullmatch(mid):
                add('hata', f"{label}: Matris ID L001 biçiminde olmalı.")
            elif mid in ids:
                add('hata', f"{label}: Matris ID iki kaynakta kullanılmış ({ids[mid]} ve {paper['item_key']}).")
            else:
                ids[mid] = paper['item_key']
            if fields.get('Karar', '').strip().casefold().startswith('hari'):
                add('hata', f"{label}: notta Karar: Hariç yazıyor ama kayıt dahil koleksiyonunda.")
            empty = [name for name in REQUIRED_FIELDS if not fields.get(name, '').strip()]
            if empty:
                add('uyarı', f"{label}: boş zorunlu alanlar — {', '.join(empty)}.")
            if fields.get('Temel bulgu', '').strip() and not PAGE_EVIDENCE.search(fields['Temel bulgu']):
                add('uyarı', f"{label}: Temel bulgu'da sayfa/tablo numarası yok (kılavuz s. 14).")
            if not paper['verified'] or not paper['annotation'].strip():
                add('uyarı', f"{label}: anotasyon kontrol edilmedi veya boş.")
            codes = store.paper_search_codes(paper['id'])
            if not codes:
                add('hata', f"{label}: bulunma yolu yok (S00x koleksiyonu veya elle bağlantı).")
            found = [search_dates[c] for c in codes if c in search_dates]
            read = _note_date(fields.get('Okuma tarihi', ''))
            if found and read and read < min(found):
                add('uyarı', f"{label}: okuma tarihi ({fields['Okuma tarihi'].strip()}) kaynağın bulunduğu aramadan "
                             f"({min(found).strftime('%d.%m.%Y')}) önce.")
            if fields.get('_bilinmeyen_alanlar'):
                add('uyarı', f"{label}: notta tanınmayan alan adı — {fields['_bilinmeyen_alanlar']}.")
            name = archive_name(fields, data)
            if name and not (archive / name).is_file():
                add('uyarı', f"{label}: {ARCHIVE_DIR}/{name} bulunamadı (PDF arşivini oluşturun).")
            reader = fields.get('Okuyan kişi', '').strip() or 'belirtilmemiş'
            readers[reader] = readers.get(reader, 0) + 1
            if fields.get('Çekirdek adayı', '').strip().casefold().startswith('evet') and '3' in fields.get('Okuma düzeyi', ''):
                core += 1
            kind = _kind(fields, data)
            preprints += kind == 'preprint'
            reviews += kind == 'review'
            year = _year(data)
            if window and year and year < window:
                outside += 1
                if not fields.get('İstisna gerekçesi', '').strip():
                    add('hata', f"{label}: {year} yılı pencere ({window}–) dışında; İstisna gerekçesi boş.")
            good += bool(GOOD_QUALITY.search(fields.get('Kalite sınıfı ve yılı', '')))

        by_code = {}
        for paper, data, fields in store.paper_rows('excluded'):
            text = fields.get('Gerekçe kodu', '') or fields.get('Dahil/hariç gerekçesi', '')
            match = EXCLUSION_CODE.search(text)
            code = match.group(0) if match else 'kodsuz'
            by_code[code] = by_code.get(code, 0) + 1
            if not match:
                add('hata', f"{paper['item_key']} ({str(data.get('title', ''))[:60]}): hariç gerekçe kodu (H1–H6) yok.")
            if fields.get('Karar', '').strip().casefold().startswith('dahil'):
                add('hata', f"{paper['item_key']}: notta Karar: Dahil yazıyor ama kayıt hariç koleksiyonunda.")
            if not fields.get('Karar veren', '').strip():
                add('uyarı', f"{paper['item_key']}: hariç kararında Karar veren boş.")

        n = len(included)
        unique = sum(v for k, v in states.items() if k != 'unavailable')
        stage = _screening_stage(store)
        # Records left outside a limited screening scope are reported in their own box, not as waiting.
        # Titles passed whose abstracts were not read stay in 01_Aday without a decision, like an unscreened record.
        unscreened = (stage['dosya']['taranmadi'] + stage['dosya']['ozet_okunmadi']) if stage['dosya'] else 0
        waiting = max(0, states.get('candidate', 0) - unscreened) + states.get('title_passed', 0) - stage['yedek']
        prisma = {'aktarilan_kayit': transferred, 'benzersiz_kayit': unique,
                  'cikarilan_tekrar': transferred - unique if transferred >= unique else None,
                  'baslik_ozet_haric': states.get('excluded_title', 0),
                  'baslik_ozet_haric_kodlar': stage['haric_kodlar'],
                  'baslik_ozet_gecen': states.get('title_passed', 0) + n + states.get('excluded', 0),
                  'tam_metin_icin_secilen_bekleyen': stage['secilen'], 'yedek_tam_metni_degerlendirilmeyen': stage['yedek'],
                  'tam_metni_degerlendirilen': n + states.get('excluded', 0),
                  'tam_metin_haric': states.get('excluded', 0), 'tam_metin_haric_kodlar': dict(sorted(by_code.items())),
                  'dahil': n, 'karar_bekleyen': waiting, 'celiskili': states.get('conflict', 0)}
        if transferred < unique:
            add('uyarı', f"PRISMA: aktarılan kayıt toplamı ({transferred}) Zotero'daki benzersiz kayıttan ({unique}) az; "
                         'bazı aramaların aktarım sayısı eksik olabilir.')
        if waiting:
            add('uyarı', f'PRISMA: {waiting} kayıt henüz başlık-özet veya tam metin kararı almadı.')
        file_counts = stage['dosya']
        if file_counts:
            prisma.update(baslik_incelenen=file_counts['baslik_incelenen'], baslik_haric=file_counts['baslik_haric'],
                          ozet_incelenen=file_counts['ozet_incelenen'], ozet_haric=file_counts['ozet_haric'],
                          ozet_okunmadi=file_counts['ozet_okunmadi'], taranmayan=file_counts['taranmadi'])
            if stage['onayli'] and (file_counts['haric'], file_counts['gecen']) != (prisma['baslik_ozet_haric'], prisma['baslik_ozet_gecen']):
                add('uyarı', f"PRISMA: eleme karar dosyasında başlık-özet hariç {file_counts['haric']} / geçen {file_counts['gecen']}, "
                             f"Zotero'da {prisma['baslik_ozet_haric']} / {prisma['baslik_ozet_gecen']}. Zotero bölümündeki "
                             "Başlık-özet eleme panelinden uygulayıp Zotero'dan yeniden okuyun.")
        quality_needed = -(-n // 2)
        limits = [
            {'kural': 'Dahil edilen kaynak ≥ 80 (K1)', 'deger': n, 'tamam': n >= MIN_INCLUDED},
            {'kural': 'Çekirdek (Evet + 3. geçiş) ≥ 20 (K8)', 'deger': core, 'tamam': core >= MIN_CORE},
            {'kural': 'Ön baskı ≤ 8 (K2)', 'deger': preprints, 'tamam': preprints <= MAX_PREPRINT},
            {'kural': 'Derleme ≤ 10 (K2)', 'deger': reviews, 'tamam': reviews <= MAX_REVIEW},
            {'kural': f'Pencere ({window or "?"}–) dışı temel çalışma ≤ 8 (K5)', 'deger': outside,
             'tamam': bool(window) and outside <= MAX_OUTSIDE_WINDOW},
            {'kural': f'Q1–Q2 / CORE A*–A ≥ yarı ({quality_needed}) (K6)', 'deger': good, 'tamam': n > 0 and good >= quality_needed},
        ]
        if not window:
            add('uyarı', 'Yıl penceresi belirlenemedi; programdaki onaylı yıl daraltmasını kullanın.')
        for limit in limits:
            if not limit['tamam']:
                add('hata', f"Sınır sağlanmıyor: {limit['kural']} — şu an {limit['deger']}.")
        counts = {'arama': len(runs), 'durumlar': states, 'okuyanlar': readers}
        return {'counts': counts, 'prisma': prisma, 'limits': limits, 'issues': issues}


def check_project(store):
    """Issue messages for manifests and the output report."""
    return [f"{i['level'].upper()}: {i['message']}" for i in delivery_report(store)['issues']]


def _text(value):return html.escape(str(value or '')).replace('\n','<br/>')


def _bib_value(value):
    return str(value).replace('\x00','').replace('\\','\x00').replace('{','\\{').replace('}','\\}').replace('\x00','\\textbackslash{}')


# Characters LaTeX treats as commands in running text (bibliography titles, venues, publishers).
_LATEX_SPECIALS=(('&','\\&'),('%','\\%'),('#','\\#'),('_','\\_'),('$','\\$'))
# Proper nouns that a style such as IEEEtran would otherwise lower-case in a title ("turkish").
BIB_PROPER_NOUNS={'Turkish','Turkey','Türkiye','Amharic','Kazakh','Thai','Philippine','Dukcapil','English','Korean',
                  'Chinese','Arabic','Vietnamese','Indonesian','Hindi','Bengali','Persian','Urdu','Japanese','German',
                  'French','Spanish','Italian','Russian','European','Wikipedia'}
# Combining marks of a decomposed letter → LaTeX accent command (BibTeX abbreviates a first name to its first byte,
# which breaks a UTF-8 initial such as "Ş."; an accent command in braces is abbreviated as one letter).
_LATEX_ACCENTS={'\u0301':"\\'",'\u0300':'\\`','\u0302':'\\^','\u0308':'\\"','\u0303':'\\~','\u0304':'\\=',
                '\u0307':'\\.','\u0327':'\\c','\u0326':'\\textcommabelow','\u0306':'\\u','\u030c':'\\v',
                '\u030a':'\\r','\u0328':'\\k','\u030b':'\\H'}
_LATEX_LETTERS={'Ø':'\\O','Ł':'\\L','Æ':'\\AE','Œ':'\\OE','Đ':'\\DJ'}


def _bib_text(value):
    """Escaped BibTeX value for running text: braces, backslash and the LaTeX special characters."""
    text=_bib_value(value)
    for char,escaped in _LATEX_SPECIALS:text=re.sub(r'(?<!\\)'+re.escape(char),lambda _:escaped,text)
    return text


def _protect_word(word):
    core=re.sub(r'^\W+|\W+$','',word)
    if not core or '\\' in core:return word
    capitals=len(re.findall(r'[A-ZÇĞİÖŞÜ]',core))
    if capitals>=2 or (capitals and re.search(r'\d',core)) or core in BIB_PROPER_NOUNS:
        return word.replace(core,'{'+core+'}',1)
    return word


def _bib_title(value):
    """Title for a style that changes case: acronyms, mixed-case names (RAG, LLMs, FaithEval, BM25) and proper nouns
    are kept in braces so they stay as written; hyphenated words are protected part by part."""
    return ''.join(token if not token or token.isspace() else '-'.join(_protect_word(p) for p in token.split('-'))
                   for token in re.split(r'(\s+)',_bib_text(value)))


def _latex_letter(char):
    if char in _LATEX_LETTERS:return '{'+_LATEX_LETTERS[char]+'}'
    import unicodedata
    base,*marks=unicodedata.normalize('NFD',char)
    if len(marks)!=1 or marks[0] not in _LATEX_ACCENTS or not base.isascii():return char
    command=_LATEX_ACCENTS[marks[0]]
    return '{'+command+(base if command[1:2] in "'`^\"~=." else '{'+base+'}')+'}'


def _bib_given(value):
    """Given names: a non-ASCII initial (Ş, Ç, Ö, Á …) becomes a LaTeX accent command so the abbreviated name is valid."""
    return re.sub(r'(?:(?<=^)|(?<=[\s.\-]))([^\x00-\x7f])',lambda m:_latex_letter(m.group(1)),_bib_text(value))


def export_sources(store,draft=False):
    """Annotated source list (PDF) and BibTeX of the included papers in matrix order; citation keys are the matrix IDs
    (L001 …) so the report can cite a source by the same ID as the matrix and the PDF archive."""
    from .pdf_archive import MATRIX_ID
    with store.lock:
        rows=store.paper_rows('included')
        if not rows:raise ValidationError('Dahil edilmiş kaynak yok. Önce Zotero koleksiyonlarını eşleştirin.')
        papers=[paper for paper,_,_ in rows]
        bad=[p['item_key'] for p in papers if not p['verified'] or not p['annotation'].strip()]
        if bad and not draft:raise ValidationError('Kontrol edilmemiş anotasyonlar: '+', '.join(bad[:15])+'. Taslak çıktı seçilebilir.')
        settings=store.settings();prefix=settings['team_code']+'_O2'
        suffix='_TASLAK' if draft else ''
        ss=styles();story=[Paragraph('Anotasyonlu kaynak listesi'+(' — TASLAK' if draft else ''),ss['Title']),
                          Paragraph(_text(settings['project_name']),ss['BodyText']),Spacer(1,16)]
        bibliography=BibDatabase();keys=[];ids=[]
        for index,(paper,data,fields) in enumerate(rows,1):
            mid=fields.get('Matris ID','').strip()
            key=mid if MATRIX_ID.fullmatch(mid) and mid not in keys else 'Z_'+re.sub('[^A-Za-z0-9_]','_',paper['library_id'])+'_'+paper['item_key']
            keys.append(key);ids.append(paper['id'])
            creators=data.get('creators',[])
            authors=['{'+_bib_text(c['name'])+'}' if c.get('name') else _bib_text(c.get('lastName',''))+', '+_bib_given(c.get('firstName','')) for c in creators if c.get('creatorType')=='author']
            entry={'ENTRYTYPE':{'journalArticle':'article','conferencePaper':'inproceedings'}.get(data.get('itemType'),'misc'),
                   'ID':key,'title':_bib_title(plain_text(data.get('title','')))}
            if authors:entry['author']=' and '.join(authors)
            year=re.search(r'\b(19|20)\d{2}\b',data.get('date',''))
            if year:entry['year']=year[0]
            for source,target in [('DOI','doi'),('volume','volume'),('issue','number'),('publisher','publisher'),('place','address')]:
                # A DOI is an identifier, not text: only braces are escaped.
                if data.get(source):entry[target]=(_bib_value if source=='DOI' else _bib_text)(plain_text(data[source]))
            if data.get('pages'):entry['pages']=_bib_value(re.sub(r'\s*[-–]\s*','--',plain_text(data['pages'])))
            # A database record page (e.g. Scopus) is not a publisher link; the DOI already identifies the paper.
            if data.get('url') and not data.get('DOI') and 'scopus.com' not in data['url']:entry['url']=_bib_value(data['url'])
            venue=data.get('publicationTitle') or data.get('proceedingsTitle')
            if venue:entry['booktitle' if entry['ENTRYTYPE']=='inproceedings' else 'journal']=_bib_text(plain_text(venue))
            bibliography.entries.append(entry)
            citation=citation_text(data) if data.get('citation') else ''
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
        # The manifest is a working record of what was exported; it stays out of the submission folder.
        # The annotated source list is a working document for the team; Kısım I submits only the .bib file.
        files={
          'pdf':(f'03_Calisma/{prefix}_KaynakListesi{suffix}.pdf',buffer.getvalue()),
          'bib':(f'05_Teslim/{prefix}_kaynaklar{suffix}.bib',bib.encode('utf-8')),
          'manifest':(f'03_Calisma/Veri/{prefix}_kaynak_manifest{suffix}.json',json_text({'created_at':utcnow(),'draft':draft,'paper_ids':ids,'citekeys':keys,'issues':check_project(store)}).encode('utf-8'))}
        result={}
        for kind,(relative,content) in files.items():
            relative=store.write_output(relative,content);result[kind]=str(store.path(relative))
        return result


def export_all(store):
    """Every Kısım I file the program produces, in one go, into 05_Teslim; then the delivery check."""
    result={'excel':store.export_excel()['path'],'matris':store.export_delivery_workbook()['path'],
            'ekranlar':export_evidence(store)['pdf'],'prisma':export_prisma(store)['pdf']}
    sources=export_sources(store)
    result['bib']=sources['bib']
    report=delivery_report(store)
    result['hata']=sum(1 for i in report['issues'] if i['level']=='hata')
    result['uyari']=sum(1 for i in report['issues'] if i['level']!='hata')
    result['issues']=[f"{i['level'].upper()}: {i['message']}" for i in report['issues']]
    return result


# Built-in font: the label is ASCII (S001 …), so the page needs no Turkish font.
EVIDENCE_LABEL=ParagraphStyle('EvidenceLabel',fontName='Helvetica-Bold',fontSize=14,leading=18,alignment=1,spaceBefore=8)


def export_evidence(store):
    """05_Teslim/<takım>_O2_AramaEkranlari.pdf: one page per search result screenshot, in search order. The
    screenshots themselves show the date and the result count (Kılavuz Bölüm 7); only the search code (S001 …) is
    written under each one so a page can be matched to its Arama_Kaydi row."""
    with store.lock:
        rows=[]
        for run in sorted(store.list_runs(),key=lambda r:int(r['display_id'][1:])):
            for capture in store.captures(run['id']):rows.append((run,capture))
        if not rows:raise ValidationError('Dışa aktarılacak doğrulanmış ekran kaydı yok.')
        story=[];page_width,page_height=landscape(A4)
        for index,(run,cap) in enumerate(rows):
            file=store.path(cap['relative_path'])
            if not file.exists() or digest(file.read_bytes())!=cap['sha256']:raise ValidationError('Eksik veya değişmiş PNG: '+run['display_id'])
            if index:story.append(PageBreak())
            image=Image(str(file));image._restrictSize(page_width-48,page_height-48-30);story.append(image)
            story.append(Paragraph(html.escape(run['display_id']),EVIDENCE_LABEL))
        out=io.BytesIO();SimpleDocTemplate(out,pagesize=landscape(A4),leftMargin=24,rightMargin=24,topMargin=24,bottomMargin=24,
                                           title=f"{store.settings()['team_code']}_O2 Arama Ekranları",author=store.settings()['operator']).build(story)
        relative=store.write_output(f"05_Teslim/{store.settings()['team_code']}_O2_AramaEkranlari.pdf",out.getvalue())
        return {'pdf':str(store.path(relative))}


def prisma_boxes(store):
    """PRISMA 2020 flow numbers (Kılavuz Adım 7) from the delivery report; full-text H3 exclusions are 'not retrieved'."""
    report = delivery_report(store)
    p = report['prisma']
    with store.lock:
        sources = {}
        for run in store.list_runs():
            count = store.export_info(run['id'])['effective_count']
            if count:
                sources[run['database_name']] = sources.get(run['database_name'], 0) + count
    codes = dict(p['tam_metin_haric_kodlar'])
    not_retrieved = codes.pop('H3', 0)
    screened = p['benzersiz_kayit']
    boxes = {
        'kaynaklar': dict(sorted(sources.items())), 'bulunan': p['aktarilan_kayit'],
        'tekrar': p['cikarilan_tekrar'], 'taranan': screened,
        'baslik_haric': p.get('baslik_haric'), 'ozet_incelenen': p.get('ozet_incelenen'), 'ozet_haric': p.get('ozet_haric'),
        'taranmayan': p.get('taranmayan') or 0, 'baslik_incelenen': p.get('baslik_incelenen'),
        'ozet_okunmadi': p.get('ozet_okunmadi') or 0,
        'baslik_ozet_haric': p['baslik_ozet_haric'], 'baslik_ozet_kodlar': p['baslik_ozet_haric_kodlar'],
        'gecen': p['baslik_ozet_gecen'], 'yedek': p['yedek_tam_metni_degerlendirilmeyen'],
        'istenen': p['baslik_ozet_gecen'] - p['yedek_tam_metni_degerlendirilmeyen'],
        'erisilemeyen': not_retrieved, 'degerlendirilen': p['tam_metni_degerlendirilen'] - not_retrieved,
        'tam_metin_haric': p['tam_metin_haric'] - not_retrieved, 'tam_metin_kodlar': codes,
        'dahil': p['dahil'], 'karar_bekleyen': p['karar_bekleyen']}
    return boxes


def _thousands(value):
    return '?' if value is None else f'{value:,}'.replace(',', '.')


def _codes(codes):
    return ', '.join(f'{k}: {_thousands(v)}' for k, v in codes.items())


def _wrap(lines, font, size, width):
    out = []
    for text in lines:
        # '(n = 1.541)' stays on one line: the count is joined with no-break spaces before wrapping.
        words, line = text.replace('(n = ', '(n\u00a0=\u00a0').split(' '), ''
        for word in words:
            candidate = (line + ' ' + word).strip()
            if line and pdfmetrics.stringWidth(candidate, font, size) > width:
                out.append(line)
                line = word
            else:
                line = candidate
        out.append(line)
    return out


def export_prisma(store):
    """05_Teslim/<takım>_O2_PRISMA.pdf. While decisions are pending the page says TASLAK and how many are waiting."""
    font = register_font()
    b = prisma_boxes(store)
    n = _thousands
    rows = [('Tanımlama',
             [f"Veritabanlarından bulunan kayıt (n = {n(b['bulunan'])})"] + [f'{name} (n = {n(v)})' for name, v in b['kaynaklar'].items()],
             [f"Çıkarılan tekrar kayıt (n = {n(b['tekrar'])})"])]
    if b['taranmayan']:
        rows += [('Tarama', [f"Tekrarlar çıkarıldıktan sonra kayıt (n = {n(b['taranan'])})"],
                  [f"Taranmayan kayıt (n = {n(b['taranmayan'])})"])]
    if b['baslik_haric'] is not None:
        rows += [('' if b['taranmayan'] else 'Tarama', [f"Başlığı incelenen kayıt (n = {n(b['baslik_incelenen'])})"],
                  [f"Başlıktan hariç tutulan (n = {n(b['baslik_haric'])})"])]
        if b['ozet_okunmadi']:
            rows += [('', [f"Başlık aşamasını geçen (n = {n(b['baslik_incelenen'] - b['baslik_haric'])})"],
                      [f"Özeti incelenmeyen (n = {n(b['ozet_okunmadi'])})"])]
        rows += [
                 ('', [f"Özeti incelenen kayıt (n = {n(b['ozet_incelenen'])})"],
                  [f"Özetten hariç tutulan (n = {n(b['ozet_haric'])})",
                   f"Başlık-özet aşamasında toplam hariç (n = {n(b['baslik_ozet_haric'])}): {_codes(b['baslik_ozet_kodlar'])}"])]
    else:
        rows += [('Tarama', [f"Başlığı ve özeti incelenen kayıt (n = {n(b['taranan'])})"],
                  [f"Hariç tutulan (n = {n(b['baslik_ozet_haric'])})", _codes(b['baslik_ozet_kodlar'])])]
    if b['yedek']:
        rows += [('', [f"Başlık-özet aşamasını geçen (n = {n(b['gecen'])})"],
                  [f"Tam metin için seçilmeyen (n = {n(b['yedek'])})"])]
    rows += [('', [f"Tam metni istenen (n = {n(b['istenen'])})"], [f"Tam metnine erişilemeyen, H3 (n = {n(b['erisilemeyen'])})"]),
             ('', [f"Tam metni değerlendirilen (n = {n(b['degerlendirilen'])})"],
              [f"Tam metinde hariç tutulan (n = {n(b['tam_metin_haric'])})", _codes(b['tam_metin_kodlar'])]),
             ('Dahil etme', [f"Derlemeye dahil edilen çalışma (n = {n(b['dahil'])})"], [])]
    buffer = io.BytesIO()
    width, height = A4
    c = pdf_canvas.Canvas(buffer, pagesize=A4)
    team = store.settings()['team_code']
    c.setTitle(f'{team}_O2 PRISMA')
    c.setFont(font, 14)
    title = 'PRISMA 2020 akış şeması'
    if b['karar_bekleyen']:
        title += f" — TASLAK ({n(b['karar_bekleyen'])} kayıt karar bekliyor)"
    c.drawString(40, height - 50, title)
    left, box_w, right, side_w, line_h = 110, 230, 375, 185, 13
    y = height - 80
    previous = None
    for stage, main, side in rows:
        main = _wrap(main, font, 9, box_w - 12)
        side = _wrap([s for s in side if s], font, 9, side_w - 12)
        lines = max(len(main), len(side)) or 1
        box_h = lines * line_h + 14
        top = y
        c.setFont(font, 9)
        c.rect(left, top - box_h, box_w, box_h)
        for i, text in enumerate(main):
            c.drawString(left + 6, top - 16 - i * line_h, text)
        if previous is not None:
            c.line(left + box_w / 2, previous, left + box_w / 2, top)
            c.line(left + box_w / 2 - 3, top + 5, left + box_w / 2, top)
            c.line(left + box_w / 2 + 3, top + 5, left + box_w / 2, top)
        if side:
            c.rect(right, top - box_h, side_w, box_h)
            for i, text in enumerate(side):
                c.drawString(right + 6, top - 16 - i * line_h, text)
            c.line(left + box_w, top - box_h / 2, right, top - box_h / 2)
            c.line(right - 5, top - box_h / 2 + 3, right, top - box_h / 2)
            c.line(right - 5, top - box_h / 2 - 3, right, top - box_h / 2)
        if stage:
            c.setFont(font, 10)
            c.drawString(40, top - 16, stage)
        previous = top - box_h
        y = previous - 26
    c.showPage()
    c.save()
    with store.lock:
        relative = store.write_output(f'05_Teslim/{team}_O2_PRISMA.pdf', buffer.getvalue())
    return {'pdf': str(store.path(relative)), 'kutular': b}
