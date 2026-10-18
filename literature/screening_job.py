"""Manager-side view of the title/abstract decisions file and the background job that applies it to Zotero."""
import json
import logging
import threading
from collections import Counter

from . import screening
from .storage import ValidationError

RELATIVE = screening.RELATIVE.as_posix()


def mirror(store):
    """01_Aday as last read from Zotero ({key: title}) and the screening state of those items in the local mirror."""
    settings = store.settings()
    library = settings.get('library', '')
    candidate = settings.get('collection_mapping', {}).get('candidate', '')
    titles, states, tags = {}, Counter(), Counter()
    with store.lock:
        rows = store.db.execute("SELECT item_key,state,data_json FROM papers WHERE library_id=? AND state!='unavailable'",
                                (library,)).fetchall()
    for row in rows:
        data = json.loads(row['data_json'])
        if candidate and candidate in data.get('collections', []):
            titles[row['item_key']] = data.get('title', '')
            states[row['state']] += 1
            for tag in data.get('tags', []):
                if isinstance(tag, dict) and tag.get('tag') in screening.TAGS.values():
                    tags[tag['tag']] += 1
    return titles, {'durumlar': dict(states), 'etiketler': dict(tags)}


def status(store, job=None):
    path = store.path(RELATIVE)
    result = {'path': str(path), 'exists': path.is_file(), 'job': job.state() if job else None}
    if not result['exists']:
        return result
    data = screening.load(path)
    titles, zotero = mirror(store)
    problems = screening.check(data, titles) if titles else ["Önce Zotero bölümünde \"Zotero'dan oku\" düğmesine basın."]
    counts = screening.counts(data)
    states = zotero['durumlar']
    with store.lock:
        applied = dict(store.db.execute('SELECT state,COUNT(*) FROM screening_applications WHERE digest=? GROUP BY state',
                                        (screening.digest(data),)).fetchall())
    passed_in_zotero = states.get('title_passed', 0) + states.get('included', 0) + states.get('excluded', 0)
    result.update(
        counts=counts, problems=problems[:20], problem_count=len(problems), approved=screening.approved(data),
        approval=screening.approval_state(data), plan=screening.summary(screening.plan(data)), zotero=zotero,
        applied=applied,
        in_zotero=bool(titles) and states.get('excluded_title', 0) == counts['haric']
        and passed_in_zotero == counts['gecen'])
    return result


def approve(store, confirmed):
    if confirmed is not True:
        raise ValidationError('Önce "Kararları kontrol ettim" kutusunu işaretleyin.')
    if screening.approved(screening.load(store.path(RELATIVE))):
        raise ValidationError('Kararlar zaten onaylı.')
    titles, _ = mirror(store)
    if not titles:
        raise ValidationError("Önce Zotero bölümünde \"Zotero'dan oku\" düğmesine basın.")
    return screening.approve(store.path(RELATIVE), store.settings().get('operator', ''), titles, store.path('Yedekler'))


class ApplyJob:
    """One application at a time, in the background; the manager polls `state()`."""

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
            raise ValidationError('Eleme kararları zaten uygulanıyor.')
        data = screening.load(store.path(RELATIVE))
        if not screening.approved(data):
            raise ValidationError('Kararlar onaylanmadı ya da onaydan sonra değişti; önce onaylayın.')
        self.lines, self.summary, self.error = [], '', ''

        def work():
            try:
                r = writer.apply_screening(data, progress=self._progress)
                existing = f", {r['notes_existing']} zaten vardı" if r['notes_existing'] else ''
                failures = f", hata: {r['failed']}" if r['failed'] else ''
                self.summary = (f"Eleme kararları Zotero'ya işlendi: {r['items']} kayıt ({r['updated']} güncellendi, "
                                f"{r['unchanged']} zaten işlenmişti), hariç notu {r['notes_created']} yeni{existing}{failures}.")
                if r['failed']:
                    self.summary += ' Hatalı kayıtlar için yeniden başlatın; kaldığı yerden devam eder.'
                after = on_done(store)
                if after:
                    self.summary += ' ' + after
                self.notify(self.summary, '')
            except Exception as error:
                logging.exception('Screening application failed.')
                self.error = str(error)
                self.notify('Eleme kararları uygulanamadı: ' + self.error + ' Yeniden başlatınca kaldığı yerden devam eder.', '')

        self.thread = threading.Thread(target=work, daemon=True, name='screening-apply')
        self.thread.start()
        return self.state()

    def _progress(self, text):
        self.lines = (self.lines + [text])[-12:]

    def state(self):
        return {'running': self.running, 'lines': list(self.lines), 'summary': self.summary, 'error': self.error}
