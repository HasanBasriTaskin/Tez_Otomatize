"""Recoverable, metadata-only writes to the explicitly configured local TEZ library."""
import json
import re
import secrets
import uuid
from dataclasses import dataclass
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import HTTPRedirectHandler, ProxyHandler, Request, build_opener

from .ris import EID, normalize_doi, scopus_eids
from .storage import ValidationError, json_text, utcnow
from .zotero import load_api_key, save_api_key


LIBRARY = 'groups/6718452'
CANDIDATE = 'BX38VWI6'
SEARCH_ROOT = 'U8THQFWA'
KEY_PATTERN = r'[23456789ABCDEFGHIJKLMNPQRSTUVWXYZ]{8}'
KEY_ALPHABET = '23456789ABCDEFGHIJKLMNPQRSTUVWXYZ'

WRITER_SCHEMA = '''
CREATE TABLE IF NOT EXISTS zotero_import_objects(
 server_id TEXT NOT NULL, library_id TEXT NOT NULL, kind TEXT NOT NULL,
 source_identity TEXT NOT NULL, object_key TEXT NOT NULL, body_json TEXT NOT NULL,
 state TEXT NOT NULL, version INTEGER, error TEXT, created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
 PRIMARY KEY(server_id,library_id,kind,source_identity),
 UNIQUE(server_id,library_id,kind,object_key));
CREATE TABLE IF NOT EXISTS zotero_source_refs(
 server_id TEXT NOT NULL, library_id TEXT NOT NULL, eid TEXT NOT NULL,
 search_id TEXT NOT NULL REFERENCES search_runs(id), session_id TEXT NOT NULL,
 item_key TEXT NOT NULL, created_at TEXT NOT NULL,
 PRIMARY KEY(server_id,library_id,eid,search_id));
CREATE TABLE IF NOT EXISTS zotero_duplicate_suspects(
 server_id TEXT NOT NULL, library_id TEXT NOT NULL, eid TEXT NOT NULL,
 item_key TEXT NOT NULL, reason TEXT NOT NULL, created_at TEXT NOT NULL,
 PRIMARY KEY(server_id,library_id,eid,item_key,reason));
CREATE TABLE IF NOT EXISTS zotero_writer_instances(
 server_id TEXT PRIMARY KEY, last_seen TEXT NOT NULL);
'''


@dataclass
class HTTPResponse:
    status: int
    body: object
    headers: dict


class ZoteroWriteError(ValidationError):
    def __init__(self, message, status=0):
        super().__init__(message)
        self.status = status


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise ZoteroWriteError('Zotero yerel API yönlendirmesi reddedildi.', code)


class LocalZoteroClient:
    def __init__(self):
        self.opener = build_opener(ProxyHandler({}), NoRedirect())

    def request(self, method, path, body=None, headers=None):
        # No configurable URL, remote host, redirect, file, attachment, or deletion endpoint.
        allowed = (path == '/' and method == 'GET') or (path == '/local/authorize' and method == 'POST')
        resource = re.fullmatch(r'/groups/6718452/(items|collections)(?:/(' + KEY_PATTERN + r'))?(?:\?[A-Za-z0-9%=&,_-]*)?', path)
        allowed |= bool(resource and (method == 'GET' or method == 'POST' and not resource[2]
                                      or method == 'PATCH' and resource[1] == 'items' and resource[2]))
        if not allowed:
            raise ValidationError('Yetkilendirilmemiş Zotero yolu veya işlemi.')
        request_headers = {'Zotero-API-Version': '3', 'User-Agent': 'LiteraturKayit/0.5.0', **(headers or {})}
        payload = None
        if body is not None:
            payload = json_text(body).encode('utf-8')
            request_headers['Content-Type'] = 'application/json'
        req = Request('http://127.0.0.1:23119/api' + path, data=payload, headers=request_headers, method=method)
        try:
            response = self.opener.open(req, timeout=120 if path == '/local/authorize' else 30)
        except HTTPError as error:
            response = error
        with response:
            raw = response.read(16 * 1024 * 1024 + 1)
            if len(raw) > 16 * 1024 * 1024:
                raise ZoteroWriteError('Zotero yanıtı boyut sınırını aşıyor.')
            try:
                data = json.loads(raw) if raw else None
            except (ValueError, UnicodeError):
                data = None
                if 200 <= response.status < 300 and raw and path != '/':
                    raise ZoteroWriteError('Zotero geçerli JSON döndürmedi.') from None
            return HTTPResponse(response.status, data, dict(response.headers))


def _header(response, name):
    return next((str(v) for k, v in response.headers.items() if k.casefold() == name.casefold()), '')


def _data(obj):
    if not isinstance(obj, dict) or not isinstance(obj.get('data'), dict):
        raise ZoteroWriteError('Zotero nesnesi geçersiz.')
    return obj['data']


class ZoteroWriter:
    def __init__(self, store, client=None):
        self.store = store
        self.client = client or LocalZoteroClient()
        self.server_id = ''
        self.key = ''
        self.remember = False

    def _scope(self):
        settings = self.store.settings()
        mapping = settings.get('collection_mapping', {})
        if settings.get('zotero_mode', 'local') != 'local' or settings.get('library') != LIBRARY:
            raise ValidationError('Otomatik aktarım yalnız yerel Zotero TEZ grubu (6718452) için yetkilidir.')
        if mapping.get('candidate', CANDIDATE) != CANDIDATE:
            raise ValidationError('Zotero aday koleksiyonu beklenen TEZ hedefiyle eşleşmiyor.')

    def _credential_name(self):
        # Server IDs identify databases, and remembered permissions must never cross that boundary.
        return 'local-write/' + self.server_id

    def _request(self, method, path, body=None, *, headers=None, check_cancel=lambda: None):
        check_cancel()
        supplied = {'Zotero-Server-ID': self.server_id, **(headers or {})}
        writing = method != 'GET' and path != '/local/authorize'
        if writing:
            self._scope()
            if not self.key:
                raise ZoteroWriteError('Zotero yazma izni gerekiyor; bağlantı bölümünden yeniden yetkilendirin.', 401)
            supplied['Zotero-API-Key'] = self.key
        try:
            response = self.client.request(method, path, body=body, headers=supplied)
        except (URLError, TimeoutError, ConnectionError) as error:
            raise ZoteroWriteError('Zotero yanıtı alınamadı; aynı kayıt anahtarıyla yeniden kontrol edilecek.') from error
        finally:
            if writing and not self.remember:
                self.key = ''
        server_id = _header(response, 'Zotero-Server-ID')
        if server_id != self.server_id:
            self.key, self.remember = '', False
            raise ZoteroWriteError('Zotero veritabanı değişti; bağlantıyı yeniden doğrulayın.', 412)
        if response.status in (401, 403):
            if writing:
                if self.remember:
                    save_api_key('', self._credential_name())
                self.key, self.remember = '', False
            raise ZoteroWriteError('Zotero yazma izni reddedildi veya süresi doldu; yeniden yetkilendirin.', response.status)
        return response

    def _get(self, path, check_cancel=lambda: None):
        response = self._request('GET', path, check_cancel=check_cancel)
        if response.status == 404:
            return None
        if response.status != 200:
            raise ZoteroWriteError(f'Zotero okuma isteği başarısız (HTTP {response.status}).', response.status)
        return response.body

    def preflight(self, authorize=False):
        self._scope()
        try:
            response = self.client.request('GET', '/', headers={'Zotero-API-Version': '3'})
        except (URLError, TimeoutError, ConnectionError):
            return dict(ready=False, authorized=False, requires_authorization=False,
                        message='Zotero açık ve yerel API erişimi etkin olmalı.', library=LIBRARY)
        server_id = _header(response, 'Zotero-Server-ID')
        if response.status != 200 or not re.fullmatch(r'[A-Za-z0-9_-]{1,200}', server_id):
            return dict(ready=False, authorized=False, requires_authorization=False,
                        message='Yerel yazma API için Zotero 10 veya üstü gerekiyor.', library=LIBRARY)
        if self.server_id != server_id:
            self.server_id, self.key, self.remember = server_id, '', False
            self.key = load_api_key(self._credential_name())
            self.remember = bool(self.key)
        with self.store.lock, self.store.db:
            self.store.db.execute('INSERT INTO zotero_writer_instances VALUES(?,?) ON CONFLICT(server_id) DO UPDATE SET last_seen=excluded.last_seen',
                                  (server_id, utcnow()))
        for key, name in ((CANDIDATE, '01_Aday'), (SEARCH_ROOT, '00_AramaKayitlari')):
            obj = self._get(f'/{LIBRARY}/collections/{key}')
            if not obj or _data(obj).get('name') != name:
                raise ValidationError('Beklenen TEZ koleksiyonu bulunamadı: ' + name)
        message = ''
        if authorize and not self.key:
            try:
                response = self._request('POST', '/local/authorize', {'appName': 'Literatür Kayıt Asistanı'})
                if response.status != 200 or not isinstance(response.body, dict):
                    raise ZoteroWriteError(f'Zotero izin isteği başarısız (HTTP {response.status}).', response.status)
                key = response.body.get('key')
                if not isinstance(key, str) or not re.fullmatch(r'[A-Za-z0-9_-]{32}', key):
                    raise ZoteroWriteError('Zotero izin yanıtı geçersiz.')
                self.key, self.remember = key, response.body.get('remember') is True
                if self.remember:
                    save_api_key(self.key, self._credential_name())
                else:
                    message = 'Tek kullanımlık izin verildi. Sonraki yazmada yeniden izin gerekebilir.'
            except ZoteroWriteError as error:
                message = str(error)
        return dict(ready=bool(self.key), authorized=bool(self.key), requires_authorization=not bool(self.key),
                    server_id=server_id, library=LIBRARY, remember=self.remember,
                    message=message or ('Zotero hazır.' if self.key else 'Zotero yazma izni gerekiyor.'))

    def _all(self, kind, check_cancel):
        result, seen, start, version = [], set(), 0, None
        while True:
            response = self._request('GET', f'/{LIBRARY}/{kind}?' + urlencode({
                'format': 'json', 'limit': 100, 'start': start}),
                check_cancel=check_cancel)
            if response.status != 200 or not isinstance(response.body, list):
                raise ZoteroWriteError('Zotero kütüphanesi tam okunamadı.')
            current_version = _header(response, 'Last-Modified-Version')
            if version is not None and current_version != version:
                raise ZoteroWriteError('Zotero kütüphanesi okunurken değişti; aktarımı yeniden başlatın.')
            version = current_version
            for obj in response.body:
                key = obj.get('key') if isinstance(obj, dict) else None
                if not key or key in seen:
                    raise ZoteroWriteError('Zotero sayfalama sonucu yineleniyor veya bozuk.')
                seen.add(key)
                result.append(obj)
            if len(response.body) < 100:
                return result
            start += len(response.body)

    def _ledger(self, kind, identity):
        with self.store.lock:
            row = self.store.db.execute('''SELECT * FROM zotero_import_objects
                WHERE server_id=? AND library_id=? AND kind=? AND source_identity=?''',
                (self.server_id, LIBRARY, kind, identity)).fetchone()
        return dict(row) if row else None

    def _reserve(self, kind, identity, body, existing_key=None):
        with self.store.lock, self.store.db:
            row = self._ledger(kind, identity)
            if row:
                return row
            key = existing_key or ''.join(secrets.choice(KEY_ALPHABET) for _ in range(8))
            intended = dict(body, key=key, version=0)
            now = utcnow()
            self.store.db.execute('INSERT INTO zotero_import_objects VALUES(?,?,?,?,?,?,?,?,?,?,?)',
                (self.server_id, LIBRARY, kind, identity, key, json_text(intended),
                 'confirmed' if existing_key else 'planned', None, None, now, now))
            return self._ledger(kind, identity)

    def _state(self, row, state, error=None, version=None):
        with self.store.lock, self.store.db:
            self.store.db.execute('''UPDATE zotero_import_objects SET state=?,error=?,version=?,updated_at=?
                WHERE server_id=? AND library_id=? AND kind=? AND source_identity=?''',
                (state, error, version, utcnow(), row['server_id'], row['library_id'], row['kind'], row['source_identity']))

    def _reconcile(self, row, check_cancel):
        if row['state'] == 'conflict':
            raise ZoteroWriteError(row['error'] or 'Zotero kaydı çakışması elle incelenmeli.')
        obj = self._get(f"/{LIBRARY}/{row['kind']}/{row['object_key']}", check_cancel)
        if not obj:
            if row['state'] == 'confirmed':
                self._state(row, 'conflict', 'Daha önce doğrulanan Zotero kaydı artık bulunamıyor.')
                raise ZoteroWriteError('Önceden aktarılan Zotero kaydı silinmiş; otomatik yeniden oluşturulmadı.')
            return None
        data = _data(obj)
        intended = json.loads(row['body_json'])
        if row['state'] == 'confirmed' and row['kind'] == 'items' and row['source_identity'].startswith('acm:'):
            matches = normalize_doi(data.get('DOI', '')) == row['source_identity'].split(':', 2)[2]
        elif row['state'] == 'confirmed':
            matches = (row['source_identity'] in scopus_eids(data)) if row['kind'] == 'items' else all(
                data.get(f) == intended.get(f) for f in ('name', 'parentCollection'))
        else:
            matches = all(data.get(k) == v for k, v in intended.items() if k not in ('key', 'version'))
        if not matches:
            self._state(row, 'conflict', 'Aynı anahtardaki Zotero içeriği beklenen içerikle eşleşmiyor.')
            raise ZoteroWriteError('Zotero anahtar/içerik çakışması; mevcut kayıt değiştirilmedi.')
        self._state(row, 'confirmed', version=obj.get('version', data.get('version')))
        return obj

    def _create(self, rows, check_cancel):
        """Persist intent before sending; each batch outcome is durable independently."""
        outcomes = {}
        for offset in range(0, len(rows), 50):
            batch = rows[offset:offset + 50]
            check_cancel()
            for row in batch:
                self._state(row, 'sending')
            try:
                response = self._request('POST', f"/{LIBRARY}/{batch[0]['kind']}",
                    [json.loads(row['body_json']) for row in batch],
                    headers={'Zotero-Write-Token': uuid.uuid4().hex}, check_cancel=check_cancel)
                if response.status != 200 or not isinstance(response.body, dict):
                    raise ZoteroWriteError(f'Zotero yazması başarısız (HTTP {response.status}).', response.status)
                reply = response.body
                for index, row in enumerate(batch):
                    idx = str(index)
                    failure = reply.get('failed', {}).get(idx)
                    if failure:
                        error = 'Zotero kayıt yazması başarısız (HTTP ' + str(failure.get('code', '?')) + ').'
                        self._state(row, 'failed', error)
                        outcomes[row['source_identity']] = (None, error)
                        continue
                    successful = reply.get('successful', {}).get(idx)
                    reported_key = successful.get('key') if isinstance(successful, dict) else None
                    reported_key = reported_key or reply.get('success', {}).get(idx) or reply.get('unchanged', {}).get(idx)
                    if reported_key != row['object_key']:
                        self._state(row, 'uncertain', 'Zotero yazma yanıtı eksik veya anahtar farklı.')
                        outcomes[row['source_identity']] = (None, 'Zotero yazma sonucu doğrulanamadı.')
                        continue
                    obj = self._reconcile(row, check_cancel)
                    if not obj:
                        raise ZoteroWriteError('Yazma yanıtındaki Zotero kaydı okunamadı.')
                    outcomes[row['source_identity']] = (obj, None)
            except ZoteroWriteError as error:
                for row in batch:
                    if row['source_identity'] not in outcomes:
                        self._state(row, 'uncertain' if not error.status else 'failed', str(error))
                        outcomes[row['source_identity']] = (None, str(error))
        return outcomes

    def _collection(self, identity, name, parent, existing, check_cancel):
        row = self._ledger('collections', identity)
        if not row:
            matches = [obj for obj in existing if _data(obj).get('name') == name
                       and _data(obj).get('parentCollection') == parent]
            if len(matches) > 1:
                raise ZoteroWriteError('Aynı ad ve üst koleksiyonda birden fazla Zotero koleksiyonu var.')
            row = self._reserve('collections', identity, {'name': name, 'parentCollection': parent},
                                matches[0]['key'] if matches else None)
        obj = self._reconcile(row, check_cancel)
        if obj:
            return obj['key']
        obj, error = self._create([row], check_cancel)[identity]
        if error:
            raise ZoteroWriteError(error)
        existing.append(obj)
        return obj['key']

    def _membership(self, obj, collection, check_cancel):
        for attempt in range(3):
            key = obj['key']
            # Read immediately before patching; union is against the current version.
            obj = self._get(f'/{LIBRARY}/items/{key}', check_cancel)
            if not obj:
                raise ZoteroWriteError('Zotero kaydı koleksiyona eklenmeden önce silinmiş.')
            data = _data(obj)
            collections = data.get('collections', [])
            if collection in collections:
                return obj
            version = obj.get('version', data.get('version'))
            if type(version) is not int:
                raise ZoteroWriteError('Zotero kayıt sürümü eksik.')
            response = self._request('PATCH', f'/{LIBRARY}/items/{key}',
                {'collections': list(dict.fromkeys(collections + [collection]))},
                headers={'If-Unmodified-Since-Version': str(version)}, check_cancel=check_cancel)
            if response.status == 412:
                continue
            if response.status not in (200, 204):
                raise ZoteroWriteError(f'Zotero koleksiyon üyeliği yazılamadı (HTTP {response.status}).', response.status)
            updated = self._get(f'/{LIBRARY}/items/{key}', check_cancel)
            if updated and collection in _data(updated).get('collections', []):
                return updated
        raise ZoteroWriteError('Zotero kaydı eşzamanlı değişti; koleksiyon üyeliği doğrulanamadı.', 412)

    def _save_paper(self, record, obj, session_id, search_id):
        data, key = dict(_data(obj)), obj['key']
        with self.store.lock, self.store.db:
            old = self.store.db.execute('SELECT id FROM papers WHERE library_id=? AND item_key=?', (LIBRARY, key)).fetchone()
            pid = old['id'] if old else str(uuid.uuid4())
            if old:
                # Reading notes, decisions, annotation and verification belong to the reviewer.
                self.store.db.execute('UPDATE papers SET data_json=?,updated_at=? WHERE id=?', (json_text(data), utcnow(), pid))
            else:
                memberships = set(data.get('collections', []))
                mapping = self.store.settings().get('collection_mapping', {})
                states = {role for role, collection in mapping.items() if collection in memberships}
                state = ('conflict' if {'included', 'excluded'} <= states else 'included' if 'included' in states
                         else 'excluded' if 'excluded' in states else 'candidate')
                self.store.db.execute('INSERT INTO papers VALUES(?,?,?,?,?,?,?,?)',
                    (pid, LIBRARY, key, json_text(data), state, '', 0, utcnow()))
            self.store.db.execute("INSERT OR IGNORE INTO reading_notes(paper_id,zotero_json,fields_json,local_draft) VALUES(?,'[]','{}','')",(pid,))
            self.store.db.execute('INSERT OR IGNORE INTO search_paper_links VALUES(?,?)', (search_id, pid))
            self.store.db.execute('INSERT OR IGNORE INTO zotero_source_refs VALUES(?,?,?,?,?,?,?)',
                (self.server_id, LIBRARY, record['eid'], search_id, session_id, key, utcnow()))

    def _similarity_index(self, items):
        index = {'doi': {}, 'title': {}}
        for obj in items:
            data = _data(obj)
            if data.get('itemType') in ('note', 'attachment', 'annotation'):
                continue
            for reason, value in (('doi', normalize_doi(data.get('DOI', ''))),
                                  ('title', ' '.join(data.get('title', '').casefold().split()))):
                if value:
                    index[reason].setdefault(value, []).append((obj['key'], scopus_eids(data)))
        return index

    def _suspects(self, record, index):
        suspects = {}
        title = ' '.join(record['title'].casefold().split())
        for reason, value in (('doi', record['doi']), ('title', title)):
            for key, eids in index[reason].get(value, []):
                if record['eid'] not in eids:
                    suspects.setdefault(key, reason)
        with self.store.lock, self.store.db:
            for key, reason in suspects.items():
                self.store.db.execute('INSERT OR IGNORE INTO zotero_duplicate_suspects VALUES(?,?,?,?,?,?)',
                    (self.server_id, LIBRARY, record['eid'], key, reason, utcnow()))
        return len(suspects)

    def import_records(self, records, session_id, search_id, check_cancel=lambda: None):
        check_cancel()
        self._scope()
        if not isinstance(session_id, str) or not session_id or len(session_id) > 200:
            raise ValidationError('Geçersiz literatür oturumu.')
        with self.store.lock:
            search = self.store.db.execute('SELECT display_id FROM search_runs WHERE id=?', (search_id,)).fetchone()
        if not search:
            raise ValidationError('Arama kaydı bulunamadı.')
        unique = {}
        for record in records:
            if not isinstance(record, dict) or not EID.fullmatch(record.get('eid', '')) or not isinstance(record.get('item'), dict):
                raise ValidationError('RIS kaydı geçersiz.')
            if scopus_eids(record['item']) != {record['eid']} or record['item'].get('itemType') in ('note', 'attachment', 'annotation'):
                raise ValidationError('RIS kaydı kimliği veya yayın türü geçersiz.')
            if record['eid'] in unique and unique[record['eid']]['item'] != record['item']:
                raise ValidationError('Aynı Scopus EID için farklı RIS içerikleri var; inceleme gerekiyor.')
            unique[record['eid']] = record
        if not self.preflight()['ready']:
            raise ZoteroWriteError('Zotero yazma izni gerekiyor; bağlantı bölümünden yetkilendirin.', 401)
        result = dict(raw_count=len(records), unique_count=len(unique), imported=0, reused=0,
                      failed=0, duplicates=0, failures=[], collection_key='')
        if not unique:
            return result
        collections = self._all('collections', check_cancel)
        session_key = self._collection('session:' + session_id, session_id, SEARCH_ROOT, collections, check_cancel)
        search_key = self._collection('search:' + search_id, search['display_id'] + '_Scopus', session_key, collections, check_cancel)
        result['collection_key'] = search_key
        items = self._all('items', check_cancel)
        by_eid = {}
        for obj in items:
            data = _data(obj)
            if data.get('itemType') not in ('note', 'attachment', 'annotation'):
                for eid in scopus_eids(data):
                    by_eid.setdefault(eid, []).append(obj)
        pending, ready = [], []
        def failed(eid, message):
            result['failed'] += 1
            result['failures'].append({'eid': eid, 'error': message})
        for eid, record in unique.items():
            check_cancel()
            try:
                row = self._ledger('items', eid)
                matches = by_eid.get(eid, [])
                if len(matches) > 1 or row and any(obj['key'] != row['object_key'] for obj in matches):
                    raise ZoteroWriteError('Aynı Scopus EID birden fazla Zotero kaydında var; otomatik birleştirilmedi.')
                if not row:
                    body = dict(record['item'], collections=[CANDIDATE, search_key])
                    row = self._reserve('items', eid, body, matches[0]['key'] if matches else None)
                obj = self._reconcile(row, check_cancel)
                if obj:
                    ready.append((record, obj, False))
                else:
                    pending.append(row)
            except ZoteroWriteError as error:
                failed(eid, str(error))
        outcomes = self._create(pending, check_cancel)
        for eid, (obj, error) in outcomes.items():
            if error:
                failed(eid, error)
            else:
                ready.append((unique[eid], obj, True))
                items.append(obj)
        similarity_index = self._similarity_index(items)
        for record, obj, new in ready:
            check_cancel()
            try:
                result['duplicates'] += self._suspects(record, similarity_index)
                obj = self._membership(obj, search_key, check_cancel)
                self._save_paper(record, obj, session_id, search_id)
                result['imported' if new else 'reused'] += 1
            except ZoteroWriteError as error:
                failed(record['eid'], str(error))
        return result

    def import_acm(self, records, search_id, check_cancel=lambda: None):
        """ACM records of one search → 00_AramaKayitlari › S0xx_ACM (and 01_Aday, like Scopus imports).
        Each search gets its own items; records also found in Scopus/IEEE are merged later in Zotero's
        Duplicate Items view, as CEN401 Adım 6 m.4 describes. A repeated collection reuses its own items."""
        check_cancel()
        self._scope()
        with self.store.lock:
            search = self.store.db.execute('SELECT display_id,database_name FROM search_runs WHERE id=?', (search_id,)).fetchone()
        if not search or search['database_name'] != 'ACM Digital Library':
            raise ValidationError('ACM arama kaydı bulunamadı.')
        unique = {}
        for record in records:
            doi = normalize_doi(record.get('doi', '')) if isinstance(record, dict) else ''
            item = record.get('item') if isinstance(record, dict) else None
            if not re.fullmatch(r'10\.\d{4,9}/\S+', doi) or not isinstance(item, dict) or item.get('itemType') not in ('journalArticle', 'conferencePaper'):
                raise ValidationError('ACM kaydı geçersiz.')
            if normalize_doi(item.get('DOI', '')) != doi:
                raise ValidationError('ACM kaydının DOI bilgisi tutarsız.')
            unique.setdefault(doi, item)
        if not self.preflight()['ready']:
            raise ZoteroWriteError('Zotero yazma izni gerekiyor; Otomatik tarama bölümünden "Zotero yazma iznini ver".', 401)
        result = dict(raw_count=len(records), unique_count=len(unique), imported=0, reused=0, failed=0, failures=[], collection_key='')
        if not unique:
            return result
        collections = self._all('collections', check_cancel)
        search_key = self._collection('acm:' + search_id, search['display_id'] + '_ACM', SEARCH_ROOT, collections, check_cancel)
        result['collection_key'] = search_key
        pending, ready = [], []
        def failed(doi, message):
            result['failed'] += 1
            result['failures'].append({'doi': doi, 'error': message})
        for doi, item in unique.items():
            check_cancel()
            identity = f'acm:{search_id}:{doi}'
            try:
                row = self._ledger('items', identity) or self._reserve('items', identity, dict(item, collections=[CANDIDATE, search_key]))
                obj = self._reconcile(row, check_cancel)
                if obj:
                    ready.append((identity, obj, False))
                else:
                    pending.append(row)
            except ZoteroWriteError as error:
                failed(doi, str(error))
        for identity, (obj, error) in self._create(pending, check_cancel).items():
            if error:
                failed(identity.split(':', 2)[2], error)
            else:
                ready.append((identity, obj, True))
        for identity, obj, new in ready:
            check_cancel()
            try:
                obj = self._membership(obj, search_key, check_cancel)
                self._save_paper({'eid': identity}, obj, 'acm:' + search_id, search_id)
                result['imported' if new else 'reused'] += 1
            except ZoteroWriteError as error:
                failed(identity.split(':', 2)[2], str(error))
        return result
