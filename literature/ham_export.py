"""Record counts of the RIS files in 01_HamExport, so Excel's "Dışa aktarılan kayıt sayısı" fills itself.

A file is attributed to a search by its name prefix (S005_Scopus.ris, S020_IEEE.ris, S007_Scopus_2.ris).
Files in 01_HamExport/_aktarilmayacak are searches deliberately not exported: they count as 0.
The files are only read; nothing is renamed, moved or rewritten here.
"""
import re
import time

from .storage import utcnow

FOLDER = '01_HamExport'
SKIPPED = '_aktarilmayacak'
NAME = re.compile(r'^(S\d{3,})_.*\.ris$', re.I)


def count_records(path):
    count = 0
    with open(path, 'rb') as f:
        for line in f:
            if line.startswith(b'\xef\xbb\xbf'):
                line = line[3:]
            if line.startswith(b'TY  -'):
                count += 1
    return count


def _files(store):
    root = store.path(FOLDER)
    for folder, skipped in ((root, 0), (root / SKIPPED, 1)):
        if not folder.is_dir():
            continue
        for file in folder.iterdir():
            match = NAME.match(file.name)
            if match and file.is_file():
                yield file, skipped, match[1].upper()


def scan(store, settle=2.0):
    """Updates ham_export_files; returns True when anything changed. A file still being written
    (modified in the last `settle` seconds) is left for the next round."""
    changed = False
    with store.lock:
        known = {r['relative_path']: dict(r) for r in store.db.execute('SELECT * FROM ham_export_files')}
        seen = set()
        for file, skipped, code in _files(store):
            relative = file.relative_to(store.root).as_posix()
            seen.add(relative)
            try:
                stat = file.stat()
            except OSError:
                continue
            row = store.db.execute('SELECT id FROM search_runs WHERE display_id=?', (code,)).fetchone()
            run_id = row[0] if row else None
            old = known.get(relative)
            if old and (old['size'], old['mtime_ns'], old['excluded'], old['run_id']) == (stat.st_size, stat.st_mtime_ns, skipped, run_id):
                continue
            if time.time() - stat.st_mtime < settle:
                continue
            try:
                records = count_records(file)
            except OSError:
                continue
            with store.db:
                store.db.execute('INSERT OR REPLACE INTO ham_export_files VALUES(?,?,?,?,?,?,?)',
                                 (relative, run_id, records, skipped, stat.st_size, stat.st_mtime_ns, utcnow()))
            changed = True
        gone = set(known) - seen
        if gone:
            with store.db:
                store.db.executemany('DELETE FROM ham_export_files WHERE relative_path=?', [(g,) for g in gone])
            changed = True
    return changed
