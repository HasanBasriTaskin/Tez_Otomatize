"""ACM Digital Library: the records of a captured search, collected from its own result pages.

ACM's Basic edition (no institutional subscription) has no bulk citation export and no type filter.
After a Ctrl+M capture of an ACM search the extension offers "ACM kayıtlarını toplayalım mı?". On
approval it reads the search's result pages (50 records each, the largest page ACM Basic offers) and
sends the list here. This module

* keeps the types CEN401 K2 counts (research-article, short-paper) and records why the others were left,
* writes 01_HamExport/S0xx_ACM_liste.csv (every record read, with its decision) and S0xx_ACM.ris,
* completes each kept record's metadata from Crossref by DOI (falls back to the result list),
* hands the kept records to the Zotero writer (00_AramaKayitlari › S0xx_ACM).

The year range is ACM's own: the search is run with its date filter and the query line says so.
"""
import csv
import html
import io
import json
import logging
import re
import time
import unicodedata
import uuid
from datetime import datetime, timezone
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, build_opener

from .storage import ValidationError, json_text, utcnow

DATABASE = 'ACM Digital Library'
WANTED = ('research-article', 'short-paper')
TYPE_FILTER = 'Tür: ' + ', '.join(WANTED)
PAGE_SIZE = 50
MAX_RECORDS = 2000
EXPORT_DIR = '01_HamExport'
YEARS = re.compile(r'Yıl: (\d{4})–(\d{4})')
DOI = re.compile(r'^10\.\d{4,9}/\S{1,300}$')
USER_AGENT = 'LiteraturKayit/0.5.2 (+https://github.com/HasanBasriTaskin/Tez_Otomatize)'

ACM_SCHEMA = '''
CREATE TABLE IF NOT EXISTS acm_collections(
 id TEXT PRIMARY KEY, run_id TEXT UNIQUE NOT NULL REFERENCES search_runs(id), context_json TEXT NOT NULL,
 state TEXT NOT NULL, message TEXT NOT NULL DEFAULT '', total INTEGER, read_count INTEGER, kept INTEGER,
 left_out INTEGER, duplicates INTEGER, crossref INTEGER, zotero_imported INTEGER, zotero_failed INTEGER,
 list_path TEXT, ris_path TEXT, created_at TEXT NOT NULL, updated_at TEXT NOT NULL);
'''
BUSY = ('collecting', 'processing')
STALE_SECONDS = 180  # a collection with no progress for this long (tab closed, Chrome restarted) may be restarted


def _stale(row):
    if row['state'] != 'collecting':
        return False
    try:
        return (datetime.now(timezone.utc) - datetime.fromisoformat(row['updated_at'])).total_seconds() > STALE_SECONDS
    except ValueError:
        return True


def canonical(query):
    return re.sub(r'\s+', '', str(query).replace('‘', '"').replace('’', '"').replace("'", '"'))


def _filters(run):
    try:
        value = json.loads(run.get('filters_json') or '[]')
    except ValueError:
        return []
    return value if isinstance(value, list) else []


def years_label(run):
    return next((f for f in _filters(run) if isinstance(f, str) and f.startswith('Yıl: ')), None)


def propose(store, run, context):
    """Offer collection for a complete ACM capture with an exact, non-zero result count."""
    if run.get('database_name') != DATABASE or run.get('count_qualifier') != 'exact' or not run.get('count_value'):
        return None
    now = utcnow()
    with store.lock, store.db:
        row = store.db.execute('SELECT * FROM acm_collections WHERE run_id=?', (run['id'],)).fetchone()
        if row:
            if row['state'] in BUSY or row['state'] == 'done':
                return None
            store.db.execute("UPDATE acm_collections SET context_json=?,state='offered',message='',updated_at=? WHERE id=?",
                             (json_text(context), now, row['id']))
            return {'id': row['id']}
        identity = str(uuid.uuid4())
        store.db.execute("INSERT INTO acm_collections(id,run_id,context_json,state,created_at,updated_at) VALUES(?,?,?,?,?,?)",
                         (identity, run['id'], json_text(context), 'offered', now, now))
        store.audit('acm_offered', run['id'], {'collection': identity})
        return {'id': identity}


def for_run(store, run_id):
    row = store.db.execute('SELECT id FROM acm_collections WHERE run_id=?', (run_id,)).fetchone()
    return row[0] if row else None


def _row(store, identity):
    row = store.db.execute('SELECT * FROM acm_collections WHERE id=?', (str(identity),)).fetchone()
    if not row:
        raise ValidationError('ACM toplama kaydı bulunamadı.')
    return dict(row)


def get(store, identity):
    with store.lock:
        row = _row(store, identity)
        run = store.get_run(row['run_id'])
    count = run['count_value']
    return {'id': row['id'], 'state': row['state'], 'message': row['message'], 'display_id': run['display_id'],
            'query': run['query_raw'], 'count': count, 'fields': run['fields'], 'years': years_label(run),
            'types': TYPE_FILTER, 'pages': -(-count // PAGE_SIZE), 'can_collect': row['state'] in ('offered', 'failed') or _stale(row),
            'kept': row['kept'], 'left_out': row['left_out'], 'read_count': row['read_count'],
            'zotero_imported': row['zotero_imported'], 'list_path': row['list_path'], 'ris_path': row['ris_path']}


def plan(store, identity, profile):
    with store.lock, store.db:
        row = _row(store, identity)
        context = json.loads(row['context_json'])
        if context.get('profile') != profile:
            raise ValidationError('Bu ACM araması başka bir Chrome oturumunda kaydedildi. Arama sayfasında yeniden Ctrl+M yapın.')
        if row['state'] not in ('offered', 'failed') and not _stale(row):
            raise ValidationError({'collecting': 'Bu arama şu anda toplanıyor.', 'processing': 'Kayıtlar işleniyor; bitmesini bekleyin.',
                                   'done': 'Bu arama daha önce toplandı.'}.get(row['state'], 'Bu arama toplanamaz.'))
        run = store.get_run(row['run_id'])
        if run['count_value'] > MAX_RECORDS:
            raise ValidationError(f"ACM {run['count_value']} sonuç gösteriyor; tek seferde en fazla {MAX_RECORDS} kayıt toplanır. Aramayı daraltın.")
        store.db.execute("UPDATE acm_collections SET state='collecting',message='ACM sonuç sayfaları okunuyor…',updated_at=? WHERE id=?",
                         (utcnow(), row['id']))
        store.audit('acm_collect_started', run['id'], {'collection': row['id']})
    return {'id': row['id'], 'display_id': run['display_id'], 'query': run['query_raw'], 'count': run['count_value'],
            'context': context}


def progress(store, identity, text):
    """The extension's progress line while pages are read; also proves the collection is alive."""
    with store.lock, store.db:
        row = _row(store, identity)
        if row['state'] != 'collecting':
            return {}
        store.db.execute('UPDATE acm_collections SET message=?,updated_at=? WHERE id=?', (_text(str(text), 300), utcnow(), row['id']))
    return {}


def fail(store, identity, error, profile=None):
    with store.lock, store.db:
        row = _row(store, identity)
        if row['state'] not in BUSY:
            return get(store, identity)
        if profile is not None and json.loads(row['context_json']).get('profile') != profile:
            raise ValidationError('Chrome oturumu eşleşmedi.')
        text = str(error or 'ACM kayıtları toplanamadı.')[:1000]
        store.db.execute("UPDATE acm_collections SET state='failed',message=?,updated_at=? WHERE id=?", (text, utcnow(), row['id']))
        store.audit('acm_collect_failed', row['run_id'], {'error': text})
    return get(store, identity)


def _text(value, limit=2000):
    if not isinstance(value, str):
        raise ValidationError('ACM kaydı geçersiz.')
    return re.sub(r'\s+', ' ', value).strip()[:limit]


def _item(raw):
    if not isinstance(raw, dict):
        raise ValidationError('ACM kaydı geçersiz.')
    doi = _text(raw.get('doi', ''), 320)
    if not DOI.fullmatch(doi):
        raise ValidationError('ACM kaydında geçerli DOI yok: ' + doi[:80])
    authors = raw.get('authors', [])
    if not isinstance(authors, list) or len(authors) > 500:
        raise ValidationError('ACM kaydının yazar listesi geçersiz.')
    page, position = raw.get('page', 0), raw.get('position', 0)
    if type(page) is not int or type(position) is not int:
        raise ValidationError('ACM kaydının sayfa bilgisi geçersiz.')
    return {'doi': doi, 'type': _text(raw.get('type', ''), 80).casefold(), 'published': _text(raw.get('published', ''), 80),
            'title': _text(raw.get('title', ''), 2000), 'authors': [_text(a, 300) for a in authors if isinstance(a, str) and a.strip()],
            'venue': _text(raw.get('venue', ''), 1000), 'pages': _text(raw.get('pages', ''), 80), 'page': page, 'position': position,
            'abstract': _text(raw.get('abstract', '') or '', 20000), 'access': _text(raw.get('access', '') or '', 80),
            'abstract_status': _text(raw.get('abstract_status', '') or '', 200)}


def classify(items):
    """Every record read, in list order, with its decision. Same DOI twice: the first one counts."""
    seen, out = set(), []
    for item in items:
        key = item['doi'].casefold()
        if key in seen:
            decision, reason = 'Alınmadı', 'Aynı DOI daha önceki bir sonuç sayfasında'
        elif item['type'] in WANTED:
            decision, reason = 'Alındı', ''
        else:
            decision, reason = 'Alınmadı', f"Tür: {item['type'] or 'belirtilmemiş'} (kılavuz K2: yalnız hakemli makale ve bildiri)"
        seen.add(key)
        out.append(dict(item, decision=decision, reason=reason))
    return out


def _free(store, name, own):
    candidate, n = name, 1
    stem, suffix = name.rsplit('.', 1)
    while store.path(f'{EXPORT_DIR}/{candidate}').exists() and f'{EXPORT_DIR}/{candidate}' != own:
        n += 1
        candidate = f'{stem}_{n}.{suffix}'
    return f'{EXPORT_DIR}/{candidate}'


LIST_HEADERS = ['Sıra', 'Sonuç sayfası', 'DOI', 'ACM türü', 'Yayın tarihi', 'Başlık', 'Yazarlar', 'Yayın yeri',
                'Karar', 'Neden', 'Künye kaynağı', 'Özet kaynağı', 'Erişim (ACM)']


def list_csv(rows, sources=None):
    sources = sources or {}
    buffer = io.StringIO(newline='')
    writer = csv.writer(buffer, delimiter=';', lineterminator='\r\n')
    writer.writerow(LIST_HEADERS)
    for index, row in enumerate(rows, 1):
        writer.writerow([index, row['page'], row['doi'], row['type'], row['published'], row['title'], '; '.join(row['authors']),
                         row['venue'], row['decision'], row['reason'],
                         *(sources.get(row['doi'].casefold(), ('', '')) if row['decision'] == 'Alındı' else ('', '')),
                         row.get('access', '') if row['decision'] == 'Alındı' else ''])
    return ('﻿' + buffer.getvalue()).encode('utf-8')


def receive(store, identity, collection, profile):
    """Validate what the extension read; write the decision list. Returns the records to complete."""
    if not isinstance(collection, dict) or not isinstance(collection.get('items'), list):
        raise ValidationError('ACM kayıt listesi eksik.')
    with store.lock:
        row = _row(store, identity)
        if row['state'] != 'collecting':
            raise ValidationError('Bu ACM toplaması beklenen durumda değil; pencereyi kapatıp yeniden açın.')
        if json.loads(row['context_json']).get('profile') != profile:
            raise ValidationError('Chrome oturumu eşleşmedi.')
        run = store.get_run(row['run_id'])
    raw = collection['items']
    if len(raw) > MAX_RECORDS:
        raise ValidationError('ACM kayıt listesi çok uzun.')
    if canonical(collection.get('query', '')) != canonical(run['query_raw']) or collection.get('total') != run['count_value']:
        return None, fail(store, identity, 'Okunan sayfalar kayıttaki aramayla eşleşmedi; yeniden Ctrl+M yapın.')
    items = [_item(x) for x in raw]
    if len(items) != run['count_value']:
        return None, fail(store, identity, f"ACM {run['count_value']} sonuç gösterdi, {len(items)} kayıt okundu. Yeniden deneyin.")
    rows = classify(items)
    kept = [r for r in rows if r['decision'] == 'Alındı']
    duplicates = sum(1 for r in rows if r['reason'].startswith('Aynı DOI'))
    code = run['display_id']
    list_path = _free(store, f'{code}_ACM_liste.csv', row['list_path'])
    store._atomic_write(list_path, list_csv(rows), replace=True)
    with store.lock, store.db:
        store.db.execute("""UPDATE acm_collections SET state='processing',message=?,total=?,read_count=?,kept=?,left_out=?,
            duplicates=?,list_path=?,updated_at=? WHERE id=?""",
            (f'{len(items)} kayıt okundu; {len(kept)} kayıt alındı. Künyeler tamamlanıyor…', run['count_value'], len(items),
             len(kept), len(items) - len(kept), duplicates, list_path, utcnow(), row['id']))
        store.audit('acm_records_received', run['id'], {'read': len(items), 'kept': len(kept), 'duplicates': duplicates,
                                                        'pages': collection.get('pages')})
    return {'id': row['id'], 'run_id': run['id'], 'display_id': code, 'rows': rows, 'kept': kept}, get(store, identity)


# ---------- metadata ----------

def _opener():
    return build_opener()


def crossref(doi, opener=None, sleep=time.sleep):
    """Crossref's public record for a DOI, or None (not registered there, e.g. ACM's 10.5555 prefix)."""
    opener = opener or _opener()
    request = Request('https://api.crossref.org/works/' + quote(doi, safe='/:;()._-'),
                      headers={'User-Agent': USER_AGENT, 'Accept': 'application/json'})
    for attempt in range(3):
        try:
            with opener.open(request, timeout=20) as response:
                data = json.loads(response.read(4 * 1024 * 1024))
            message = data.get('message') if isinstance(data, dict) else None
            return message if isinstance(message, dict) else None
        except HTTPError as error:
            if error.code == 404:
                return None
            if error.code not in (429, 500, 502, 503, 504):
                return None
        except (URLError, TimeoutError, ConnectionError, ValueError, OSError):
            pass
        sleep(2 * (attempt + 1))
    return None


def plain(value):
    """Crossref text as Zotero stores it: no JATS/HTML markup (e.g. <scp>…</scp>), entities decoded,
    one space between words, Unicode NFC. Zotero normalizes field values, so anything else would
    differ from what it hands back."""
    text = html.unescape(re.sub(r'<[^>]+>', ' ', str(value or '')))
    return unicodedata.normalize('NFC', re.sub(r'\s+', ' ', text).strip())


def _first(value):
    if isinstance(value, list):
        return next((plain(v) for v in value if plain(v)), '')
    return plain(value)


def _date_parts(message):
    for key in ('published-print', 'published-online', 'issued', 'published'):
        parts = (message.get(key) or {}).get('date-parts') if isinstance(message.get(key), dict) else None
        if parts and parts[0] and parts[0][0]:
            return [int(p) for p in parts[0][:3] if isinstance(p, int) or str(p).isdigit()]
    return []


def _page_date(text):
    for fmt in ('%d %B %Y', '%B %Y', '%Y'):
        try:
            value = datetime.strptime(text.strip(), fmt)
            return [value.year, value.month, value.day][:{'%d %B %Y': 3, '%B %Y': 2, '%Y': 1}[fmt]]
        except ValueError:
            continue
    return []


def _abstract(value):
    return re.sub(r'^Abstract\s*[:.]?\s*', '', plain(value), flags=re.I)


def _person(name):
    name = name.strip()
    if ',' in name:
        last, _, first = name.partition(',')
        return first.strip(), last.strip()
    first, _, last = name.rpartition(' ')
    return first.strip(), (last or name).strip()


def complete(item, message):
    """Merge Crossref (when found) with what the result list showed. The list is the fallback, never empty."""
    message = message or {}
    kind_cr = message.get('type', '')
    venue = _first(message.get('container-title')) or item['venue']
    if kind_cr == 'journal-article':
        kind = 'journalArticle'
    elif kind_cr in ('proceedings-article', 'book-chapter') or re.search(r'proceedings|conference|companion|symposium|workshop', venue, re.I):
        kind = 'conferencePaper'
    else:
        kind = 'journalArticle'
    creators = []
    for person in message.get('author') or []:
        if isinstance(person, dict) and (person.get('family') or person.get('name')):
            creators.append((plain(person.get('given', '')), plain(person.get('family') or person.get('name'))))
    if not creators:
        creators = [_person(plain(a)) for a in item['authors']]
    date = _date_parts(message) or _page_date(item['published'])
    pages = plain(message.get('page') or item['pages']).replace('–', '-')
    event = message.get('event') if isinstance(message.get('event'), dict) else {}
    return {'doi': item['doi'], 'acm_type': item['type'], 'kind': kind,
            'title': _first(message.get('title')) or plain(item['title']), 'creators': creators,
            'date': '-'.join(f'{p:02d}' if i else str(p) for i, p in enumerate(date)), 'year': str(date[0]) if date else '',
            'venue': plain(venue), 'conference': plain(event.get('name', '')), 'place': plain(event.get('location', '')),
            'pages': pages, 'volume': plain(message.get('volume', '')), 'issue': plain(message.get('issue', '')),
            'publisher': plain(message.get('publisher', '')) or 'Association for Computing Machinery',
            'isbn': _first(message.get('ISBN')), 'issn': _first(message.get('ISSN')),
            'abstract': plain(item.get('abstract', '')) or _abstract(message.get('abstract')), 'url': 'https://dl.acm.org/doi/' + item['doi'],
            'source': 'Crossref' if message else 'ACM sonuç listesi', 'access': item.get('access', ''),
            'abstract_source': 'ACM makale sayfası' if plain(item.get('abstract', '')) else 'Crossref' if _abstract(message.get('abstract'))
            else 'yok' + (f" ({item['abstract_status']})" if item.get('abstract_status') else '')}


def _clean(value):
    return re.sub(r'[\r\n]+', ' ', str(value)).strip()


def ris_record(r):
    start, _, end = r['pages'].partition('-')
    lines = [('TY', 'CONF' if r['kind'] == 'conferencePaper' else 'JOUR'), ('TI', r['title'])]
    lines += [('AU', f'{last}, {first}' if first else last) for first, last in r['creators']]
    lines += [('PY', r['year']), ('DA', r['date'].replace('-', '/')), ('T2', r['venue'])]
    if r['kind'] == 'journalArticle':
        lines.append(('JO', r['venue']))
    if r['conference']:
        lines.append(('C3', r['conference']))
    lines += [('SP', start.strip()), ('EP', end.strip()), ('VL', r['volume']), ('IS', r['issue']),
              ('SN', r['isbn'] or r['issn']), ('PB', r['publisher']), ('CY', r['place']), ('DO', r['doi']),
              ('UR', r['url']), ('AB', r['abstract']), ('M3', r['acm_type']), ('DB', DATABASE)]
    return ''.join(f'{tag}  - {_clean(value)}\n' for tag, value in lines if _clean(value)) + 'ER  - \n'


def ris_text(records):
    return '\n'.join(ris_record(r) for r in records) + '\n'


def zotero_item(r):
    item = {'itemType': r['kind'], 'title': r['title'],
            'creators': [{'creatorType': 'author', 'firstName': first, 'lastName': last} if first
                         else {'creatorType': 'author', 'name': last} for first, last in r['creators']],
            'abstractNote': r['abstract'], 'date': r['date'], 'pages': r['pages'], 'DOI': r['doi'], 'url': r['url'],
            'volume': r['volume'], 'publisher': r['publisher'] if r['kind'] == 'conferencePaper' else '',
            'libraryCatalog': DATABASE, 'extra': 'ACM türü: ' + r['acm_type'] + (f"\nACM erişim: {r['access']}" if r.get('access') else ''),
            'tags': [], 'collections': [], 'relations': {}}
    if r['kind'] == 'conferencePaper':
        item.update(proceedingsTitle=r['venue'], conferenceName=r['conference'], place=r['place'], ISBN=r['isbn'])
    else:
        item.update(publicationTitle=r['venue'], issue=r['issue'], ISSN=r['issn'])
    return {k: v for k, v in item.items() if v not in ('', None) or k in ('tags', 'collections', 'relations', 'creators')}


def process(store, job, writer, fetch=crossref, pause=0.25, sleep=time.sleep):
    """Complete metadata, write S0xx_ACM.ris, add the records to Zotero. Returns the final state."""
    identity, records, sources = job['id'], [], {}
    try:
        for item in job['kept']:
            message = fetch(item['doi'])
            record = complete(item, message)
            records.append(record)
            sources[item['doi'].casefold()] = (record['source'], record['abstract_source'])
            sleep(pause)
        with store.lock:
            row = _row(store, identity)
        store._atomic_write(row['list_path'], list_csv(job['rows'], sources), replace=True)
        ris_path = _free(store, f"{job['display_id']}_ACM.ris", row['ris_path'])
        store._atomic_write(ris_path, ris_text(records).encode('utf-8'), replace=True)
        files = '; '.join(p.rsplit('/', 1)[-1] for p in (ris_path, row['list_path']))
        store.update_run(job['run_id'], {'export_files': files})
        crossref_count = sum(1 for r in records if r['source'] == 'Crossref')
        with store.lock, store.db:
            store.db.execute('UPDATE acm_collections SET ris_path=?,crossref=?,updated_at=? WHERE id=?',
                             (ris_path, crossref_count, utcnow(), identity))
        imported, failed, note = 0, 0, ''
        if records:
            try:
                result = writer.import_acm([{'doi': r['doi'], 'item': zotero_item(r)} for r in records], job['run_id'])
                imported, failed = result['imported'] + result['reused'], result['failed']
                if failed:
                    note = f" Zotero'ya {failed} kayıt yazılamadı: {result['failures'][0]['error']}"
            except Exception as error:
                failed = len(records)
                note = f" Zotero'ya yazılamadı: {error}. {ris_path.rsplit('/', 1)[-1]} dosyasını Zotero'ya elle aktarabilir ya da yeniden toplayabilirsiniz."
        left = len(job['rows']) - len(records)
        message = (f"{job['display_id']}: {len(job['rows'])} kayıt okundu, {len(records)} kayıt alındı"
                   f"{f', {left} kayıt tür dışında kaldı' if left else ''}. "
                   f"Künye: {crossref_count} Crossref, {len(records) - crossref_count} ACM listesi. "
                   f"Özet: {sum(1 for r in records if r['abstract_source'] == 'ACM makale sayfası')} ACM sayfası, "
                   f"{sum(1 for r in records if r['abstract_source'] == 'Crossref')} Crossref, "
                   f"{sum(1 for r in records if r['abstract_source'].startswith('yok'))} yok. "
                   f"Zotero: {imported} kayıt {job['display_id']}_ACM koleksiyonunda.{note}")
        state = 'failed' if failed else 'done'
        with store.lock, store.db:
            store.db.execute('UPDATE acm_collections SET state=?,message=?,zotero_imported=?,zotero_failed=?,updated_at=? WHERE id=?',
                             (state, message, imported, failed, utcnow(), identity))
            store.audit('acm_collect_finished', job['run_id'], {'state': state, 'kept': len(records), 'zotero': imported,
                                                               'failed': failed, 'crossref': crossref_count})
        return state, message
    except Exception as error:
        logging.exception('ACM records could not be processed.')
        fail(store, identity, f'Kayıtlar işlenemedi: {error}')
        return 'failed', f"{job['display_id']}: kayıtlar işlenemedi: {error}"
