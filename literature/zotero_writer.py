"""Recoverable, metadata-only writes to the explicitly configured local TEZ library."""
import hashlib
import json
import os
import re
import secrets
import uuid
from dataclasses import dataclass
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from pathlib import Path
from urllib.request import HTTPRedirectHandler, ProxyHandler, Request, build_opener

from .ris import EID, normalize_doi, scopus_eids
from .storage import ValidationError, json_text, utcnow
from . import fulltext, screening
from .zotero import load_api_key, plain_html, save_api_key


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
CREATE TABLE IF NOT EXISTS screening_applications(
 server_id TEXT NOT NULL, library_id TEXT NOT NULL, item_key TEXT NOT NULL, digest TEXT NOT NULL,
 state TEXT NOT NULL, error TEXT, note_key TEXT, updated_at TEXT NOT NULL,
 PRIMARY KEY(server_id,library_id,item_key));
CREATE TABLE IF NOT EXISTS pdf_attachments(
 server_id TEXT NOT NULL, library_id TEXT NOT NULL, item_key TEXT NOT NULL, filename TEXT NOT NULL, md5 TEXT NOT NULL,
 attachment_key TEXT, state TEXT NOT NULL, error TEXT, updated_at TEXT NOT NULL,
 PRIMARY KEY(server_id,library_id,item_key));
CREATE TABLE IF NOT EXISTS fulltext_applications(
 server_id TEXT NOT NULL, library_id TEXT NOT NULL, item_key TEXT NOT NULL, digest TEXT NOT NULL,
 state TEXT NOT NULL, error TEXT, note_key TEXT, updated_at TEXT NOT NULL,
 PRIMARY KEY(server_id,library_id,item_key));
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


UPLOAD_TOKEN = r'[A-Za-z0-9_-]{8,128}'
UPLOAD_URL = re.compile(r'http://(?:localhost|127\.0\.0\.1):23119/api(/local/uploads/' + UPLOAD_TOKEN + r')')


class LocalZoteroClient:
    def __init__(self):
        self.opener = build_opener(ProxyHandler({}), NoRedirect())

    def request(self, method, path, body=None, headers=None, raw=None):
        """Only the local Zotero API of this computer and only the TEZ group. Items are never deleted; the only
        deletion is an empty collection, and file uploads go to stored-file attachments of TEZ items."""
        allowed = (path == '/' and method == 'GET') or (path == '/local/authorize' and method == 'POST')
        resource = re.fullmatch(r'/groups/6718452/(items|collections)(?:/(' + KEY_PATTERN + r')(?:/(items|collections|file))?)?'
                                r'(?:\?[A-Za-z0-9%=&,_-]*)?', path)
        if resource:
            kind, key, sub = resource[1], resource[2], resource[3]
            allowed |= bool(method == 'GET' and sub != 'file'
                        or method == 'POST' and not key and raw is None
                        or method == 'PATCH' and kind == 'items' and key and not sub
                        or method == 'POST' and kind == 'items' and sub == 'file' and raw is not None
                        or method == 'DELETE' and kind == 'collections' and key and not sub)
        upload = re.fullmatch(r'/local/uploads/' + UPLOAD_TOKEN, path)
        allowed |= bool(upload and method == 'POST' and raw is not None)
        if not allowed:
            raise ValidationError('Yetkilendirilmemiş Zotero yolu veya işlemi.')
        request_headers = {'Zotero-API-Version': '3', 'User-Agent': 'LiteraturKayit/0.9.4', **(headers or {})}
        payload = None
        if raw is not None:
            payload = bytes(raw)
        elif body is not None:
            payload = json_text(body).encode('utf-8')
            request_headers['Content-Type'] = 'application/json'
        req = Request('http://127.0.0.1:23119/api' + path, data=payload, headers=request_headers, method=method)
        try:
            response = self.opener.open(req, timeout=120 if path == '/local/authorize' or raw is not None else 30)
        except HTTPError as error:
            response = error
        with response:
            raw_reply = response.read(16 * 1024 * 1024 + 1)
            if len(raw_reply) > 16 * 1024 * 1024:
                raise ZoteroWriteError('Zotero yanıtı boyut sınırını aşıyor.')
            try:
                data = json.loads(raw_reply) if raw_reply else None
            except (ValueError, UnicodeError):
                data = None
                if 200 <= response.status < 300 and raw_reply and path != '/' and raw is None:
                    raise ZoteroWriteError('Zotero geçerli JSON döndürmedi.') from None
            return HTTPResponse(response.status, data, dict(response.headers))


def _header(response, name):
    return next((str(v) for k, v in response.headers.items() if k.casefold() == name.casefold()), '')


def _data(obj):
    if not isinstance(obj, dict) or not isinstance(obj.get('data'), dict):
        raise ZoteroWriteError('Zotero nesnesi geçersiz.')
    return obj['data']


def title_key(title):
    return re.sub(r'\W+', '', str(title or '').casefold())


def paper_identity(data, fallback=''):
    """One identity per publication across searches and databases: the DOI, else a long enough title."""
    doi = normalize_doi(data.get('DOI', '') or data.get('doi', ''))
    if doi:
        return 'paper:doi:' + doi
    key = title_key(data.get('title', ''))
    if len(key) >= 20:
        return 'paper:title:' + key
    return 'paper:record:' + fallback if fallback else ''


def same_note(a, b):
    return ' '.join(plain_html(a or '').split()) == ' '.join(plain_html(b or '').split())


def _tag_names(data):
    return [t.get('tag') for t in data.get('tags', []) if isinstance(t, dict)]


def paper_aliases(data):
    """Every identity an existing Zotero item answers to (DOI and title), for matching against a new record."""
    out = set()
    doi = normalize_doi(data.get('DOI', ''))
    if doi:
        out.add('paper:doi:' + doi)
    key = title_key(data.get('title', ''))
    if len(key) >= 20:
        out.add('paper:title:' + key)
    return out


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

    def _request(self, method, path, body=None, *, headers=None, check_cancel=lambda: None, raw=None):
        check_cancel()
        supplied = {'Zotero-Server-ID': self.server_id, **(headers or {})}
        writing = method != 'GET' and path != '/local/authorize'
        if writing:
            self._scope()
            if not self.key:
                raise ZoteroWriteError('Zotero yazma izni gerekiyor; bağlantı bölümünden yeniden yetkilendirin.', 401)
            supplied['Zotero-API-Key'] = self.key
        try:
            response = self.client.request(method, path, body=body, headers=supplied, **({'raw': raw} if raw is not None else {}))
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

    def _all_settled(self, kind, check_cancel, waits=(5, 15, 30)):
        """Right after a write Zotero is still indexing new files, so the library version can move between pages."""
        import time
        for wait in (*waits, None):
            try:
                return self._all(kind, check_cancel)
            except ZoteroWriteError as error:
                if wait is None or 'değişti' not in str(error):
                    raise
                time.sleep(wait)

    def _ledger(self, kind, identity):
        with self.store.lock:
            row = self.store.db.execute('''SELECT * FROM zotero_import_objects
                WHERE server_id=? AND library_id=? AND kind=? AND source_identity=?''',
                (self.server_id, LIBRARY, kind, identity)).fetchone()
        return dict(row) if row else None

    def _ledger_by_key(self, kind, key):
        with self.store.lock:
            row = self.store.db.execute('''SELECT * FROM zotero_import_objects
                WHERE server_id=? AND library_id=? AND kind=? AND object_key=?''', (self.server_id, LIBRARY, kind, key)).fetchone()
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
        if row['kind'] == 'items' and row['source_identity'].startswith('acm:'):
            # ACM items carry a random key reserved by this program; the DOI identifies the record. Zotero may
            # normalize text fields, so a field-by-field comparison would reject a correctly written item.
            matches = (normalize_doi(data.get('DOI', '')) == row['source_identity'].split(':', 2)[2]
                       and data.get('itemType') == intended.get('itemType'))
        elif row['kind'] == 'items' and row['source_identity'].startswith(('screening-note:', 'reading-note:', 'fulltext-exclusion-note:')):
            # Zotero may wrap or re-serialize note HTML; the parent and the visible text identify the note.
            matches = (data.get('itemType') == 'note' and data.get('parentItem') == intended.get('parentItem')
                       and same_note(data.get('note'), intended.get('note')))
        elif row['kind'] == 'items' and row['source_identity'].startswith('pdf-attachment:'):
            # Zotero fills md5/mtime and may retitle the attachment; the parent and the stored-file mode identify it.
            matches = (data.get('itemType') == 'attachment' and data.get('parentItem') == intended.get('parentItem')
                       and data.get('linkMode') == intended.get('linkMode'))
        elif row['kind'] == 'items' and row['source_identity'].startswith('paper:record:'):
            matches = title_key(data.get('title')) == title_key(intended.get('title')) and data.get('itemType') == intended.get('itemType')
        elif row['kind'] == 'items' and row['source_identity'].startswith('paper:'):
            matches = paper_identity(data) == row['source_identity'] or row['source_identity'] in paper_aliases(data)
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

    def _add_collections(self, obj, wanted, check_cancel):
        for attempt in range(3):
            obj = self._get(f"/{LIBRARY}/items/{obj['key']}", check_cancel)
            if not obj:
                raise ZoteroWriteError('Zotero kaydı koleksiyona eklenmeden önce silinmiş.')
            data = _data(obj)
            current = data.get('collections', [])
            if all(key in current for key in wanted):
                return obj
            version = obj.get('version', data.get('version'))
            if type(version) is not int:
                raise ZoteroWriteError('Zotero kayıt sürümü eksik.')
            response = self._request('PATCH', f"/{LIBRARY}/items/{obj['key']}",
                {'collections': list(dict.fromkeys(current + list(wanted)))},
                headers={'If-Unmodified-Since-Version': str(version)}, check_cancel=check_cancel)
            if response.status == 412:
                continue
            if response.status not in (200, 204):
                raise ZoteroWriteError(f'Zotero koleksiyon üyeliği yazılamadı (HTTP {response.status}).', response.status)
        raise ZoteroWriteError('Zotero kaydı eşzamanlı değişti; koleksiyon üyeliği doğrulanamadı.', 412)

    def import_papers(self, searches, check_cancel=lambda: None, progress=lambda text: None):
        """Scopus/IEEE RIS records → one Zotero item per publication (DOI, else title), placed in every search's
        collection 00_AramaKayitlari › S0xx_<Platform> and in 01_Aday. Items already in the TEZ library with the
        same DOI/title (e.g. collected from ACM) are reused, so duplicates are not created in the first place.
        `searches` is a list of dicts: search_id, label ('Scopus'/'IEEE'), records (parse_ris output).
        Returns one result per search; a repeated import reuses everything it wrote before."""
        check_cancel()
        self._scope()
        if not self.preflight()['ready']:
            raise ZoteroWriteError('Zotero yazma izni gerekiyor; Otomatik tarama bölümünden "Zotero yazma iznini ver".', 401)
        progress('Zotero kütüphanesi okunuyor…')
        collections = self._all('collections', check_cancel)
        index = {}
        for obj in self._all('items', check_cancel):
            data = _data(obj)
            if data.get('itemType') in ('note', 'attachment', 'annotation'):
                continue
            for alias in paper_aliases(data):
                index.setdefault(alias, obj['key'])
        results = []
        total = sum(len(s['records']) for s in searches)
        done = 0
        for search in searches:
            check_cancel()
            with self.store.lock:
                run = self.store.db.execute('SELECT display_id FROM search_runs WHERE id=?', (search['search_id'],)).fetchone()
            if not run:
                raise ValidationError('Arama kaydı bulunamadı.')
            name = f"{run['display_id']}_{search['label']}"
            search_key = self._collection('ris:' + search['search_id'], name, SEARCH_ROOT, collections, check_cancel)
            result = dict(search_id=search['search_id'], display_id=run['display_id'], collection=name, records=len(search['records']),
                          created=0, reused=0, failed=0, failures=[], keys=set())
            pending, ready = [], []
            identities = {}
            for number, record in enumerate(search['records'], 1):
                item = record['item']
                identity = paper_identity(item, f"{search['search_id']}:{number}")
                if identity in identities:
                    continue  # the same publication twice in one export: one item, counted once
                identities[identity] = record
                try:
                    row = self._ledger('items', identity)
                    if not row:
                        existing = index.get(identity) or next((index[a] for a in paper_aliases(item) if a in index), None)
                        # An item this program already wrote (e.g. from ACM) keeps its own ledger entry.
                        row = (existing and self._ledger_by_key('items', existing)) or self._reserve(
                            'items', identity, dict(item, collections=[CANDIDATE, search_key]), existing)
                    obj = self._reconcile(row, check_cancel)
                    if obj:
                        ready.append((identity, obj, False))
                    else:
                        pending.append(row)
                except ZoteroWriteError as error:
                    result['failed'] += 1
                    result['failures'].append({'title': item.get('title', '')[:120], 'error': str(error)})
            for offset in range(0, len(pending), 50):
                for identity, (obj, error) in self._create(pending[offset:offset + 50], check_cancel).items():
                    if error:
                        result['failed'] += 1
                        result['failures'].append({'title': identities[identity]['item'].get('title', '')[:120], 'error': error})
                    else:
                        ready.append((identity, obj, True))
                        for alias in paper_aliases(_data(obj)) | {identity}:
                            index.setdefault(alias, obj['key'])
                progress(f"{name}: {min(offset + 50, len(pending))}/{len(pending)} yeni kayıt yazıldı")
            for number, (identity, obj, new) in enumerate(ready, 1):
                check_cancel()
                try:
                    obj = self._add_collections(obj, [CANDIDATE, search_key], check_cancel)
                    self._save_paper({'eid': identity}, obj, 'ris:' + search['search_id'], search['search_id'])
                    result['created' if new else 'reused'] += 1
                    result['keys'].add(obj['key'])
                except ZoteroWriteError as error:
                    result['failed'] += 1
                    result['failures'].append({'title': identities[identity]['item'].get('title', '')[:120], 'error': str(error)})
                if number % 100 == 0:
                    progress(f"{name}: {number}/{len(ready)} kayıt koleksiyona eklendi")
            done += len(search['records'])
            progress(f"{name} bitti ({done}/{total} kayıt): {result['created']} yeni, {result['reused']} zaten vardı, {result['failed']} hata")
            results.append(result)
        return results

    def _add_to_item(self, obj, collections, tags, check_cancel, remove_tags=(), remove_collections=()):
        """Union of collections and tags on one item (with optional tag/collection replacement when decisions change).
        The first attempt uses the version read with the library, a 412 re-reads the item. Returns True when a request was sent."""
        for attempt in range(3):
            if attempt:
                obj = self._get(f"/{LIBRARY}/items/{obj['key']}", check_cancel)
                if not obj:
                    raise ZoteroWriteError('Zotero kaydı silinmiş; eleme kararı uygulanmadı.')
            data = _data(obj)
            current_collections = data.get('collections', [])
            current_tags = _tag_names(data)
            missing_collections = [c for c in collections if c not in current_collections]
            present_remove_collections = [c for c in remove_collections if c in current_collections]
            missing_tags = [t for t in tags if t not in current_tags]
            present_remove_tags = [t for t in remove_tags if t in current_tags]
            if not missing_collections and not present_remove_collections and not missing_tags and not present_remove_tags:
                return attempt > 0
            version = obj.get('version', data.get('version'))
            if type(version) is not int:
                raise ZoteroWriteError('Zotero kayıt sürümü eksik.')
            body = {}
            if missing_collections or present_remove_collections:
                kept_cols = [c for c in current_collections if c not in present_remove_collections]
                body['collections'] = kept_cols + [c for c in missing_collections if c not in kept_cols]
            if missing_tags or present_remove_tags:
                kept = [t for t in data.get('tags', []) if not (isinstance(t, dict) and t.get('tag') in present_remove_tags)]
                body['tags'] = kept + [{'tag': t} for t in missing_tags]
            response = self._request('PATCH', f"/{LIBRARY}/items/{obj['key']}", body,
                                     headers={'If-Unmodified-Since-Version': str(version)}, check_cancel=check_cancel)
            if response.status == 412:
                continue
            if response.status not in (200, 204):
                raise ZoteroWriteError(f'Zotero eleme güncellemesi yazılamadı (HTTP {response.status}).', response.status)
            return True
        raise ZoteroWriteError('Zotero kaydı eşzamanlı değişti; eleme kararı doğrulanamadı.', 412)

    def _screening_state(self, key, digest, state, error=None, note_key=None):
        with self.store.lock, self.store.db:
            self.store.db.execute('''INSERT INTO screening_applications VALUES(?,?,?,?,?,?,?,?)
                ON CONFLICT(server_id,library_id,item_key) DO UPDATE SET digest=excluded.digest,state=excluded.state,
                error=excluded.error,note_key=COALESCE(excluded.note_key,screening_applications.note_key),
                updated_at=excluded.updated_at''', (self.server_id, LIBRARY, key, digest, state, error, note_key, utcnow()))

    def _fulltext_state(self, key, digest, state, error=None, note_key=None):
        with self.store.lock, self.store.db:
            self.store.db.execute('''INSERT INTO fulltext_applications VALUES(?,?,?,?,?,?,?,?)
                ON CONFLICT(server_id,library_id,item_key) DO UPDATE SET digest=excluded.digest,state=excluded.state,
                error=excluded.error,note_key=COALESCE(excluded.note_key,fulltext_applications.note_key),
                updated_at=excluded.updated_at''', (self.server_id, LIBRARY, key, digest, state, error, note_key, utcnow()))

    def _update_note_if_changed(self, row, html, check_cancel):
        """If an approved reading note was modified since a previous run, update its text in Zotero and ledger."""
        intended = json.loads(row['body_json'])
        if same_note(intended.get('note'), html):
            return row
        obj = self._get(f"/{LIBRARY}/items/{row['object_key']}", check_cancel)
        if obj and _data(obj).get('itemType') == 'note' and _data(obj).get('parentItem') == intended.get('parentItem'):
            if not same_note(_data(obj).get('note'), html):
                version = obj.get('version', _data(obj).get('version'))
                response = self._request('PATCH', f"/{LIBRARY}/items/{row['object_key']}", {'note': html},
                                         headers={'If-Unmodified-Since-Version': str(version)}, check_cancel=check_cancel)
                if response.status not in (200, 204):
                    raise ZoteroWriteError(f'Zotero okuma notu güncellenemedi (HTTP {response.status}).', response.status)
        intended['note'] = html
        with self.store.lock, self.store.db:
            self.store.db.execute('''UPDATE zotero_import_objects SET body_json=?,updated_at=?
                WHERE server_id=? AND library_id=? AND kind=? AND source_identity=?''',
                (json_text(intended), utcnow(), row['server_id'], row['library_id'], row['kind'], row['source_identity']))
        return self._ledger(row['kind'], row['source_identity'])

    def apply_screening(self, data, check_cancel=lambda: None, progress=lambda text: None):
        """Approved title/abstract decisions → TEZ: 02_BaslikOzet_Gecen / 05_Haric_BaslikOzet (and 06_Erisim_Kontrol),
        reason-code or full-text tags, and one exclusion note per excluded item. Items stay in 01_Aday; nothing is
        removed or overwritten. A repeated run sends only what is still missing."""
        check_cancel()
        self._scope()
        if not screening.approved(data):
            raise ValidationError('Eleme kararları onaylanmadı ya da onaydan sonra değişti; Zotero\'ya bir şey yazılmadı.')
        actions = screening.plan(data)
        decided = self.store.path(fulltext.RELATIVE.as_posix())
        ft_keys = set()
        if decided.is_file():
            # Full-text decisions own the TamMetin-Secildi / TamMetin-Yedek tags once they exist (a spare promoted to
            # full text, or a selected paper left unread); re-applying the title/abstract stage must not reset them.
            ft_keys = {r.get('key') for r in fulltext.load(decided)['kayitlar']}
            for action in actions:
                if action['key'] in ft_keys:
                    action['tags'] = [t for t in action['tags'] if t not in screening.TAGS.values()]
        mapping = self.store.settings().get('collection_mapping', {})
        targets = {}
        for decision, role in screening.ROLES.items():
            key = mapping.get(role)
            if not key:
                raise ValidationError(f'{screening.COLLECTIONS[decision]} koleksiyonu eşleştirilmemiş (Zotero bölümü → koleksiyon eşleştirmesi).')
            targets[role] = (key, screening.COLLECTIONS[decision])
        if not self.preflight()['ready']:
            raise ZoteroWriteError('Zotero yazma izni gerekiyor; Otomatik tarama bölümünden "Zotero yazma iznini ver".', 401)
        for key, name in targets.values():
            obj = self._get(f'/{LIBRARY}/collections/{key}', check_cancel)
            if not obj or _data(obj).get('name') != name:
                raise ValidationError('Beklenen TEZ koleksiyonu bulunamadı: ' + name)
        progress('Zotero kütüphanesi okunuyor…')
        items = self._all('items', check_cancel)
        by_key, candidates, notes = {}, {}, {}
        for obj in items:
            item = _data(obj)
            if item.get('itemType') == 'note' and item.get('parentItem'):
                notes.setdefault(item['parentItem'], []).append(obj)
            elif item.get('itemType') not in ('attachment', 'annotation', 'note'):
                by_key[obj['key']] = obj
                if CANDIDATE in item.get('collections', []):
                    candidates[obj['key']] = item.get('title', '')
        problems = screening.check(data, candidates)
        if problems:
            raise ValidationError(f'Karar dosyası 01_Aday ile uyuşmuyor ({len(problems)} sorun); Zotero\'ya bir şey yazılmadı. '
                                  f'İlk sorun: {problems[0]}')
        access_key = ''
        collections = self._all('collections', check_cancel)
        existing_access_key = next((c['key'] for c in collections if _data(c).get('name') == screening.ACCESS_COLLECTION), '')
        if any(a['access_check'] for a in actions):
            access_key = self._collection('screening:access', screening.ACCESS_COLLECTION, False, collections, check_cancel)
            existing_access_key = access_key
        digest = screening.digest(data)
        result = dict(items=len(actions), updated=0, unchanged=0, notes_created=0, notes_existing=0, failed=0, failures=[])

        def failed(key, error):
            result['failed'] += 1
            result['failures'].append({'key': key, 'error': str(error)})
            self._screening_state(key, digest, 'failed', str(error))

        all_screening_tags = set(screening.CODES) | set(screening.TAGS.values())
        screening_cols = [k for k, _ in targets.values()] + ([existing_access_key] if existing_access_key else [])
        for r in data['kayitlar']:
            if r.get('durum') in screening.UNDECIDED and r.get('key') in by_key:
                ukey = r['key']
                uobj = by_key[ukey]
                udata = _data(uobj)
                if any(c in udata.get('collections', []) for c in screening_cols) or any(t in _tag_names(udata) for t in all_screening_tags):
                    check_cancel()
                    try:
                        if self._add_to_item(uobj, [], [], check_cancel, remove_tags=all_screening_tags, remove_collections=screening_cols):
                            result['updated'] += 1
                        with self.store.lock, self.store.db:
                            self.store.db.execute('DELETE FROM screening_applications WHERE server_id=? AND library_id=? AND item_key=?',
                                                  (self.server_id, LIBRARY, ukey))
                            self.store.db.execute('DELETE FROM fulltext_applications WHERE server_id=? AND library_id=? AND item_key=?',
                                                  (self.server_id, LIBRARY, ukey))
                    except ZoteroWriteError as error:
                        failed(ukey, error)

        note_rows = []
        for number, action in enumerate(actions, 1):
            check_cancel()
            key = action['key']
            wanted = [targets[action['role']][0]] + ([access_key] if action['access_check'] else [])
            remove_cols = [k for r_role, (k, _) in targets.items() if r_role != action['role']] + (
                [existing_access_key] if existing_access_key and not action['access_check'] else [])
            candidate_remove_tags = set(screening.CODES) if key in ft_keys else all_screening_tags
            remove_tags = [t for t in candidate_remove_tags if t not in action['tags']]
            try:
                if self._add_to_item(by_key[key], wanted, action['tags'], check_cancel,
                                     remove_tags=remove_tags, remove_collections=remove_cols):
                    result['updated'] += 1
                else:
                    result['unchanged'] += 1
                if action['note']:
                    identity = 'screening-note:' + key
                    html = screening.note_html(action['note'].split('\n'))
                    row = self._ledger('items', identity)
                    if not row:
                        existing = next((n['key'] for n in notes.get(key, []) if same_note(_data(n).get('note'), html)), None)
                        row = self._reserve('items', identity, {'itemType': 'note', 'parentItem': key, 'note': html,
                                                                'tags': []}, existing)
                    note_rows.append(row)
                else:
                    self._screening_state(key, digest, 'applied')
            except ZoteroWriteError as error:
                failed(key, error)
            if number % 100 == 0:
                progress(f'Koleksiyon ve etiketler: {number}/{len(actions)}')
        pending = []
        for row in note_rows:
            check_cancel()
            key = row['source_identity'].split(':', 1)[1]
            try:
                if self._reconcile(row, check_cancel):
                    result['notes_existing'] += 1
                    self._screening_state(key, digest, 'applied', note_key=row['object_key'])
                else:
                    pending.append(row)
            except ZoteroWriteError as error:
                failed(key, error)
        for offset in range(0, len(pending), 50):
            for identity, (obj, error) in self._create(pending[offset:offset + 50], check_cancel).items():
                key = identity.split(':', 1)[1]
                if error:
                    failed(key, error)
                else:
                    result['notes_created'] += 1
                    self._screening_state(key, digest, 'applied', note_key=obj['key'])
            progress(f'Hariç notları: {min(offset + 50, len(pending))}/{len(pending)} yazıldı')
        with self.store.lock, self.store.db:
            self.store.audit('screening_apply', LIBRARY, {k: v for k, v in result.items() if k != 'failures'} | {'digest': digest})
        return result

    def apply_fulltext(self, data, root=None, check_cancel=lambda: None, progress=lambda text: None):
        """Approved full-text decisions and 83 reading notes → TEZ: 03_TamMetin_Dahil / 04_Haric_TamMetin,
        tag reconciliation (TamMetin-Secildi / TamMetin-Yedek / H3), and reading/exclusion child notes."""
        check_cancel()
        self._scope()
        root = root or self.store.root
        if not fulltext.approved(data, root):
            raise ValidationError('Tam metin kararları veya okuma notları onaylanmadı ya da onaydan sonra değişti; Zotero\'ya bir şey yazılmadı.')
        actions = fulltext.plan(data, root)
        mapping = self.store.settings().get('collection_mapping', {})
        targets = {}
        for decision, role in fulltext.ROLES.items():
            key = mapping.get(role)
            if not key:
                raise ValidationError(f'{fulltext.COLLECTIONS[decision]} koleksiyonu eşleştirilmemiş (Zotero bölümü → koleksiyon eşleştirmesi).')
            targets[role] = (key, fulltext.COLLECTIONS[decision])
        if not self.preflight()['ready']:
            raise ZoteroWriteError('Zotero yazma izni gerekiyor; Otomatik tarama bölümünden "Zotero yazma iznini ver".', 401)
        for key, name in targets.values():
            obj = self._get(f'/{LIBRARY}/collections/{key}', check_cancel)
            allowed_names = {name, '04_Haric'} if name == '04_Haric_TamMetin' else {name}
            if not obj or _data(obj).get('name') not in allowed_names:
                raise ValidationError('Beklenen TEZ koleksiyonu bulunamadı: ' + name)
        progress('Zotero kütüphanesi okunuyor…')
        items = self._all('items', check_cancel)
        by_key, candidates, notes = {}, {}, {}
        relevant_cols = {k for k, _ in targets.values()} | {CANDIDATE}
        for obj in items:
            item = _data(obj)
            if item.get('itemType') == 'note' and item.get('parentItem'):
                notes.setdefault(item['parentItem'], []).append(obj)
            elif item.get('itemType') not in ('attachment', 'annotation', 'note'):
                by_key[obj['key']] = obj
                if set(item.get('collections', [])) & relevant_cols:
                    candidates[obj['key']] = item.get('title', '')
        problems = fulltext.check(data, candidates, root)
        if problems:
            raise ValidationError(f'Tam metin kararları Zotero ile uyuşmuyor ({len(problems)} sorun); Zotero\'ya bir şey yazılmadı. '
                                  f'İlk sorun: {problems[0]}')
        digest = fulltext.digest(data, root)
        counts = fulltext.counts(data, root)
        result = dict(items=len(actions), included=counts['dahil'], excluded=counts['haric'],
                      updated=0, unchanged=0, notes_created=0, notes_existing=0, failed=0, failures=[])

        def failed(key, error):
            result['failed'] += 1
            result['failures'].append({'key': key, 'error': str(error)})
            self._fulltext_state(key, digest, 'failed', str(error))

        note_rows = []
        for number, action in enumerate(actions, 1):
            check_cancel()
            key = action['key']
            wanted = [targets[action['role']][0]]
            try:
                if self._add_to_item(by_key[key], wanted, action['tags'], check_cancel, remove_tags=action['remove_tags']):
                    result['updated'] += 1
                else:
                    result['unchanged'] += 1
                if action['note']:
                    identity = action['note_identity']
                    html = fulltext.note_html(action['note'].splitlines())
                    row = self._ledger('items', identity)
                    if row:
                        row = self._update_note_if_changed(row, html, check_cancel)
                    else:
                        existing = next((n['key'] for n in notes.get(key, []) if same_note(_data(n).get('note'), html)), None)
                        row = self._reserve('items', identity, {'itemType': 'note', 'parentItem': key, 'note': html,
                                                                'tags': []}, existing)
                    note_rows.append(row)
                else:
                    self._fulltext_state(key, digest, 'applied')
            except ZoteroWriteError as error:
                failed(key, error)
            if number % 25 == 0 or number == len(actions):
                progress(f'Koleksiyon ve etiketler: {number}/{len(actions)}')
        pending = []
        for row in note_rows:
            check_cancel()
            key = row['source_identity'].split(':', 1)[1]
            try:
                if self._reconcile(row, check_cancel):
                    result['notes_existing'] += 1
                    self._fulltext_state(key, digest, 'applied', note_key=row['object_key'])
                else:
                    pending.append(row)
            except ZoteroWriteError as error:
                failed(key, error)
        for offset in range(0, len(pending), 50):
            for identity, (obj, error) in self._create(pending[offset:offset + 50], check_cancel).items():
                key = identity.split(':', 1)[1]
                if error:
                    failed(key, error)
                else:
                    result['notes_created'] += 1
                    self._fulltext_state(key, digest, 'applied', note_key=obj['key'])
            progress(f'Okuma ve hariç notları: {min(offset + 50, len(pending))}/{len(pending)} yazıldı')
        with self.store.lock, self.store.db:
            self.store.audit('fulltext_apply', LIBRARY, {k: v for k, v in result.items() if k != 'failures'} | {'digest': digest})
        return result

    # --- PDF attachments, field corrections and empty-collection cleanup (0.9.1) -----------------------------

    def _pdf_state(self, key, filename, md5, state, attachment_key=None, error=None):
        with self.store.lock, self.store.db:
            self.store.db.execute('''INSERT INTO pdf_attachments VALUES(?,?,?,?,?,?,?,?,?)
                ON CONFLICT(server_id,library_id,item_key) DO UPDATE SET filename=excluded.filename,md5=excluded.md5,
                attachment_key=COALESCE(excluded.attachment_key,pdf_attachments.attachment_key),state=excluded.state,
                error=excluded.error,updated_at=excluded.updated_at''',
                (self.server_id, LIBRARY, key, filename, md5, attachment_key, state, error, utcnow()))

    def _upload_file(self, attachment, content, filename, mtime_ms, check_cancel):
        """Zotero 10 local file upload: authorize (md5/filename/size/mtime) → send the bytes → register."""
        md5 = hashlib.md5(content).hexdigest()
        data = _data(attachment)
        if data.get('md5') == md5:
            return 'exists', md5
        endpoint = f"/{LIBRARY}/items/{attachment['key']}/file"
        condition = {'If-Match': data['md5']} if data.get('md5') else {'If-None-Match': '*'}
        form = {'Content-Type': 'application/x-www-form-urlencoded', **condition}
        response = self._request('POST', endpoint, headers=form, check_cancel=check_cancel,
                                 raw=urlencode({'md5': md5, 'filename': filename, 'filesize': len(content),
                                                'mtime': mtime_ms}).encode('ascii'))
        if response.status != 200 or not isinstance(response.body, dict):
            raise ZoteroWriteError(f'Zotero PDF yükleme isteğini kabul etmedi (HTTP {response.status}).', response.status)
        if response.body.get('exists'):
            return 'exists', md5
        match = UPLOAD_URL.fullmatch(str(response.body.get('url', '')))
        token = str(response.body.get('uploadKey', ''))
        if not match or not re.fullmatch(UPLOAD_TOKEN, token):
            raise ZoteroWriteError('Zotero yükleme adresi bu bilgisayardaki Zotero adresi değil; PDF gönderilmedi.')
        content_type = str(response.body.get('contentType') or 'application/pdf')
        if not re.fullmatch(r'[A-Za-z0-9.+/-]{1,100}(?:; ?[A-Za-z0-9=._-]{1,100})?', content_type):
            content_type = 'application/pdf'
        prefix = str(response.body.get('prefix') or '').encode('utf-8')
        suffix = str(response.body.get('suffix') or '').encode('utf-8')
        check_cancel()
        try:
            # The upload key authorizes this request; no API key or server ID is sent with the file.
            sent = self.client.request('POST', match[1], headers={'Content-Type': content_type}, raw=prefix + content + suffix)
        except (URLError, TimeoutError, ConnectionError) as error:
            raise ZoteroWriteError('PDF Zotero\'ya gönderilemedi; yeniden başlatınca bu dosyadan devam eder.') from error
        if sent.status not in (200, 201, 204):
            raise ZoteroWriteError(f'Zotero PDF dosyasını almadı (HTTP {sent.status}).', sent.status)
        done = self._request('POST', endpoint, headers=form, check_cancel=check_cancel,
                             raw=urlencode({'upload': token}).encode('ascii'))
        if done.status not in (200, 204):
            raise ZoteroWriteError(f'Zotero PDF kaydını tamamlamadı (HTTP {done.status}).', done.status)
        return 'uploaded', md5

    def attach_pdfs(self, entries, check_cancel=lambda: None, progress=lambda text: None):
        """Each included paper gets its archived PDF as a stored-file child attachment (Kılavuz Adım 8: "Zotero'da her
        kaydın PDF'i kayda eklenir"). A PDF already attached to the item is kept and no second copy is made."""
        result = dict(pdfs=len(entries), uploaded=0, existing=0, failed=0, failures=[])
        if not entries:
            return result
        if not self.preflight()['ready']:
            raise ZoteroWriteError('Zotero yazma izni gerekiyor; Zotero bölümünden yeniden yetkilendirin.', 401)
        progress('PDF ekleri için Zotero okunuyor…')
        children, parents = {}, set()
        for obj in self._all_settled('items', check_cancel):
            data = _data(obj)
            if data.get('itemType') == 'attachment' and data.get('parentItem'):
                children.setdefault(data['parentItem'], []).append(obj)
            elif data.get('itemType') not in ('note', 'annotation', 'attachment'):
                parents.add(obj['key'])
        for number, entry in enumerate(entries, 1):
            check_cancel()
            key, name, path = entry['key'], entry['filename'], Path(entry['path'])
            try:
                if key not in parents:
                    raise ZoteroWriteError('Zotero kaydı bulunamadı.')
                content = path.read_bytes()
                if not content.startswith(b'%PDF'):
                    raise ZoteroWriteError(f'{name} bir PDF dosyası değil.')
                identity = 'pdf-attachment:' + key
                row = self._ledger('items', identity)
                if not row:
                    pdfs = [o for o in children.get(key, []) if _data(o).get('contentType') == 'application/pdf'
                            and _data(o).get('linkMode') in ('imported_file', 'imported_url')]
                    same = [o for o in pdfs if _data(o).get('filename') == name]
                    if pdfs and not same:
                        result['existing'] += 1
                        self._pdf_state(key, name, hashlib.md5(content).hexdigest(), 'existing', pdfs[0]['key'])
                        continue
                    row = self._reserve('items', identity, {
                        'itemType': 'attachment', 'parentItem': key, 'linkMode': 'imported_file', 'title': 'Tam metin PDF',
                        'contentType': 'application/pdf', 'filename': name, 'tags': []}, same[0]['key'] if same else None)
                obj = self._reconcile(row, check_cancel)
                if not obj:
                    obj, error = self._create([row], check_cancel)[identity]
                    if error:
                        raise ZoteroWriteError(error)
                outcome, md5 = self._upload_file(obj, content, name, int(os.path.getmtime(path) * 1000), check_cancel)
                checked = self._get(f"/{LIBRARY}/items/{obj['key']}", check_cancel)
                if outcome == 'uploaded' and checked and _data(checked).get('md5') not in (None, '', md5):
                    raise ZoteroWriteError('Zotero\'daki PDF özeti gönderilen dosyayla aynı değil.')
                result['uploaded' if outcome == 'uploaded' else 'existing'] += 1
                self._pdf_state(key, name, md5, 'attached', obj['key'])
            except (ZoteroWriteError, OSError) as error:
                result['failed'] += 1
                result['failures'].append({'key': key, 'error': str(error)})
                self._pdf_state(key, name, '', 'failed', error=str(error))
            if number % 10 == 0 or number == len(entries):
                progress(f'PDF ekleri: {number}/{len(entries)}')
        with self.store.lock, self.store.db:
            self.store.audit('pdf_attach', LIBRARY, {k: v for k, v in result.items() if k != 'failures'})
        return result

    CORRECTABLE_FIELDS = ('title', 'url', 'DOI', 'place', 'pages', 'publicationTitle', 'proceedingsTitle',
                          'conferenceName', 'volume', 'issue', 'publisher')

    def apply_corrections(self, corrections, check_cancel=lambda: None, progress=lambda text: None):
        """Field corrections on TEZ items, each written only while Zotero still holds the expected old value."""
        result = dict(corrections=len(corrections), updated=0, unchanged=0, failed=0, failures=[])
        if not corrections:
            return result
        if not self.preflight()['ready']:
            raise ZoteroWriteError('Zotero yazma izni gerekiyor; Zotero bölümünden yeniden yetkilendirin.', 401)
        same = lambda a, b: ' '.join(str(a or '').replace(' ', ' ').split()) == ' '.join(str(b or '').replace(' ', ' ').split())
        for correction in corrections:
            check_cancel()
            key, field, old, new = correction['key'], correction['alan'], correction.get('eski'), correction['yeni']
            try:
                if field not in self.CORRECTABLE_FIELDS:
                    raise ZoteroWriteError(f'{field} alanı bu düzeltme ile değiştirilmez.')
                for attempt in range(3):
                    obj = self._get(f'/{LIBRARY}/items/{key}', check_cancel)
                    if not obj:
                        raise ZoteroWriteError('Zotero kaydı bulunamadı.')
                    data = _data(obj)
                    # The local API leaves empty fields out of the item; an empty field is written only when the
                    # expected old value is empty too, and Zotero itself rejects a field the item type lacks.
                    if field not in data and old not in (None, ''):
                        raise ZoteroWriteError(f'{field} alanı Zotero kaydında yok; beklenen eski değer bulunamadı.')
                    current = data.get(field, '')
                    if current == new:
                        result['unchanged'] += 1
                        break
                    if old is not None and not same(current, old):
                        raise ZoteroWriteError(f'Zotero\'daki {field} değeri beklenenden farklı; değiştirilmedi.')
                    response = self._request('PATCH', f'/{LIBRARY}/items/{key}', {field: new},
                                             headers={'If-Unmodified-Since-Version': str(obj.get('version', data.get('version')))},
                                             check_cancel=check_cancel)
                    if response.status == 412:
                        continue
                    if response.status == 400:
                        raise ZoteroWriteError(f'Zotero {field} alanını bu kayıt türünde kabul etmedi.', 400)
                    if response.status not in (200, 204):
                        raise ZoteroWriteError(f'Zotero alanı yazılamadı (HTTP {response.status}).', response.status)
                    result['updated'] += 1
                    break
                else:
                    raise ZoteroWriteError('Zotero kaydı eşzamanlı değişti; düzeltme doğrulanamadı.', 412)
            except ZoteroWriteError as error:
                result['failed'] += 1
                result['failures'].append({'key': key, 'alan': field, 'error': str(error)})
        progress(f"Künye düzeltmeleri: {result['updated']} yazıldı, {result['unchanged']} zaten doğruydu"
                 + (f", {result['failed']} yazılamadı" if result['failed'] else ''))
        with self.store.lock, self.store.db:
            self.store.audit('zotero_corrections', LIBRARY, {k: v for k, v in result.items() if k != 'failures'})
        return result

    def remove_empty_collections(self, entries, check_cancel=lambda: None, progress=lambda text: None):
        """Deletes the listed collections only when the name matches and nothing (no item, no subcollection) is in them."""
        result = dict(collections=len(entries), removed=0, absent=0, failed=0, failures=[])
        if not entries:
            return result
        if not self.preflight()['ready']:
            raise ZoteroWriteError('Zotero yazma izni gerekiyor; Zotero bölümünden yeniden yetkilendirin.', 401)
        protected = set(self.store.settings().get('collection_mapping', {}).values()) | {CANDIDATE, SEARCH_ROOT}
        for entry in entries:
            check_cancel()
            key, name = entry['key'], entry['ad']
            try:
                if key in protected or not re.fullmatch(KEY_PATTERN, key):
                    raise ZoteroWriteError('Bu koleksiyon silinemez.')
                obj = self._get(f'/{LIBRARY}/collections/{key}', check_cancel)
                if not obj:
                    result['absent'] += 1
                    continue
                data = _data(obj)
                if data.get('name') != name:
                    raise ZoteroWriteError(f"Koleksiyonun adı {data.get('name')!r}; beklenen {name!r}.")
                for sub in ('items', 'collections'):
                    inside = self._get(f'/{LIBRARY}/collections/{key}/{sub}?' + urlencode({'format': 'json', 'limit': 1}), check_cancel)
                    if inside:
                        raise ZoteroWriteError('Koleksiyon boş değil; silinmedi.')
                response = self._request('DELETE', f'/{LIBRARY}/collections/{key}',
                                         headers={'If-Unmodified-Since-Version': str(obj.get('version', data.get('version')))},
                                         check_cancel=check_cancel)
                if response.status not in (200, 204):
                    raise ZoteroWriteError(f'Koleksiyon silinemedi (HTTP {response.status}).', response.status)
                result['removed'] += 1
            except ZoteroWriteError as error:
                result['failed'] += 1
                result['failures'].append({'key': key, 'ad': name, 'error': str(error)})
        progress(f"Boş koleksiyonlar: {result['removed']} silindi" + (f", {result['failed']} silinmedi" if result['failed'] else ''))
        with self.store.lock, self.store.db:
            self.store.audit('zotero_empty_collections', LIBRARY, {k: v for k, v in result.items() if k != 'failures'})
        return result
