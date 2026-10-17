"""Scopus and IEEE RIS files in 01_HamExport → Zotero, one item per publication.

Every search whose export lies in 01_HamExport (not in _aktarilmayacak) is imported into its own collection
00_AramaKayitlari › S0xx_Scopus / S0xx_IEEE and into 01_Aday. A publication found by several searches or
databases (same DOI, else same title) becomes a single Zotero item that sits in all of their collections, so
the duplicates CEN401 Adım 6 asks to merge are never created; ACM items already in the library are reused.
"""
import json
import logging
import threading
from pathlib import Path

from .ris import parse_ris
from .storage import ValidationError, json_text, utcnow

PLATFORMS = {'Scopus': 'Scopus', 'IEEE Xplore': 'IEEE'}
SCHEMA = '''
CREATE TABLE IF NOT EXISTS zotero_ris_imports(
 run_id TEXT PRIMARY KEY REFERENCES search_runs(id), display_id TEXT NOT NULL, files TEXT NOT NULL,
 records INTEGER NOT NULL, unique_items INTEGER, created INTEGER, reused INTEGER, failed INTEGER,
 skipped INTEGER, failures_json TEXT NOT NULL DEFAULT '[]', updated_at TEXT NOT NULL);
'''


def ensure_schema(store):
    if getattr(store, '_zotero_ris_ready', False):
        return
    with store.lock:
        store.db.executescript(SCHEMA)
        store._zotero_ris_ready = True


def plan(store):
    """Searches with RIS files to import, in S-code order."""
    with store.lock:
        rows = store.db.execute(
            "SELECT r.id, r.display_id, r.database_name, r.count_value, f.relative_path, f.record_count FROM ham_export_files f "
            "JOIN search_runs r ON r.id=f.run_id WHERE f.excluded=0 AND lower(f.relative_path) LIKE '%.ris' "
            "ORDER BY r.display_id, f.relative_path").fetchall()
    searches = {}
    for row in rows:
        if row['database_name'] not in PLATFORMS:
            continue
        entry = searches.setdefault(row['id'], {'search_id': row['id'], 'display_id': row['display_id'],
                                                'label': PLATFORMS[row['database_name']], 'count': row['count_value'],
                                                'files': [], 'records': 0})
        entry['files'].append(row['relative_path'])
        entry['records'] += row['record_count']
    return list(searches.values())


def status(store):
    ensure_schema(store)
    with store.lock:
        done = {r['run_id']: dict(r) for r in store.db.execute('SELECT * FROM zotero_ris_imports')}
    rows = []
    for entry in plan(store):
        result = done.get(entry['search_id'])
        rows.append({'display_id': entry['display_id'], 'label': entry['label'], 'files': [Path(f).name for f in entry['files']],
                     'records': entry['records'], 'imported': bool(result), **({k: result[k] for k in (
                         'unique_items', 'created', 'reused', 'failed', 'skipped', 'updated_at')} if result else {})})
    return rows


def run(store, writer, progress=lambda text: None, check_cancel=lambda: None):
    """Parse every planned RIS and import; returns (summary text, per-search results)."""
    ensure_schema(store)
    searches = []
    for entry in plan(store):
        records, skipped = [], []
        for relative in entry['files']:
            records += parse_ris(store.path(relative).read_bytes(), require_eid=False, skipped=skipped)
        searches.append(dict(entry, records=records, skipped=skipped))
    if not searches:
        raise ValidationError("01_HamExport'ta Zotero'ya aktarılacak Scopus/IEEE RIS dosyası yok.")
    progress(f"{len(searches)} arama, {sum(len(s['records']) for s in searches)} kayıt okunuyor…")
    results = writer.import_papers(searches, check_cancel=check_cancel, progress=progress)
    keys = set()
    with store.lock, store.db:
        for search, result in zip(searches, results):
            keys |= result['keys']
            store.db.execute('INSERT OR REPLACE INTO zotero_ris_imports VALUES(?,?,?,?,?,?,?,?,?,?,?)',
                             (search['search_id'], search['display_id'], json_text([Path(f).name for f in search['files']]),
                              len(search['records']) + len(search['skipped']), len(result['keys']), result['created'], result['reused'],
                              result['failed'], len(search['skipped']), json_text(result['failures'][:50]), utcnow()))
        store.audit('zotero_ris_import', 'TEZ', {'searches': len(results), 'records': sum(r['records'] for r in results),
                                                 'items': len(keys), 'failed': sum(r['failed'] for r in results)})
    records = sum(r['records'] for r in results)
    failed = sum(r['failed'] for r in results)
    skipped = sum(len(s['skipped']) for s in searches)
    created = len({k for r in results for k in r['keys']} )
    text = (f"Zotero aktarımı bitti: {len(results)} arama, {records} kayıt → {created} tekil Zotero öğesi "
            f"({records - created} tekrar ayrı öğe olarak eklenmedi). "
            f"Yeni: {sum(r['created'] for r in results)}, zaten vardı: {sum(r['reused'] for r in results)}"
            f"{f', hata: {failed}' if failed else ''}{f', okunamayan kayıt: {skipped}' if skipped else ''}.")
    return text, results


class ImportJob:
    """One import at a time, in the background; the manager polls `state()`."""

    def __init__(self, notify):
        self.notify = notify
        self.thread = None
        self.lines = []
        self.summary = ''
        self.error = ''

    @property
    def running(self):
        return bool(self.thread and self.thread.is_alive())

    def start(self, store, writer, on_done=lambda store: None):
        if self.running:
            raise ValidationError('Zotero aktarımı zaten çalışıyor.')
        self.lines, self.summary, self.error = [], '', ''

        def work():
            try:
                self.summary, _ = run(store, writer, progress=self._progress)
                self.notify(self.summary, '')
                on_done(store)
            except Exception as error:
                logging.exception('RIS → Zotero import failed.')
                self.error = str(error)
                self.notify('Zotero aktarımı durdu: ' + self.error + ' Yeniden başlatınca kaldığı yerden devam eder.', '')

        self.thread = threading.Thread(target=work, daemon=True, name='zotero-ris-import')
        self.thread.start()
        return self.state()

    def _progress(self, text):
        self.lines = (self.lines + [text])[-12:]

    def state(self):
        return {'running': self.running, 'lines': list(self.lines), 'summary': self.summary, 'error': self.error}
