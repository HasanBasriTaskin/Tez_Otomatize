import json
import re
import time
import uuid
from html.parser import HTMLParser
from urllib.request import Request,urlopen
from urllib.parse import urlencode
from urllib.error import HTTPError,URLError

from .storage import ValidationError,json_text,utcnow,safe_url


# Every field the reader can write in a Zotero child note. Older notes keep working: the first
# 24 names are the original template; later names were added for the matrix ID and exclusion log.
NOTE_FIELDS=['Amaç/problem','Yöntem','Veri seti ve dil','Karşılaştırılan yöntemler','Değerlendirme metrikleri',
             'Temel bulgu','Yazarların sınırlılıkları','Benim değerlendirmem','Tezle ilişki','Kanıt sayfaları',
             'Okuma düzeyi','Okuyan kişi','Okuma tarihi','Dahil/hariç gerekçesi','Anotasyon',
             'Kalite sınıfı ve yılı','Kalite kaynağı','Deney düzeni','Kaynak ihtiyacı','Açık kod/veri',
             'Tema','Yerel PDF','PDF bağlantısı','Çekirdek adayı',
             'Matris ID','Karar','Yayın türü','Aşama','Gerekçe kodu','Karar veren','Karar tarihi','İstisna gerekçesi']
FIELD_ALIASES={'3–5 cümlelik anotasyon':'Anotasyon','kanıt sayfaları/bölümler/tablolar':'Kanıt sayfaları',
               'açıklama':'Dahil/hariç gerekçesi'}

# Template lines: (field, prefilled value or hint). A hint is shown in parentheses and counts as empty
# until the reader replaces it, so an untouched template never looks like real data.
READING_LINES=[('Matris ID','(L001, L002 … dahil edince verin)'),('Karar','Dahil'),
               ('Yayın türü','(Dergi makalesi / Konferans bildirisi / Ön baskı / Derleme)'),
               ('Kalite sınıfı ve yılı','(ör. Q1 (JCR 2025) veya CORE A* (2023))'),('Kalite kaynağı','(JCR/SJR/CORE bağlantısı)'),
               ('Okuyan kişi',''),('Okuma düzeyi','(1 / 2 / 3)'),('Okuma tarihi','(GG.AA.YYYY)'),('Çekirdek adayı','(Evet / Hayır)'),
               ('Amaç/problem',''),('Yöntem',''),('Karşılaştırılan yöntemler',''),('Veri seti ve dil',''),('Deney düzeni',''),
               ('Değerlendirme metrikleri',''),('Temel bulgu','(sayı + koşul + sayfa/tablo, ör. Recall@5 = 0,81 (Tablo 3, s. 6))'),
               ('Kaynak ihtiyacı','(gecikme/bellek/maliyet ölçülmüş mü?)'),('Açık kod/veri','(bağlantı veya Hayır)'),
               ('Yazarların sınırlılıkları',''),('Benim değerlendirmem',''),('Tema','(T1_Parcalama, T2_Erisim …)'),('Tezle ilişki','(AS1–AS5)'),
               ('Kanıt sayfaları',''),('İstisna gerekçesi','(yalnız 2024 öncesi temel çalışmada doldurun)'),
               ('Yerel PDF','(boş bırakılırsa program L001_Yazar_Yil_KisaBaslik.pdf adını üretir)'),('PDF bağlantısı',''),
               ('Anotasyon','(3–5 cümle, kendi cümlelerinizle)')]
EXCLUSION_LINES=[('Karar','Hariç'),('Aşama','Tam metin'),('Gerekçe kodu','(H1 / H2 / H3 / H4 / H5 / H6)'),
                 ('Açıklama',''),('Karar veren',''),('Karar tarihi','(GG.AA.YYYY)')]


def _template(lines):
    return '\n'.join(f'{name}: {value}'.rstrip() + ('' if value else ' ') for name,value in lines)


READING_TEMPLATE=_template(READING_LINES)
EXCLUSION_TEMPLATE=_template(EXCLUSION_LINES)
NOTE_TEMPLATE=READING_TEMPLATE  # kept for older callers
TEMPLATE_HINTS={value for _,value in READING_LINES+EXCLUSION_LINES if value.startswith('(')}
UNKNOWN_KEY='_bilinmeyen_alanlar'
# A line such as "Gerekce: x" looks like a field name: short, letters and spaces only.
FIELD_LIKE=re.compile(r'[^\W\d_](?:[^\W\d_]|[ /\-]){0,38}',re.UNICODE)
SEARCH_CODE=re.compile(r'(S\d{3,})(?!\d)')
EXCLUSION_CODES=re.compile(r'\bH[1-6]\b')


class PlainText(HTMLParser):
    def __init__(self):super().__init__();self.parts=[];self.hidden=0
    def handle_starttag(self,tag,attrs):
        if tag in ('script','style'):self.hidden+=1
        if tag in ('p','br','li','div','h1','h2','h3','tr'):self.parts.append('\n')
    def handle_endtag(self,tag):
        if tag in ('script','style'):self.hidden=max(0,self.hidden-1)
        if tag in ('p','li','div','h1','h2','h3','tr'):self.parts.append('\n')
    def handle_data(self,data):
        if not self.hidden:self.parts.append(data)


def plain_html(value):
    parser=PlainText();parser.feed(value or '');return ''.join(parser.parts).strip()


def parse_note(value):
    """Read `Field: value` lines. Unknown field-like keys stay with the previous field (no data loss)
    and are reported under UNKNOWN_KEY so a typo cannot silently corrupt another column."""
    output={};current=None;unknown=[]
    aliases={k.casefold():k for k in NOTE_FIELDS}
    aliases.update(FIELD_ALIASES)
    for line in plain_html(value).splitlines():
        line=line.strip()
        if not line:continue
        key,sep,content=line.partition(':')
        if sep and key.strip().casefold() in aliases:
            current=aliases[key.strip().casefold()];output[current]=content.strip()
            continue
        if sep and FIELD_LIKE.fullmatch(key.strip()) and key.strip() not in unknown:unknown.append(key.strip())
        if current:output[current]+='\n'+line
    for field,text in list(output.items()):
        if text.strip() in TEMPLATE_HINTS:output[field]=''
    if unknown:output[UNKNOWN_KEY]=', '.join(unknown)
    return output


def save_api_key(key,mode='web'):
    import win32cred
    name='LiteraturKayit/Zotero/'+mode
    if not key:
        try:win32cred.CredDelete(name,win32cred.CRED_TYPE_GENERIC,0)
        except Exception:pass
        return
    if not isinstance(key,str) or not re.fullmatch(r'[A-Za-z0-9_-]{8,200}',key):raise ValidationError('Geçersiz Zotero anahtarı.')
    win32cred.CredWrite({'Type':win32cred.CRED_TYPE_GENERIC,'TargetName':name,'UserName':'Zotero',
                        'CredentialBlob':key.encode('utf-16-le'),'Persist':win32cred.CRED_PERSIST_LOCAL_MACHINE},0)


def load_api_key(mode):
    import win32cred
    try:return win32cred.CredRead('LiteraturKayit/Zotero/'+mode,win32cred.CRED_TYPE_GENERIC)['CredentialBlob'].decode('utf-16-le')
    except Exception:return ''


class ZoteroClient:
    def __init__(self,settings):
        self.mode=settings.get('zotero_mode','local')
        if self.mode not in ('local','web'):raise ValidationError('Zotero bağlantı türü geçersiz.')
        self.base='http://127.0.0.1:23119/api' if self.mode=='local' else 'https://api.zotero.org'
        self.library=settings.get('library','users/0')
        if not re.fullmatch(r'(users|groups)/\d+',self.library):raise ValidationError('Geçersiz kütüphane kimliği.')

    def _get(self,path,params):
        key=load_api_key(self.mode)
        headers={'Zotero-API-Version':'3','User-Agent':'LiteraturKayit/0.1'}
        if key:headers['Zotero-API-Key']=key
        if self.mode=='web' and not key:raise ValidationError('Zotero Web API için salt okunur anahtar girin.')
        url=self.base+'/'+self.library+'/'+path+'?'+urlencode(params)
        for attempt in range(3):
            try:
                with urlopen(Request(url,headers=headers,method='GET'),timeout=20) as response:
                    raw=response.read(16*1024*1024+1)
                    if len(raw)>16*1024*1024:raise ValidationError('Zotero yanıtı çok büyük.')
                    self._last_version=response.headers.get('Last-Modified-Version')
                    return json.loads(raw)
            except HTTPError as e:
                if e.code in (429,503) and attempt<2:
                    time.sleep(min(10,int(e.headers.get('Retry-After','2'))));continue
                if e.code in (401,403):raise ValidationError('Zotero erişimi reddetti. Yerel API iznini veya salt okunur anahtarı kontrol edin.') from None
                raise ValidationError(f'Zotero HTTP {e.code} yanıtı verdi. Kütüphane kimliğini kontrol edin.') from None
            except (URLError,TimeoutError):raise ValidationError('Zotero bağlantısı kurulamadı. Zotero açık ve yerel API erişimi etkin olmalı.') from None

    def all(self,kind):
        if kind not in ('items','collections'):raise ValidationError('Geçersiz Zotero kaynak türü.')
        result=[];seen=set();start=0;version=None
        while True:
            params={'format':'json','limit':100,'start':start}
            if kind=='items':params.update(include='data,bib',style='ieee')
            batch=self._get(kind,params)
            if not isinstance(batch,list):raise ValidationError('Beklenmeyen Zotero yanıtı.')
            current_version=getattr(self,'_last_version',None)
            if start and current_version!=version:raise ValidationError('Zotero kütüphanesi okunurken değişti. Yeniden deneyin.')
            version=current_version
            for obj in batch:
                key=obj.get('key') if isinstance(obj,dict) else None
                if not key or key in seen:raise ValidationError('Zotero sayfalama sonucu yineleniyor veya bozuk.')
                seen.add(key)
            result.extend(batch)
            if len(batch)<100:return result
            start+=len(batch)


# Collection roles from the manager screen, latest screening stage first.
ROLE_STATES=[('included','included'),('excluded','excluded'),('excluded_title','excluded_title'),
             ('title_abstract','title_passed'),('candidate','candidate')]
CONFLICTING_ROLES=[{'included','excluded'},{'included','excluded_title'},{'title_abstract','excluded_title'}]
PDF_LINK_MODES={'imported_file','imported_url'}


def search_codes(collection_names):
    """S codes named by Zotero collections such as `S004` or `S004_Scopus`."""
    codes=set()
    for name in collection_names:
        match=SEARCH_CODE.match((name or '').strip())
        if match:codes.add(match.group(1))
    return sorted(codes)


def _merge_notes(attached):
    parsed={};note_conflict=False
    for note in attached:
        for field,value in parse_note(note['note']).items():
            if field==UNKNOWN_KEY:
                known=[x for x in parsed.get(field,'').split(', ') if x]
                parsed[field]=', '.join(dict.fromkeys(known+value.split(', ')))
            elif field in parsed and parsed[field]!=value:
                # An empty duplicate field (e.g. an untouched template line) is not a disagreement.
                if not value:continue
                if not parsed[field]:parsed[field]=value
                else:note_conflict=True
            else:parsed[field]=value
    return parsed,note_conflict


def import_items(store,library,items,mapping,collections=None):
    """Mirror the Zotero library into the project database. Zotero stays the source of truth;
    nothing is written back. `collections` maps collection key -> name and enables S-code links."""
    notes={};attachments={};count=0;conflicts=0
    seen=set()
    for item in items:
        data=item.get('data',{})
        if data.get('itemType')=='note' and data.get('parentItem'):
            notes.setdefault(data['parentItem'],[]).append({'key':item.get('key'), 'note':data.get('note','')})
        if (data.get('itemType')=='attachment' and data.get('parentItem') and item.get('key')
                and data.get('contentType')=='application/pdf' and data.get('linkMode') in PDF_LINK_MODES):
            attachments.setdefault(data['parentItem'],[]).append((item['key'],data.get('filename',''),data.get('contentType',''),data.get('linkMode','')))
    names=collections or {}
    code_members={}
    with store.lock,store.db:
        for item in items:
            data=item.get('data',{})
            if data.get('itemType') in ('attachment','note','annotation') or not item.get('key'):continue
            data=dict(data)
            data['url']=safe_url(data.get('url',''))
            data['citation']=plain_html(item.get('bib',''))
            identity=item['key']
            seen.add(identity)
            attached=notes.get(identity,[])
            parsed,note_conflict=_merge_notes(attached)
            memberships=set(data.get('collections',[]))
            roles={role for role,collection in mapping.items() if collection and collection in memberships}
            conflict=note_conflict or any(pair<=roles for pair in CONFLICTING_ROLES)
            state='conflict' if conflict else next((st for role,st in ROLE_STATES if role in roles),'candidate')
            old=store.db.execute('SELECT * FROM papers WHERE library_id=? AND item_key=?',(library,identity)).fetchone()
            pid=old['id'] if old else str(uuid.uuid4())
            annotation=parsed.get('Anotasyon','')
            unchanged=bool(old and old['annotation']==annotation and old['data_json']==json_text(data))
            verified=old['verified'] if unchanged else 0
            store.db.execute('INSERT INTO papers VALUES(?,?,?,?,?,?,?,?) ON CONFLICT(library_id,item_key) DO UPDATE SET data_json=excluded.data_json,state=excluded.state,annotation=excluded.annotation,verified=excluded.verified,updated_at=excluded.updated_at',
                             (pid,library,identity,json_text(data),state,annotation,verified,utcnow()))
            store.db.execute('INSERT INTO reading_notes(paper_id,zotero_json,fields_json) VALUES(?,?,?) ON CONFLICT(paper_id) DO UPDATE SET zotero_json=excluded.zotero_json,fields_json=excluded.fields_json',
                             (pid,json_text(attached),json_text(parsed)))
            if state=='excluded':
                store.db.execute('INSERT OR REPLACE INTO screening_decisions VALUES(?,?,?,?)',(pid,state,parsed.get('Dahil/hariç gerekçesi',''),utcnow()))
            store.db.execute('DELETE FROM paper_attachments WHERE paper_id=?',(pid,))
            for key,filename,ctype,mode in attachments.get(identity,[]):
                store.db.execute('INSERT OR REPLACE INTO paper_attachments VALUES(?,?,?,?,?)',(pid,key,filename,ctype,mode))
            if collections is not None:
                codes=search_codes(names.get(c,'') for c in memberships)
                store.db.execute('DELETE FROM paper_search_codes WHERE paper_id=?',(pid,))
                for code in codes:
                    store.db.execute('INSERT INTO paper_search_codes VALUES(?,?)',(pid,code))
                    code_members.setdefault(code,set()).add(identity)
            count+=1;conflicts+=int(conflict)
        # A successful full library read is authoritative for availability, but never deletes local history.
        for old in store.db.execute('SELECT id,item_key FROM papers WHERE library_id=?',(library,)).fetchall():
            if old['item_key'] not in seen:
                store.db.execute("UPDATE papers SET state='unavailable',verified=0,updated_at=? WHERE id=?",(utcnow(),old['id']))
        # Items read earlier from another library (e.g. the personal library before the group was set)
        # are not part of this project's pool; keep them but stop counting them.
        store.db.execute("UPDATE papers SET state='unavailable',verified=0,updated_at=? WHERE library_id!=? AND state!='unavailable'",(utcnow(),library))
        unknown_codes=[]
        if collections is not None:
            now=utcnow()
            store.db.execute('UPDATE search_run_exports SET zotero_count=NULL,zotero_collection=NULL,zotero_checked_at=?',(now,))
            for code,members in sorted(code_members.items()):
                run=store.db.execute('SELECT id FROM search_runs WHERE display_id=?',(code,)).fetchone()
                if not run:unknown_codes.append(code);continue
                store.db.execute('INSERT OR IGNORE INTO search_run_exports(run_id,updated_at) VALUES(?,?)',(run['id'],now))
                collection=', '.join(sorted({n for n in names.values() if search_codes([n])==[code]}))
                store.db.execute('UPDATE search_run_exports SET zotero_count=?,zotero_collection=?,zotero_checked_at=? WHERE run_id=?',
                                 (len(members),collection,now,run['id']))
        store.audit('zotero_read',library,{'papers':count,'conflicts':conflicts,'unknown_codes':unknown_codes})
    # Items merged or deleted in Zotero stay in the mirror as unavailable; they are not duplicates any more.
    duplicates=[dict(r) for r in store.db.execute("SELECT json_extract(data_json,'$.DOI') AS doi,COUNT(*) AS count FROM papers WHERE library_id=? AND state!='unavailable' AND json_extract(data_json,'$.DOI')!='' GROUP BY lower(json_extract(data_json,'$.DOI')) HAVING COUNT(*)>1",(library,))]
    return {'count':count,'conflicts':conflicts,'duplicates':duplicates,'unknown_codes':unknown_codes}
