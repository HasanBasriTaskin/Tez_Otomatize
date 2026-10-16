"""Literatur_PDF archive: standard file names and copies of Zotero-stored PDFs.

The archive is a copy. Zotero's own storage is never renamed, moved or deleted.
"""
import os
import re
import unicodedata
from pathlib import Path

from .storage import ValidationError, digest

ARCHIVE_DIR = 'Literatur_PDF'
MATRIX_ID = re.compile(r'L\d{3,}')
TURKISH = str.maketrans({'ç': 'c', 'Ç': 'C', 'ğ': 'g', 'Ğ': 'G', 'ı': 'i', 'İ': 'I', 'ö': 'o', 'Ö': 'O',
                         'ş': 's', 'Ş': 'S', 'ü': 'u', 'Ü': 'U'})
STOPWORDS = {'a', 'an', 'the', 'of', 'for', 'and', 'or', 'in', 'on', 'to', 'with', 'via', 'by', 'from', 'is',
             'are', 'at', 'as', 'its', 'how', 'do', 'does', 'what', 'when', 'into', 'using', 'towards', 'toward',
             've', 'ile', 'icin', 'bir', 'bu'}
TITLE_WORDS = 4
MAX_NAME = 80


def ascii_text(value):
    """Turkish letters and accents to plain ASCII letters/digits."""
    value = str(value or '').translate(TURKISH)
    value = unicodedata.normalize('NFKD', value).encode('ascii', 'ignore').decode('ascii')
    return value


def _token(value):
    return re.sub(r'[^A-Za-z0-9]', '', ascii_text(value))


def first_author(data):
    for creator in data.get('creators', []):
        if creator.get('creatorType', 'author') == 'author':
            return _token(creator.get('lastName') or creator.get('name', '').split(' ')[-1]) or 'Yazar'
    return 'Yazar'


def year_of(data):
    match = re.search(r'\b(19|20)\d{2}\b', str(data.get('date', '')))
    return match.group(0) if match else 'tarihsiz'


def short_title(data):
    title = str(data.get('shortTitle') or data.get('title') or '')
    head = re.split(r'[:?]', title, maxsplit=1)[0] if ':' in title or '?' in title else title
    # A short acronym before the colon ("RAGAs: …") is the best short title.
    if ':' in title and 2 <= len(_token(head)) <= 20 and len(head.split()) <= 2:
        return _token(head)
    words = [w for w in re.split(r'[\s\-–—/]+', ascii_text(title)) if w]
    picked = [w for w in words if w.lower().strip('.,;()') not in STOPWORDS][:TITLE_WORDS]
    return ''.join(_token(w)[:1].upper() + _token(w)[1:] for w in picked) or 'Baslik'


def standard_name(matrix_id, data):
    """`L001_Yazar_Yil_KisaBaslik.pdf`, ASCII only, no spaces."""
    stem = f'{matrix_id}_{first_author(data)}_{year_of(data)}_{short_title(data)}'
    return stem[:MAX_NAME].rstrip('_') + '.pdf'


def clean_name(value):
    """A user-written file name from the note, reduced to a safe single file name."""
    name = Path(str(value or '').strip().replace('\\', '/')).name
    if not name:
        return ''
    stem, suffix = (name[:-4], '.pdf') if name.lower().endswith('.pdf') else (name, '.pdf')
    stem = re.sub(r'[^A-Za-z0-9_.\-]', '_', ascii_text(stem)).strip('._')
    return (stem[:MAX_NAME] + suffix) if stem else ''


def archive_name(fields, data):
    """File name the archive and the matrix use: the note's `Yerel PDF`, else the standard name."""
    own = clean_name(fields.get('Yerel PDF', ''))
    if own:
        return own
    matrix_id = fields.get('Matris ID', '').strip()
    return standard_name(matrix_id, data) if MATRIX_ID.fullmatch(matrix_id) else ''


def zotero_data_dir(settings):
    """Zotero data directory (Zotero → Settings → Advanced → Files and Folders)."""
    configured = str(settings.get('zotero_data_dir') or '').strip()
    return Path(os.path.expandvars(configured)).expanduser() if configured else Path.home() / 'Zotero'


def _source_pdf(storage, attachments):
    for key, filename in attachments:
        folder = storage / key
        if not re.fullmatch(r'[A-Z0-9]{8}', key) or not folder.is_dir():
            continue
        candidate = folder / filename if filename else None
        if candidate and candidate.is_file() and candidate.parent == folder:
            return candidate
        found = sorted(p for p in folder.glob('*.pdf') if p.is_file())
        if found:
            return found[0]
    return None


def build_archive(store):
    """Copy every included paper's Zotero PDF to Literatur_PDF under its matrix name.

    Existing archive files are never overwritten or deleted; differences are reported instead."""
    with store.lock:
        storage = zotero_data_dir(store.settings()) / 'storage'
        if not storage.is_dir():
            raise ValidationError(f'Zotero veri klasörü bulunamadı: {storage.parent}. Zotero → Settings → Advanced → '
                                  'Files and Folders bölümündeki "Data Directory Location" yolunu Ayarlar\'a yazın.')
        target = store.path(ARCHIVE_DIR)
        target.mkdir(parents=True, exist_ok=True)
        report = {'folder': str(target), 'copied': [], 'unchanged': [], 'missing_id': [], 'missing_pdf': [],
                  'conflicts': [], 'multiple_pdfs': [], 'extra_files': []}
        expected = set()
        for paper, data, fields in store.paper_rows('included'):
            label = (fields.get('Matris ID', '').strip() or paper['item_key']) + ' · ' + str(data.get('title', ''))[:80]
            if not MATRIX_ID.fullmatch(fields.get('Matris ID', '').strip()):
                report['missing_id'].append(label)
                continue
            name = archive_name(fields, data)
            if name in expected:
                report['conflicts'].append(f'{label}: {name} adı başka bir kaynakta da kullanılıyor.')
                continue
            expected.add(name)
            attachments = [(r['attachment_key'], r['filename']) for r in store.db.execute(
                'SELECT attachment_key,filename FROM paper_attachments WHERE paper_id=? ORDER BY attachment_key', (paper['id'],))]
            if len(attachments) > 1:
                report['multiple_pdfs'].append(label)
            source = _source_pdf(storage, attachments)
            if not source:
                report['missing_pdf'].append(label)
                continue
            content = source.read_bytes()
            if not content.startswith(b'%PDF'):
                report['missing_pdf'].append(f'{label}: Zotero ekindeki dosya PDF değil.')
                continue
            destination = target / name
            if destination.exists():
                if digest(destination.read_bytes()) == digest(content):
                    report['unchanged'].append(name)
                else:
                    report['conflicts'].append(f'{name}: arşivdeki dosya Zotero\'daki PDF\'ten farklı; üzerine yazılmadı.')
                continue
            store._atomic_write(f'{ARCHIVE_DIR}/{name}', content)
            report['copied'].append(name)
        report['extra_files'] = sorted(p.name for p in target.iterdir()
                                       if p.is_file() and p.suffix.lower() == '.pdf' and p.name not in expected)
        with store.db:
            store.audit('pdf_archive', ARCHIVE_DIR, {k: len(v) for k, v in report.items() if isinstance(v, list)})
        return report
