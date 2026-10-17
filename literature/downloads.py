"""Downloads folder watcher: database exports are matched to captured searches and moved into 01_HamExport.

When "İndirilenleri takip et" is on, every new file in the Downloads folder is looked at once:

* Scopus RIS (e.g. export_<uuid>_<timestamp>.ris, scopus.ris): recognised by its Scopus EIDs.
* IEEE Xplore Results CSV (export2026.10.16-13.03.49.csv): recognised by its column headers.
* IEEE Xplore Citations RIS: recognised by IEEE Xplore links.

Its record count must equal the exact result count of exactly one captured search of that database that has
no export file yet (searches replaced by a captured narrowing step do not count). The file is then moved to
01_HamExport as S0xx_Scopus.ris / S0xx_IEEE.csv / S0xx_IEEE.ris (an IEEE CSV is then turned into RIS by the
existing CSV watcher). Anything uncertain is left where it is and listed for the user to assign. Other files
are never touched; nothing is deleted except the moved file's original after a verified copy.
"""
import hashlib
import json
import logging
import os
import re
import shutil
import threading
import time
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

from . import ieee_csv
from .ris import scopus_eids
from .storage import ValidationError, json_text, utcnow

EXPORT_DIR = '01_HamExport'
SCOPUS, IEEE = 'Scopus', 'IEEE Xplore'
KINDS = {'scopus_ris': (SCOPUS, '_Scopus.ris'), 'ieee_csv': (IEEE, '_IEEE.csv'), 'ieee_ris': (IEEE, '_IEEE.ris')}
LOOKBACK = timedelta(hours=24)  # files downloaded shortly before the watcher was switched on are included
MAX_BYTES = 200 * 1024 * 1024
SKIP_SUFFIXES = ('.crdownload', '.part', '.tmp', '.download')

SCHEMA = '''
CREATE TABLE IF NOT EXISTS download_files(
 id TEXT PRIMARY KEY, sha256 TEXT UNIQUE NOT NULL, original_path TEXT NOT NULL, original_name TEXT NOT NULL,
 kind TEXT, records INTEGER, state TEXT NOT NULL, run_id TEXT REFERENCES search_runs(id), target_path TEXT,
 message TEXT NOT NULL DEFAULT '', created_at TEXT NOT NULL, updated_at TEXT NOT NULL);
'''


def ensure_schema(store):
    if getattr(store, '_downloads_ready', False):
        return
    with store.lock:
        store.db.executescript(SCHEMA)
        store._downloads_ready = True


def default_folder():
    try:
        from win32com.shell import shell, shellcon
        return Path(shell.SHGetKnownFolderPath(shellcon.FOLDERID_Downloads))
    except Exception:
        return Path(os.environ.get('USERPROFILE') or Path.home()) / 'Downloads'


def folder(store):
    configured = (store.settings().get('downloads_dir') or '').strip()
    return Path(configured) if configured else default_folder()


def _text(raw):
    for encoding in ('utf-8-sig', 'cp1254', 'cp1252'):
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue
    return ''


def classify(name, raw):
    """(kind, record count) for a recognised export, otherwise (None, 0)."""
    suffix = Path(name).suffix.casefold()
    if suffix == '.ris':
        text = _text(raw)
        records = len(re.findall(r'(?m)^TY  -', text))
        if not records:
            return None, 0
        if scopus_eids({'UR': re.findall(r'(?m)^(?:UR|L1|L2|AN|ID)  - (.*)$', text),
                        'N1': re.findall(r'(?m)^N1  - (.*)$', text)}) or re.search(r'(?m)^DB  - Scopus\s*$', text):
            return 'scopus_ris', records
        if 'ieeexplore.ieee.org' in text or re.search(r'(?m)^DB  - IEEE', text):
            return 'ieee_ris', records
        return None, 0
    if suffix == '.csv':
        rows = ieee_csv.read_rows(raw)
        return ('ieee_csv', len(rows)) if rows is not None else (None, 0)
    return None, 0


def _has_export(store, run_id):
    if store.db.execute('SELECT 1 FROM ham_export_files WHERE run_id=? AND excluded=0', (run_id,)).fetchone():
        return True
    ieee_csv.ensure_schema(store)
    return bool(store.db.execute("SELECT 1 FROM ieee_csv_imports WHERE run_id=? AND state='converted'", (run_id,)).fetchone())


def candidates(store, kind, records):
    """Searches this file can belong to, most recently captured first."""
    database = KINDS[kind][0]
    rows = store.db.execute(
        "SELECT * FROM search_runs WHERE database_name=? AND count_qualifier='exact' AND count_value=? "
        "AND id NOT IN (SELECT run_id FROM search_refinements WHERE state='captured') ORDER BY observed_at_utc DESC, display_id DESC",
        (database, records)).fetchall()
    return [dict(r) for r in rows if not _has_export(store, r['id'])]


def _export_hashes(store):
    root = store.path(EXPORT_DIR)
    found = {}
    if root.is_dir():
        for file in list(root.glob('*.ris')) + list(root.glob('*.csv')) + list(root.glob('_aktarilmayacak/*')):
            try:
                if file.is_file() and file.stat().st_size <= MAX_BYTES:
                    found[hashlib.sha256(file.read_bytes()).hexdigest()] = file.name
            except OSError:
                continue
    return found


def _free(store, name):
    stem, suffix = name.rsplit('.', 1)
    candidate, n = name, 1
    while store.path(f'{EXPORT_DIR}/{candidate}').exists():
        n += 1
        candidate = f'{stem}_{n}.{suffix}'
    return candidate


def _retry(action, attempts=10, wait=0.3):
    """Windows Defender and Explorer briefly lock freshly downloaded files; try again before giving up."""
    for attempt in range(attempts):
        try:
            return action()
        except PermissionError:
            if attempt == attempts - 1:
                raise
            time.sleep(wait)


def _move(store, source, name, sha):
    """Copy into 01_HamExport, verify, then remove the download. Never overwrites."""
    target = store.path(f'{EXPORT_DIR}/{name}')
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_name(target.name + '.' + uuid.uuid4().hex + '.tmp')
    _retry(lambda: shutil.copyfile(source, temporary))
    if hashlib.sha256(temporary.read_bytes()).hexdigest() != sha:
        temporary.unlink()
        raise ValidationError('Kopya doğrulanamadı; dosya taşınmadı.')
    if target.exists():
        temporary.unlink()
        raise FileExistsError(target)
    _retry(lambda: os.rename(temporary, target))
    try:
        _retry(lambda: os.remove(source))
        return ''
    except OSError:
        return ' İndirilenler klasöründeki özgün dosya silinemedi (açık olabilir).'


def _place(store, entry, run, source, raw_sha, kind, records):
    name = _free(store, run['display_id'] + KINDS[kind][1])
    note = _move(store, source, name, raw_sha)
    if kind != 'ieee_csv':  # the CSV watcher records the CSV and its RIS itself
        info = store.export_info(run['id'])
        files = [x.strip() for x in re.split(r'[;\n]+', info.get('export_files') or '') if x.strip()]
        if name not in files:
            store.update_run(run['id'], {'export_files': '; '.join(files + [name])})
    message = f"{source.name} → {name} ({records} kayıt).{note}"
    with store.lock, store.db:
        store.db.execute("UPDATE download_files SET state='moved',run_id=?,target_path=?,message=?,updated_at=? WHERE id=?",
                         (run['id'], f'{EXPORT_DIR}/{name}', message, utcnow(), entry))
        store.audit('download_moved', run['id'], {'from': str(source), 'to': name, 'records': records, 'kind': kind})
    return {'state': 'moved', 'run': run['display_id'], 'file': source.name, 'target': name, 'records': records,
            'kind': kind, 'message': f"{run['display_id']}: {message}"}


def handle(store, source):
    """Look at one downloaded file once. Returns a result dict for recognised exports, else None."""
    ensure_schema(store)
    raw = source.read_bytes()
    sha = hashlib.sha256(raw).hexdigest()
    with store.lock:
        if store.db.execute('SELECT 1 FROM download_files WHERE sha256=?', (sha,)).fetchone():
            return None
    kind, records = classify(source.name, raw)
    now, entry = utcnow(), str(uuid.uuid4())
    state, message = 'ignored', ''
    existing = _export_hashes(store).get(sha) if kind else None
    if existing:
        message = f'Aynı dosya 01_HamExport içinde zaten var ({existing}); dokunulmadı.'
    with store.lock, store.db:
        store.db.execute('INSERT INTO download_files VALUES(?,?,?,?,?,?,?,?,?,?,?,?)',
                         (entry, sha, str(source), source.name, kind, records, 'ignored' if not kind or existing else 'needs_run',
                          None, None, message, now, now))
    if not kind or existing:
        return None
    with store.lock:
        matches = candidates(store, kind, records)
    if len(matches) == 1:
        return _place(store, entry, matches[0], source, sha, kind, records)
    database = KINDS[kind][0]
    message = (f'{records} kayıtlı {database} dosyası için {len(matches)} uygun arama var; Arama kayıtları → İndirilenler bölümünden seçin.'
               if matches else
               f'{records} kayıtlı {database} dosyası hiçbir aramayla eşleşmedi (dışa aktarılmamış ve sonuç sayısı aynı arama yok). '
               'Arama kayıtları → İndirilenler bölümünden seçebilirsiniz.')
    with store.lock, store.db:
        store.db.execute('UPDATE download_files SET message=? WHERE id=?', (message, entry))
        store.audit('download_waiting', entry, {'file': source.name, 'records': records, 'kind': kind,
                                                'candidates': [m['display_id'] for m in matches]})
    return {'state': 'needs_run', 'file': source.name, 'records': records, 'kind': kind, 'message': message,
            'candidates': [m['display_id'] for m in matches]}


def list_entries(store):
    ensure_schema(store)
    with store.lock:
        out = []
        for row in store.db.execute("SELECT d.*, r.display_id FROM download_files d LEFT JOIN search_runs r ON r.id=d.run_id "
                                    "WHERE d.state!='ignored' ORDER BY d.created_at DESC LIMIT 100"):
            item = dict(row)
            if item['state'] == 'needs_run':
                item['missing'] = not Path(item['original_path']).exists()
                item['candidates'] = [r['display_id'] for r in candidates(store, item['kind'], item['records'])]
                item['runs'] = [r[0] for r in store.db.execute(
                    'SELECT display_id FROM search_runs WHERE database_name=? ORDER BY display_id', (KINDS[item['kind']][0],))]
            out.append(item)
        return out


def assign(store, entry, display_id):
    """The user's choice for a file that could not be matched on its own."""
    ensure_schema(store)
    with store.lock:
        row = store.db.execute('SELECT * FROM download_files WHERE id=?', (str(entry),)).fetchone()
        if not row or row['state'] != 'needs_run':
            raise ValidationError('Bu dosya zaten işlendi veya bulunamadı.')
        run = store.get_run(str(display_id))
        if run['database_name'] != KINDS[row['kind']][0]:
            raise ValidationError(f"Bu dosya {KINDS[row['kind']][0]} dışa aktarımı; aynı veritabanından bir arama seçin.")
    source = Path(row['original_path'])
    if not source.exists():
        raise ValidationError('Dosya İndirilenler klasöründe bulunamadı.')
    if hashlib.sha256(source.read_bytes()).hexdigest() != row['sha256']:
        raise ValidationError('Dosya değişmiş; yeniden indirin.')
    result = _place(store, row['id'], run, source, row['sha256'], row['kind'], row['records'])
    if run['count_value'] != row['records']:
        result['warning'] = f"Dosyada {row['records']} kayıt var, {run['display_id']} {run['count_value']} sonuç gösteriyor."
    return result


class DownloadsWatcher(threading.Thread):
    """Polls the Downloads folder while the project setting is on; a file is read only after it stops changing."""

    def __init__(self, get_store, notify, interval=3.0, on_change=None, guard=None):
        super().__init__(daemon=True, name='downloads-watcher')
        self.get_store, self.notify, self.interval, self.on_change = get_store, notify, interval, on_change
        self.guard = guard or threading.RLock()
        self.stop_event, self.wake = threading.Event(), threading.Event()
        self.sizes = {}

    def stop(self):
        self.stop_event.set()
        self.wake.set()

    def poke(self):
        self.wake.set()

    def poll(self):
        with self.guard:
            return self._poll(self.get_store())

    def _poll(self, store):
        settings = store.settings()
        if not settings.get('downloads_watch'):
            return []
        root = folder(store)
        if not root.is_dir():
            return []
        try:
            since = datetime.fromisoformat(settings.get('downloads_since') or '').timestamp()
        except ValueError:
            since = (datetime.now(timezone.utc) - LOOKBACK).timestamp()
        results = []
        for file in sorted(root.iterdir()):
            name = file.name.casefold()
            if name.endswith(SKIP_SUFFIXES) or Path(name).suffix not in ('.ris', '.csv'):
                continue
            try:
                stat = file.stat()
            except OSError:
                continue
            if not file.is_file() or stat.st_mtime < since or stat.st_size == 0 or stat.st_size > MAX_BYTES:
                continue
            key = (stat.st_size, stat.st_mtime_ns)
            if self.sizes.get(str(file)) != key:
                self.sizes[str(file)] = key  # wait one more round for a finished download
                continue
            try:
                result = handle(store, file)
            except PermissionError:
                continue
            except Exception:
                logging.exception('Downloaded file could not be handled: %s', file.name)
                continue
            if result:
                results.append(result)
        if results and self.on_change:
            self.on_change(store)
        return results

    def run(self):
        while not self.stop_event.is_set():
            try:
                for result in self.poll():
                    self.notify(result['message'], result.get('run', ''))
            except Exception:
                logging.exception('Downloads watcher round failed.')
            self.wake.wait(self.interval)
            self.wake.clear()


def lookback_start():
    return (datetime.now(timezone.utc) - LOOKBACK).isoformat()
