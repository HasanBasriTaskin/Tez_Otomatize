"""Editable per-project search packages, validated before browser actions."""
import json
import re
import uuid

from .storage import ValidationError, digest, json_text

INITIAL = 'TITLE-ABS-KEY(("retrieval augmented generation" OR "retrieval-augmented generation") AND ("question answering" OR Turkish OR institutional OR regulation))'
TOPICS = [
    ('Q01', 'Türkçe ve çok dillilik', '("retrieval augmented generation" OR "retrieval-augmented generation") AND (Turkish OR multilingual OR "low resource")'),
    ('Q02', 'Kurumsal belgeler ve mevzuat', '("retrieval augmented generation" OR "question answering") AND (regulation OR legal OR institutional OR university)'),
    ('Q03', 'Parçalama ve erişim', '("retrieval augmented generation" OR "question answering") AND (chunking OR "dense retrieval" OR "hybrid retrieval" OR reranking)'),
    ('Q04', 'Atıf ve kanıta bağlılık', '("retrieval augmented generation" OR "large language model") AND (citation OR attribution OR faithfulness OR groundedness)'),
    ('Q05', 'Cevaplanamazlık', '("retrieval augmented generation" OR "question answering") AND (unanswerable OR abstention OR "negative rejection" OR "insufficient evidence")'),
    ('Q06', 'Model ve maliyet', '("retrieval augmented generation") AND (evaluation OR benchmark OR latency OR cost OR "long context")'),
]

RELATIVE_PATH = '03_Calisma/sorgu-paketi.json'
MAX_BYTES = 128 * 1024


def default_package():
    return {'schema':1,'name':'OEC-1017 — RAG literatür taraması','initial':INITIAL,
            'topics':[dict(code=code,label=label,query=query) for code,label,query in TOPICS]}


def _text(value, label, limit):
    if not isinstance(value,str) or not value.strip() or len(value)>limit or any(ord(c)<32 and c not in '\r\n\t' for c in value):
        raise ValidationError(f'{label}: boş olmayan, en fazla {limit} karakterlik metin gerekli.')
    return value.strip()


def _query(value, label, initial=False):
    value=_text(value,label,8192 if initial else 4096)
    quoted=False;depth=0;unquoted=[]
    for char in value:
        if char=='"':quoted=not quoted
        elif not quoted:
            unquoted.append(char)
            if char=='(':depth+=1
            elif char==')':depth-=1
            if depth<0:raise ValidationError(label+': parantezler eşleşmiyor.')
    if quoted or depth:raise ValidationError(label+': çift tırnak veya parantezler eşleşmiyor.')
    outside=''.join(unquoted)
    if re.search(r'\b(?:PUBYEAR|DOCTYPE)\b',outside,re.I):
        raise ValidationError(label+': yıl ve yayın türü eklerini kaldırın; bunları uygulama ekler.')
    if initial:
        if not re.fullmatch(r'TITLE-ABS-KEY\s*\(.+\)',value,re.I|re.S):
            raise ValidationError(label+': TITLE-ABS-KEY(...) biçiminde tam başlangıç sorgusu gerekli.')
    elif re.search(r'\bTITLE-ABS-KEY\s*\(',outside,re.I):
        raise ValidationError(label+': yalnız kavram bloklarını yazın; TITLE-ABS-KEY(...) otomatik eklenir.')
    return value


def validate_package(value):
    if not isinstance(value,dict) or set(value)!={'schema','name','initial','topics'} or type(value['schema']) is not int or value['schema']!=1:
        raise ValidationError('Sorgu paketi biçimi geçersiz; schema, name, initial ve topics alanları gerekli (schema: 1).')
    if not isinstance(value['topics'],list) or not 1<=len(value['topics'])<=20:
        raise ValidationError('Sorgu paketinde 1–20 konu bulunmalı.')
    result={'schema':1,'name':_text(value['name'],'Paket adı',120),
            'initial':_query(value['initial'],'Başlangıç sorgusu',True),'topics':[]}
    seen=set()
    for topic in value['topics']:
        if not isinstance(topic,dict) or set(topic)!={'code','label','query'}:
            raise ValidationError('Her konuda code, label ve query alanları gerekli.')
        code=topic['code']
        if not isinstance(code,str) or not re.fullmatch(r'Q[A-Z0-9_-]{1,19}',code) or code in seen:
            raise ValidationError('Konu kimlikleri Q ile başlayan benzersiz kısa kimlikler olmalı (Q01 gibi).')
        seen.add(code)
        result['topics'].append({'code':code,'label':_text(topic['label'],code+' konu adı',120),
                                 'query':_query(topic['query'],code+' sorgusu')})
    if len(json_text(result).encode('utf-8'))>MAX_BYTES:
        raise ValidationError('Sorgu paketi 128 KB sınırını aşıyor.')
    return result


class QueryPackage:
    def __init__(self,store):self.store=store

    def load(self):
        with self.store.lock:
            path=self.store.path(RELATIVE_PATH)
            if not path.exists():
                self.store._atomic_write(RELATIVE_PATH,(json.dumps(default_package(),ensure_ascii=False,indent=2)+'\n').encode('utf-8'))
            with path.open('rb') as stream:raw=stream.read(MAX_BYTES+1)
            if len(raw)>MAX_BYTES:raise ValidationError('Sorgu paketi 128 KB sınırını aşıyor: '+str(path))
            try:package=validate_package(json.loads(raw.decode('utf-8-sig')))
            except (UnicodeError,json.JSONDecodeError) as error:
                raise ValidationError('Sorgu paketi geçerli UTF-8 JSON değil. Dosya korunuyor: '+str(path)) from error
            return {'package':package,'revision':digest(raw),'path':str(path)}

    def save(self,package,revision):
        package=validate_package(package)
        with self.store.lock:
            if self.store.db.execute("SELECT 1 FROM workflow_sessions WHERE state NOT IN ('completed','stopped')").fetchone():
                raise ValidationError('Önce mevcut taramayı tamamlayın veya Durdur seçin; devam eden taramanın sorguları korunur.')
            current=self.load()
            if revision!=current['revision']:
                raise ValidationError('Sorgu dosyası değişti. Dosyadan yeniden yükleyip değişiklikleri karşılaştırın.')
            raw=self.store.path(RELATIVE_PATH).read_bytes()
            if digest(raw)!=revision:raise ValidationError('Sorgu dosyası kaydetme sırasında değişti; yeniden yükleyin.')
            backup='Yedekler/sorgu-paketi_'+uuid.uuid4().hex+'.json'
            self.store._atomic_write(backup,raw)
            self.store._atomic_write(RELATIVE_PATH,(json.dumps(package,ensure_ascii=False,indent=2)+'\n').encode('utf-8'),replace=True)
            with self.store.db:self.store.audit('query_package_saved',revision,{'name':package['name'],'backup':backup})
            return self.load()
