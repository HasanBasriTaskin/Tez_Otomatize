"""Manager-side view of the full-text decisions and reading notes, and the background job that applies them to Zotero."""
import json
import logging
import threading
from collections import Counter

from . import fulltext
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
    counts['yedek'] = spare_total or 177
    result.update(
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
                existing = f", {r['notes_existing']} zaten vardı" if r['notes_existing'] else ''
                failures = f", hata: {r['failed']}" if r['failed'] else ''
                self.summary = (f"Tamamlandı — {r['included']} dahil (03_TamMetin_Dahil) ve {r['excluded']} H3 hariç "
                                f"(04_Haric_TamMetin) kaydı Zotero'ya işlendi ({r['updated']} güncellendi, "
                                f"{r['unchanged']} zaten işlenmişti, not: {r['notes_created']} yeni{existing}{failures}); "
                                f"literatür matrisi güncellendi.")
                if r['failed']:
                    self.summary += ' Hatalı kayıtlar için yeniden başlatın; kaldığı yerden devam eder.'
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
