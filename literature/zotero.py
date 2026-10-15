import json
import re
import time
import uuid
from html.parser import HTMLParser
from urllib.request import Request,urlopen
from urllib.parse import urlencode
from urllib.error import HTTPError,URLError

from .storage import ValidationError,json_text,utcnow,safe_url


NOTE_FIELDS=['Amaç/problem','Yöntem','Veri seti ve dil','Karşılaştırılan yöntemler','Değerlendirme metrikleri',
             'Temel bulgu','Yazarların sınırlılıkları','Benim değerlendirmem','Tezle ilişki','Kanıt sayfaları',
             'Okuma düzeyi','Okuyan kişi','Okuma tarihi','Dahil/hariç gerekçesi','Anotasyon',
             'Kalite sınıfı ve yılı','Kalite kaynağı','Deney düzeni','Kaynak ihtiyacı','Açık kod/veri',
             'Tema','Yerel PDF','PDF bağlantısı','Çekirdek adayı']
NOTE_TEMPLATE='\n'.join(name+': ' for name in NOTE_FIELDS)


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
    output={};current=None
    aliases={k.casefold():k for k in NOTE_FIELDS}
    aliases.update({'3–5 cümlelik anotasyon':'Anotasyon','kanıt sayfaları/bölümler/tablolar':'Kanıt sayfaları'})
    for line in plain_html(value).splitlines():
        line=line.strip()
        if not line:continue
        key,sep,content=line.partition(':')
        if sep and key.casefold() in aliases:
            current=aliases[key.casefold()];output[current]=content.strip()
        elif current:output[current]+='\n'+line
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


def import_items(store,library,items,mapping):
    notes={};count=0;conflicts=0
    seen=set()
    for item in items:
        data=item.get('data',{})
        if data.get('itemType')=='note' and data.get('parentItem'):
            notes.setdefault(data['parentItem'],[]).append({'key':item.get('key'), 'note':data.get('note','')})
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
            parsed={};note_conflict=False
            for note in attached:
                for field,value in parse_note(note['note']).items():
                    if field in parsed and parsed[field]!=value:note_conflict=True
                    else:parsed[field]=value
            memberships=set(data.get('collections',[]))
            states={role for role,collection in mapping.items() if collection and collection in memberships}
            conflict=('included' in states and 'excluded' in states) or note_conflict
            state='conflict' if conflict else 'included' if 'included' in states else 'excluded' if 'excluded' in states else 'candidate'
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
            count+=1;conflicts+=int(conflict)
        # A successful full library read is authoritative for availability, but never deletes local history.
        for old in store.db.execute('SELECT id,item_key FROM papers WHERE library_id=?',(library,)).fetchall():
            if old['item_key'] not in seen:
                store.db.execute("UPDATE papers SET state='unavailable',verified=0,updated_at=? WHERE id=?",(utcnow(),old['id']))
        store.audit('zotero_read',library,{'papers':count,'conflicts':conflicts})
    duplicates=[dict(r) for r in store.db.execute("SELECT json_extract(data_json,'$.DOI') AS doi,COUNT(*) AS count FROM papers WHERE json_extract(data_json,'$.DOI')!='' GROUP BY lower(json_extract(data_json,'$.DOI')) HAVING COUNT(*)>1")]
    return {'count':count,'conflicts':conflicts,'duplicates':duplicates}
