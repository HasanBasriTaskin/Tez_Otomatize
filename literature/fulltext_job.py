"""Manager-side view of the full-text decisions and reading notes, and the background job that applies them to Zotero."""
import json
import logging
import threading
from collections import Counter

from . import fulltext, zotero_fixes
from .storage import ValidationError

RELATIVE = fulltext.RELATIVE.as_posix()


def mirror(store):
    """Items in 02_BaslikOzet_Gecen / 03_TamMetin_Dahil / 04_Haric_TamMetin as last read from Zotero."""
    settings = store.settings()
    library = settings.get('library', '')
    mapping = settings.get('collection_mapping', {})
    relevant_collections = {mapping.get(r) for r in ('title_abstract', 'included', 'excluded', 'candidate') if mapping.get(r)}
    titles, states, tags = {}, Counter(), Counter()
    with store.lock:
        rows = store.db.execute("SELECT item_key,state,data_json FROM papers WHERE library_id=? AND state!='unavailable'",
                                (library,)).fetchall()
    for row in rows:
        data = json.loads(row['data_json'])
        cols = set(data.get('collections', []))
        if not relevant_collections or (cols & relevant_collections):
            titles[row['item_key']] = data.get('title', '')
            if row['state'] in ('title_passed', 'included', 'excluded'):
                states[row['state']] += 1
                for tag in data.get('tags', []):
                    if isinstance(tag, dict) and tag.get('tag') in (*fulltext.TAGS.values(), *fulltext.CODES):
                        tags[tag['tag']] += 1
    return titles, {'durumlar': dict(states), 'etiketler': dict(tags)}


def reading_warnings(store, data):
    """Reading dates earlier than the search that found the paper (Kılavuz Adım 4: records are kept as the work is done)."""
    from datetime import datetime
    from zoneinfo import ZoneInfo
    from .exports import _note_date
    from .zotero import parse_note
    found = {}
    for run in store.list_runs():
        try:
            found[run['display_id']] = datetime.fromisoformat(str(run['observed_at_utc']).replace('Z', '+00:00')).astimezone(ZoneInfo('Europe/Istanbul')).date()
        except (TypeError, ValueError):
            pass
    library = store.settings().get('library', '')
    warnings = []
    for r in data['kayitlar']:
        if r.get('durum') != 'Dahil':
            continue
        read = _note_date(parse_note(fulltext.note_text_for(r, store.root)).get('Okuma tarihi', ''))
        with store.lock:
            row = store.db.execute('SELECT id FROM papers WHERE library_id=? AND item_key=?', (library, r['key'])).fetchone()
            codes = store.paper_search_codes(row['id']) if row else []
        dates = [found[c] for c in codes if c in found]
        if read and dates and read < min(dates):
            warnings.append(f"{r.get('matris_id') or r['key']}: okuma tarihi {read.strftime('%d.%m.%Y')}, kaynağın bulunduğu "
                            f"ilk arama {min(dates).strftime('%d.%m.%Y')}.")
    return warnings


def status(store, job=None):
    path = store.path(RELATIVE)
    result = {'path': str(path), 'exists': path.is_file(), 'job': job.state() if job else None}
    if not result['exists']:
        return result
    data = fulltext.load(path)
    titles, zotero = mirror(store)
    problems = fulltext.check(data, titles, store.root) if titles else ["Önce Zotero bölümünde \"Zotero'dan oku\" düğmesine basın."]
    counts = fulltext.counts(data, store.root)
    states = zotero['durumlar']
    dig = fulltext.digest(data, store.root)
    with store.lock:
        applied = dict(store.db.execute('SELECT state,COUNT(*) FROM fulltext_applications WHERE digest=? GROUP BY state',
                                        (dig,)).fetchall())
    spare_total = max(0, (states.get('title_passed', 0) + states.get('included', 0) + states.get('excluded', 0))
                      - counts['dahil'] - counts['haric'])
    counts['yedek'] = spare_total
    try:
        fixes = zotero_fixes.summary(zotero_fixes.load(store.root))
    except ValidationError as error:
        fixes = {'kunye': 0, 'bos_koleksiyon': 0}
        problems.append(str(error))
    with store.lock:
        attached = dict(store.db.execute('SELECT state,COUNT(*) FROM pdf_attachments GROUP BY state').fetchall())
    result.update(
        pdf=len(fulltext.pdf_entries(data, store.root)), pdf_zotero=attached, fixes=fixes,
        warnings=reading_warnings(store, data),
        counts=counts, problems=problems[:20], problem_count=len(problems),
        approved=fulltext.approved(data, store.root),
        approval=fulltext.approval_state(data, store.root),
        plan=fulltext.summary(fulltext.plan(data, store.root)),
        zotero=zotero, applied=applied,
        in_zotero=bool(titles) and states.get('included', 0) == counts['dahil']
        and states.get('excluded', 0) == counts['haric'])
    return result


def approve(store, confirmed):
    if confirmed is not True:
        raise ValidationError('Onay kutusunu işaretleyin.')
    data = fulltext.load(store.path(RELATIVE))
    if fulltext.approved(data, store.root):
        raise ValidationError('Tam metin kararları ve okuma notları zaten onaylı.')
    titles, _ = mirror(store)
    if not titles:
        raise ValidationError("Önce Zotero bölümünde \"Zotero'dan oku\" düğmesine basın.")
    return fulltext.approve(store.path(RELATIVE), store.settings().get('operator', ''), titles,
                            store.path('Yedekler'), root=store.root)


class ApplyJob:
    """One full-text application at a time, in the background; the manager polls `state()`."""

    def __init__(self, notify):
        self.notify = notify
        self.thread = None
        self.lines = []
        self.summary = ''
        self.error = ''

    @property
    def running(self):
        return bool(self.thread and self.thread.is_alive())

    def start(self, store, writer, on_done=lambda store: ''):
        if self.running:
            raise ValidationError('Tam metin ve okuma notları zaten uygulanıyor.')
        data = fulltext.load(store.path(RELATIVE))
        if not fulltext.approved(data, store.root):
            raise ValidationError('Tam metin kararları veya okuma notları onaylanmadı ya da onaydan sonra değişti; önce onaylayın.')
        self.lines, self.summary, self.error = [], '', ''

        def work():
            try:
                r = writer.apply_fulltext(data, root=store.root, progress=self._progress)
                fixes = zotero_fixes.load(store.root)
                c = writer.apply_corrections(zotero_fixes.corrections(fixes), progress=self._progress)
                p = writer.attach_pdfs(fulltext.pdf_entries(data, store.root), progress=self._progress)
                e = writer.remove_empty_collections(zotero_fixes.empty_collections(fixes), progress=self._progress)
                failed = r['failed'] + c['failed'] + p['failed'] + e['failed']
                parts = [f"{r['included']} dahil kayıt 03_TamMetin_Dahil'de, {r['excluded']} H3 kaydı 04_Haric_TamMetin'de",
                         f"okuma notları: {r['notes_created']} yeni, {r['notes_existing']} zaten vardı",
                         f"PDF ekleri: {p['uploaded']} yüklendi, {p['existing']} zaten ekliydi"]
                if c['corrections']:
                    parts.append(f"künye düzeltmeleri: {c['updated']} yazıldı, {c['unchanged']} zaten doğruydu")
                if e['collections']:
                    parts.append(f"boş koleksiyonlar: {e['removed']} silindi, {e['absent']} zaten yoktu")
                self.summary = 'Tamamlandı — ' + '; '.join(parts) + '.'
                if failed:
                    details = [f"{x['key']}: {x['error']}" for x in (r['failures'] + c['failures'] + p['failures'] + e['failures'])[:5]]
                    self.summary += f' Yazılamayan {failed} işlem var ({"; ".join(details)}). Yeniden başlatınca kaldığı yerden devam eder.'
                after = on_done(store)
                if after:
                    self.summary += ' ' + after
                self.notify(self.summary, '')
            except Exception as error:
                logging.exception('Full-text application failed.')
                self.error = str(error)
                self.notify('Tam metin kararları uygulanamadı: ' + self.error + ' Yeniden başlatınca kaldığı yerden devam eder.', '')

        self.thread = threading.Thread(target=work, daemon=True, name='fulltext-apply')
        self.thread.start()
        return self.state()

    def _progress(self, text):
        self.lines = (self.lines + [text])[-12:]

    def state(self):
        return {'running': self.running, 'lines': list(self.lines), 'summary': self.summary, 'error': self.error}
