"""IEEE Xplore "Export → Search Results → CSV" files → RIS, matched to the right IEEE search record.

IEEE's Citations/RIS export only covers the records ticked on the current page (selection does not
accumulate across pages); the Results CSV covers the whole result list. The user drops the CSV,
unrenamed, into 01_HamExport; the watcher matches it to a captured IEEE search (S0xx), renames it to
S0xx_IEEE.csv and writes S0xx_IEEE.ris with the tags of IEEE's own RIS export (checked field by field
against 94 records of a real IEEE RIS download on 16.10.2026).
"""
import csv
import hashlib
import io
import json
import logging
import re
import threading
import time
import uuid

from . import ham_export
from .storage import ValidationError, json_text, utcnow

EXPORT_DIR = '01_HamExport'
REQUIRED = ('Document Title', 'Authors', 'Publication Title', 'Publication Year', 'Abstract', 'DOI',
            'Document Identifier')
NAMED = re.compile(r'^(S\d{3,})_IEEE(?:_\d+)?\.csv$', re.I)
SCHEMA = '''
CREATE TABLE IF NOT EXISTS ieee_csv_imports(
 id TEXT PRIMARY KEY, sha256 TEXT UNIQUE NOT NULL, original_name TEXT NOT NULL, csv_path TEXT NOT NULL,
 ris_path TEXT, row_count INTEGER NOT NULL, run_id TEXT REFERENCES search_runs(id), state TEXT NOT NULL,
 message TEXT NOT NULL DEFAULT '', created_at TEXT NOT NULL, updated_at TEXT NOT NULL);
'''


def ensure_schema(store):
    if getattr(store, '_ieee_csv_ready', False):
        return
    with store.lock:
        store.db.executescript(SCHEMA)
        store._ieee_csv_ready = True


def _decode(raw):
    for encoding in ('utf-8-sig', 'cp1254', 'cp1252'):
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue
    raise ValidationError('CSV kodlaması okunamadı.')


def read_rows(raw):
    """Returns the rows of an IEEE results CSV, or None when the file is not one."""
    reader = csv.DictReader(io.StringIO(_decode(raw), newline=''))
    header = [h.strip() for h in (reader.fieldnames or [])]
    if not all(name in header for name in REQUIRED):
        return None
    reader.fieldnames = header
    return [{k: (v or '').strip() for k, v in row.items() if k} for row in reader
            if any((v or '').strip() for k, v in row.items() if k)]


def _split(value):
    return [part.strip() for part in value.split(';') if part.strip()]


def ris_type(identifier):
    text = identifier.casefold()
    if 'conference' in text:
        return 'CONF'
    if 'journal' in text or 'magazine' in text or 'early access' in text:
        return 'JOUR'
    if 'book' in text or 'course' in text:
        return 'BOOK'
    if 'standard' in text:
        return 'STAND'
    return 'GEN'


def _clean(value):
    return re.sub(r'[\r\n]+', ' ', value).strip()


def record(row):
    """One RIS record in IEEE's own tag order (TY TI T2 SP EP AU PY KW DO JO IS SN VO VL JA Y1 AB),
    plus PB, which IEEE's RIS leaves out but the CSV carries."""
    venue = _clean(row.get('Publication Title', ''))
    lines = [('TY', ris_type(row.get('Document Identifier', ''))), ('TI', _clean(row.get('Document Title', ''))),
             ('T2', venue), ('SP', row.get('Start Page', '')), ('EP', row.get('End Page', ''))]
    lines += [('AU', name) for name in _split(row.get('Authors', ''))]
    lines.append(('PY', row.get('Publication Year', '')))
    lines += [('KW', word) for word in _split(row.get('IEEE Terms', '')) + _split(row.get('Author Keywords', ''))]
    lines += [('DO', row.get('DOI', '')), ('JO', venue), ('IS', row.get('Issue', '')), ('SN', row.get('ISSN', '')),
              ('VO', row.get('Volume', '')), ('VL', row.get('Volume', '')), ('JA', venue),
              ('Y1', row.get('Meeting Date') or row.get('Issue Date') or row.get('Publication Year', '')),
              ('AB', _clean(row.get('Abstract', '')))]
    if row.get('Publisher'):
        lines.append(('PB', _clean(row['Publisher'])))
    return ''.join(f'{tag}  - {_clean(str(value))}\n' for tag, value in lines) + 'ER  - \n'


def to_ris(rows):
    return '\n'.join(record(row) for row in rows) + '\n'


def _years(run):
    from .refinement import ieee_filters
    try:
        filters = json.loads(run.get('filters_json') or '[]')
    except ValueError:
        filters = []
    _, applied, natural = ieee_filters(filters)
    return applied or natural


def _fits(rows, run):
    years = _years(run)
    if not years:
        return True
    found = [int(r['Publication Year']) for r in rows if r.get('Publication Year', '').isdigit()]
    return all(years[0] <= y <= years[1] for y in found)


def candidates(store, rows):
    """IEEE searches this CSV can belong to: same exact result count, not yet given a CSV, not superseded
    by a captured narrowing step, and no publication year outside the search's year range."""
    ensure_schema(store)
    found = []
    for run in store.db.execute(
            "SELECT * FROM search_runs WHERE database_name='IEEE Xplore' AND count_qualifier='exact' AND count_value=? "
            "AND id NOT IN (SELECT run_id FROM ieee_csv_imports WHERE run_id IS NOT NULL AND state='converted') "
            "AND id NOT IN (SELECT run_id FROM search_refinements WHERE state='captured') ORDER BY display_id",
            (len(rows),)):
        run = dict(run)
        if _fits(rows, run):
            found.append(run)
    return found


def _free(store, name):
    stem, suffix = name.rsplit('.', 1)
    candidate, n = name, 1
    while store.path(f'{EXPORT_DIR}/{candidate}').exists():
        n += 1
        candidate = f'{stem}_{n}.{suffix}'
    return candidate


def _convert(store, entry, rows, run, source):
    """Rename the CSV to S0xx_IEEE.csv and write S0xx_IEEE.ris beside it; never overwrites a file."""
    code = run['display_id']
    named = NAMED.match(source.name)
    csv_name = source.name if named and named[1].upper() == code else _free(store, f'{code}_IEEE.csv')
    ris_name = _free(store, csv_name[:-4] + '.ris')
    target = store.path(f'{EXPORT_DIR}/{csv_name}')
    if target != source:
        source.rename(target)
    ris = store.path(f'{EXPORT_DIR}/{ris_name}')
    with open(ris, 'x', encoding='utf-8', newline='\n') as f:
        f.write(to_ris(rows))
    now = utcnow()
    info = store.export_info(run['id'])
    files = [x for x in re.split(r'[;\n]+', info.get('export_files') or '') if x.strip()]
    files = [x.strip() for x in files] + [n for n in (csv_name, ris_name) if n not in files]
    store.update_run(run['id'], {'export_files': '; '.join(files)})
    with store.lock, store.db:
        store.db.execute("UPDATE ieee_csv_imports SET csv_path=?,ris_path=?,run_id=?,state='converted',message=?,updated_at=? "
                         "WHERE id=?", (f'{EXPORT_DIR}/{csv_name}', f'{EXPORT_DIR}/{ris_name}', run['id'],
                                        f'{len(rows)} kayıt', now, entry))
        store.audit('ieee_csv_converted', run['id'], {'csv': csv_name, 'ris': ris_name, 'rows': len(rows),
                                                      'original': source.name})
    return {'run': code, 'csv': csv_name, 'ris': ris_name, 'rows': len(rows)}


def process_file(store, source):
    """Handle one CSV in 01_HamExport. Returns a result dict, or None for already known / non-IEEE files."""
    ensure_schema(store)
    raw = source.read_bytes()
    sha = hashlib.sha256(raw).hexdigest()
    with store.lock:
        if store.db.execute('SELECT 1 FROM ieee_csv_imports WHERE sha256=?', (sha,)).fetchone():
            return None
    rows = read_rows(raw)
    now = utcnow()
    entry = str(uuid.uuid4())
    relative = f'{EXPORT_DIR}/{source.name}'
    if rows is None:
        with store.lock, store.db:
            store.db.execute('INSERT INTO ieee_csv_imports VALUES(?,?,?,?,?,?,?,?,?,?,?)',
                             (entry, sha, source.name, relative, None, 0, None, 'ignored', 'IEEE CSV başlıkları yok', now, now))
        return None
    named = NAMED.match(source.name)
    with store.lock:
        if named:
            try:
                run = store.get_run(named[1].upper())
                matches = [run] if run['database_name'] == 'IEEE Xplore' else []
            except ValidationError:
                matches = []
        else:
            matches = candidates(store, rows)
        with store.db:
            store.db.execute('INSERT INTO ieee_csv_imports VALUES(?,?,?,?,?,?,?,?,?,?,?)',
                             (entry, sha, source.name, relative, None, len(rows), None, 'needs_run', '', now, now))
        if len(matches) == 1:
            return dict(_convert(store, entry, rows, matches[0], source), state='converted')
        message = (f'{len(rows)} kayıtlı IEEE CSV için {len(matches)} uygun arama var; eklentide seçin.' if matches else
                   f'{len(rows)} kayıtlı IEEE CSV hiçbir IEEE aramasıyla eşleşmedi (sonuç sayısı aynı olmalı). '
                   f'Eklentide aramayı seçin.')
        with store.db:
            store.db.execute('UPDATE ieee_csv_imports SET message=? WHERE id=?', (message, entry))
            store.audit('ieee_csv_waiting', entry, {'file': source.name, 'rows': len(rows),
                                                    'candidates': [m['display_id'] for m in matches]})
        return {'state': 'needs_run', 'file': source.name, 'rows': len(rows),
                'candidates': [m['display_id'] for m in matches], 'message': message}


def list_imports(store):
    ensure_schema(store)
    with store.lock:
        out = []
        for row in store.db.execute("SELECT i.*, r.display_id FROM ieee_csv_imports i LEFT JOIN search_runs r ON r.id=i.run_id "
                                    "WHERE i.state!='ignored' ORDER BY i.created_at DESC LIMIT 200"):
            item = dict(row)
            if item['state'] == 'needs_run':
                file = store.path(item['csv_path'])
                rows = read_rows(file.read_bytes()) if file.exists() else None
                item['missing'] = rows is None
                item['candidates'] = [r['display_id'] for r in candidates(store, rows)] if rows else []
                item['ieee_runs'] = [r[0] for r in store.db.execute(
                    "SELECT display_id FROM search_runs WHERE database_name='IEEE Xplore' ORDER BY display_id")]
            out.append(item)
        return out


def assign(store, entry, display_id):
    """The user's choice for an unmatched CSV. Any IEEE search may be chosen (e.g. >2,000 results)."""
    ensure_schema(store)
    with store.lock:
        row = store.db.execute('SELECT * FROM ieee_csv_imports WHERE id=?', (entry,)).fetchone()
        if not row or row['state'] != 'needs_run':
            raise ValidationError('Bu CSV zaten işlendi veya bulunamadı.')
        run = store.get_run(str(display_id))
        if run['database_name'] != 'IEEE Xplore':
            raise ValidationError('Yalnız IEEE Xplore aramaları seçilebilir.')
        source = store.path(row['csv_path'])
        if not source.exists():
            raise ValidationError('CSV dosyası 01_HamExport klasöründe bulunamadı.')
        raw = source.read_bytes()
        if hashlib.sha256(raw).hexdigest() != row['sha256']:
            raise ValidationError('CSV dosyası değişmiş; dosyayı klasörden çıkarıp yeniden koyun.')
        rows = read_rows(raw)
        result = _convert(store, entry, rows, run, source)
        if run['count_value'] != len(rows):
            result['warning'] = (f"CSV {len(rows)} kayıt, {run['display_id']} {run['count_value']} sonuç gösteriyor "
                                 f"(IEEE dışa aktarım sınırı olabilir).")
        return result


class CsvWatcher(threading.Thread):
    """Polls <project>/01_HamExport for new CSV files; a file is read only after it stops changing."""

    def __init__(self, get_store, notify, interval=3.0, on_change=None, guard=None):
        super().__init__(daemon=True, name='ieee-csv-watcher')
        self.get_store, self.notify, self.interval, self.on_change = get_store, notify, interval, on_change
        # The application's command lock: a project switch never closes the store under a running conversion.
        self.guard = guard or threading.RLock()
        self.settle = 2.0  # seconds a RIS file must stay unchanged before it is counted
        self.stop_event = threading.Event()
        self.sizes, self.done = {}, set()

    def stop(self):
        self.stop_event.set()

    def poll(self):
        with self.guard:
            return self._poll(self.get_store())

    def _poll(self, store):
        folder = store.path(EXPORT_DIR)
        if not folder.is_dir():
            return []
        results = []
        for file in sorted(folder.glob('*.csv')):
            try:
                stat = file.stat()
            except OSError:
                continue
            key = (str(file), stat.st_size, stat.st_mtime_ns)
            if key in self.done:
                continue
            if self.sizes.get(str(file)) != key or stat.st_size == 0:
                self.sizes[str(file)] = key  # wait one more round for a stable file
                continue
            try:
                result = process_file(store, file)
            except PermissionError:
                continue  # still open in Excel or the browser; retry later
            except Exception:
                logging.exception('IEEE CSV could not be processed: %s', file.name)
                self.done.add(key)
                self.notify(f'{file.name} işlenemedi. Dosyayı kontrol edin.', '')
                continue
            self.done.add(key)
            if result:
                results.append(result)
                if result['state'] == 'converted':
                    self.notify(f"{result['run']}: IEEE CSV → {result['ris']} ({result['rows']} kayıt). "
                                f"CSV {result['csv']} adını aldı.", result['run'])
                else:
                    self.notify(result['message'], '')
                if self.on_change:
                    try:
                        self.on_change(store)
                    except Exception:
                        logging.exception('Excel refresh after IEEE CSV failed.')
        try:
            counted = ham_export.scan(store, self.settle)
        except Exception:
            logging.exception('RIS record count scan failed.')
            counted = False
        if counted and self.on_change:
            try:
                self.on_change(store)
            except Exception:
                logging.exception('Excel refresh after RIS count failed.')
        return results

    def run(self):
        while not self.stop_event.wait(self.interval):
            try:
                self.poll()
            except Exception:
                logging.exception('IEEE CSV watcher round failed.')
