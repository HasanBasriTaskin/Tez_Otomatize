"""Full-text screening decisions and reading notes (03_Calisma/Eleme/tam_metin_kararlari.json + 03_Calisma/Okuma_Taslaklari/L*.txt).

Nothing is written to Zotero until the user explicitly checks and approves the full-text decisions and reading notes.
The approval records who approved, when, and a SHA-256 digest covering both the decision table and the exact text of
all 83 reading notes; if any decision or reading note file changes afterwards, the approval is invalidated.
"""
import hashlib
import html
import json
import os
import shutil
from collections import Counter
from datetime import datetime
from pathlib import Path

from .exports import GOOD_QUALITY, PAGE_EVIDENCE, REQUIRED_FIELDS
from .pdf_archive import ARCHIVE_DIR, MATRIX_ID
from .storage import ValidationError
from .zotero import UNKNOWN_KEY, parse_note

RELATIVE = Path('03_Calisma') / 'Eleme' / 'tam_metin_kararlari.json'
NOTES_DIR = Path('03_Calisma') / 'Okuma_Taslaklari'
CANDIDATE_PDF_DIR = '04_PDF_Aday'
STATUSES = ('Dahil', 'Hariç', 'Yedek')
CODES = ('H1', 'H2', 'H3', 'H4', 'H5', 'H6')
ROLES = {'Dahil': 'included', 'Hariç': 'excluded', 'Yedek': 'title_abstract'}
COLLECTIONS = {'Dahil': '03_TamMetin_Dahil', 'Hariç': '04_Haric_TamMetin', 'Yedek': '02_BaslikOzet_Gecen'}
TAGS = {'Seçildi': 'TamMetin-Secildi', 'Yedek': 'TamMetin-Yedek'}
DECISION_FIELDS = ('key', 'baslik', 'durum', 'matris_id', 'sorumlu', 'not_dosyasi', 'yerel_pdf',
                   'gerekce_kodu', 'gerekce', 'karar_veren', 'karar_tarihi')


def load(path):
    path = Path(path)
    if not path.is_file():
        raise ValidationError(f'Tam metin karar dosyası yok: {path}')
    try:
        data = json.loads(path.read_text(encoding='utf-8'))
    except ValueError as error:
        raise ValidationError(f'Tam metin karar dosyası okunamadı: {error}') from None
    if data.get('sema') != 1 or not isinstance(data.get('kayitlar'), list):
        raise ValidationError('Tam metin karar dosyasının biçimi tanınmadı (sema 1 bekleniyor).')
    return data


def _project_root(path):
    path = Path(path).resolve()
    if path.name == RELATIVE.name and path.parent.name == 'Eleme':
        return path.parents[2]
    return path if path.is_dir() else path.parent


def note_text_for(record, root=None):
    """Read the 27-line reading note text for an included paper from disk or inline test data."""
    if record.get('not_metni'):
        return str(record['not_metni']).strip()
    rel = str(record.get('not_dosyasi') or '').strip()
    if not rel and record.get('matris_id'):
        rel = (NOTES_DIR / f"{record['matris_id']}.txt").as_posix()
    if root and rel:
        candidate = (Path(root) / rel).resolve()
        if candidate.is_file():
            return candidate.read_text(encoding='utf-8').strip()
    return ''


def digest(data, root=None):
    """SHA-256 of the full-text decisions AND the full text of every reading note."""
    rows = []
    for r in data['kayitlar']:
        entry = {f: r.get(f, '') for f in DECISION_FIELDS}
        entry['not_metni'] = note_text_for(r, root) if r.get('durum') == 'Dahil' else ''
        rows.append(entry)
    rows.sort(key=lambda r: str(r['key']))
    text = json.dumps(rows, ensure_ascii=False, sort_keys=True, separators=(',', ':'))
    return hashlib.sha256(text.encode('utf-8')).hexdigest()


def same_text(a, b):
    return ' '.join(str(a or '').split()) == ' '.join(str(b or '').split())


def check(data, candidates, root=None):
    """Validate full-text decisions and all 83 reading notes against Zotero items and local PDFs."""
    problems = []
    records = data['kayitlar']
    keys = Counter(r.get('key') for r in records)
    problems += [f'{k}: birden çok karar' for k, n in keys.items() if n > 1]
    problems += [f'{k}: Zotero kütüphanesinde (02_BaslikOzet_Gecen) yok' for k in keys if k not in candidates]
    mids = Counter(str(r.get('matris_id') or '').strip() for r in records if r.get('durum') == 'Dahil')
    problems += [f'{m}: birden çok kayıtta aynı Matris ID' for m, n in mids.items() if m and n > 1]
    for r in records:
        key, status = r.get('key'), r.get('durum')
        if status not in STATUSES:
            problems.append(f'{key}: bilinmeyen durum {status!r}')
            continue
        if key in candidates and not same_text(candidates[key], r.get('baslik')):
            problems.append(f'{key}: başlık Zotero kaydıyla aynı değil')
        if status == 'Dahil':
            mid = str(r.get('matris_id') or '').strip()
            label = mid or key
            if not MATRIX_ID.fullmatch(mid):
                problems.append(f'{key}: geçersiz Matris ID {mid!r}')
            raw_note = note_text_for(r, root)
            if not raw_note:
                problems.append(f'{label}: okuma notu dosyası bulunamadı veya boş')
                continue
            parsed = parse_note(raw_note)
            if parsed.get('Matris ID', '').strip() != mid:
                problems.append(f"{label}: nottaki Matris ID ({parsed.get('Matris ID')!r}) eşleşmiyor")
            if parsed.get('Karar', '').strip().casefold() != 'dahil':
                problems.append(f'{label}: notta Karar: Dahil olmalı')
            if UNKNOWN_KEY in parsed:
                problems.append(f'{label}: notta tanınmayan alan — {parsed[UNKNOWN_KEY]}')
            missing = [f for f in (*REQUIRED_FIELDS, 'Okuma tarihi', 'Çekirdek adayı', 'Anotasyon', 'Yerel PDF')
                       if not parsed.get(f, '').strip()]
            if missing:
                problems.append(f"{label}: boş zorunlu alan — {', '.join(missing)}")
            if parsed.get('Temel bulgu', '').strip() and not PAGE_EVIDENCE.search(parsed['Temel bulgu']):
                problems.append(f'{label}: Temel bulgu alanında sayfa/tablo kanıtı yok')
            pdf_name = parsed.get('Yerel PDF', '').strip() or str(r.get('yerel_pdf') or '').strip()
            if root and pdf_name:
                cand_pdf = Path(root) / CANDIDATE_PDF_DIR / pdf_name
                arch_pdf = Path(root) / ARCHIVE_DIR / pdf_name
                if not (cand_pdf.is_file() or arch_pdf.is_file()):
                    problems.append(f'{label}: yerel PDF bulunamadı ({CANDIDATE_PDF_DIR}/{pdf_name})')
        elif status == 'Hariç':
            if r.get('gerekce_kodu') not in CODES:
                problems.append(f"{key}: geçersiz gerekçe kodu {r.get('gerekce_kodu')!r}")
            if not str(r.get('gerekce') or '').strip():
                problems.append(f'{key}: hariç gerekçe açıklaması boş')
            if not str(r.get('karar_veren') or '').strip():
                problems.append(f'{key}: karar veren boş')
            if not str(r.get('karar_tarihi') or '').strip():
                problems.append(f'{key}: karar tarihi boş')
        elif status == 'Yedek':
            if r.get('matris_id') or r.get('gerekce_kodu'):
                problems.append(f'{key}: yedek kayıtta Matris ID veya gerekçe kodu olmamalı')
    return problems


def counts(data, root=None):
    records = data['kayitlar']
    status = Counter(r.get('durum') for r in records)
    excluded = [r for r in records if r.get('durum') == 'Hariç']
    readers = Counter()
    core = 0
    good = 0
    for r in records:
        if r.get('durum') != 'Dahil':
            continue
        parsed = parse_note(note_text_for(r, root))
        reader = parsed.get('Okuyan kişi', '').strip() or str(r.get('sorumlu') or '').strip() or 'belirtilmemiş'
        readers[reader] += 1
        if parsed.get('Çekirdek adayı', '').strip().casefold().startswith('evet') and '3' in parsed.get('Okuma düzeyi', ''):
            core += 1
        if GOOD_QUALITY.search(parsed.get('Kalite sınıfı ve yılı', '')):
            good += 1
    return {
        'toplam': len(records),
        'dahil': status['Dahil'],
        'haric': status['Hariç'],
        'haric_kod': dict(sorted(Counter(r.get('gerekce_kodu', '') for r in excluded).items())),
        'yedek_iade': status['Yedek'],
        'okuyanlar': dict(readers),
        'cekirdek': core,
        'kaliteli': good,
    }


def approved(data, root=None):
    approval = data.get('onay') or {}
    return bool(approval.get('onaylandi') and str(approval.get('onaylayan', '')).strip() and approval.get('tarih')
                and approval.get('ozet') == digest(data, root))


def approval_state(data, root=None):
    approval = data.get('onay') or {}
    if approved(data, root):
        return f"Onaylı: {approval['onaylayan']}, {approval['tarih']}"
    if approval.get('onaylandi') and approval.get('ozet') and approval.get('ozet') != digest(data, root):
        return 'Onay geçersiz: kararlar veya okuma notları onaydan sonra değişmiş. Yeniden kontrol edip onaylayın.'
    return 'Onaylanmadı'


def approve(path, operator, candidates, backup_dir, root=None, today=None):
    path = Path(path)
    root = Path(root) if root else _project_root(path)
    operator = str(operator or '').strip()
    if not operator:
        raise ValidationError('Onaylayan kişi boş. Ayarlar → Kaydı yapan kişi alanını doldurun.')
    data = load(path)
    problems = check(data, candidates, root)
    if problems:
        raise ValidationError(f'Tam metin kararlarında/notlarında {len(problems)} sorun var; önce düzeltin. İlk sorun: {problems[0]}')
    backup_dir = Path(backup_dir)
    backup_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    shutil.copy2(path, backup_dir / f'tam_metin_kararlari_onay_oncesi_{stamp}.json')
    data['onay'] = {'onaylandi': True, 'onaylayan': operator,
                    'tarih': today or datetime.now().strftime('%d.%m.%Y'), 'ozet': digest(data, root)}
    temporary = path.with_name(path.name + '.yazılıyor')
    temporary.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding='utf-8')
    os.replace(temporary, path)
    return data['onay']


def exclusion_note_lines(record, approval=None):
    reviewer = str(record.get('karar_veren') or (approval or {}).get('onaylayan') or '').strip()
    date_str = str(record.get('karar_tarihi') or (approval or {}).get('tarih') or '').strip()
    return [
        'Karar: Hariç',
        'Aşama: Tam metin',
        f"Gerekçe kodu: {record['gerekce_kodu']}",
        f"Açıklama: {record.get('gerekce', '')}",
        f'Karar veren: {reviewer}',
        f'Karar tarihi: {date_str}',
    ]


def note_html(lines):
    return ''.join(f'<p>{html.escape(line, quote=False)}</p>' for line in lines if line.strip())


def plan(data, root=None):
    """Zotero actions per full-text decision item: target collection, tags to add/remove, and child note."""
    ok = approved(data, root)
    actions = []
    for r in data['kayitlar']:
        status = r['durum']
        key = r['key']
        if status == 'Dahil':
            raw = note_text_for(r, root) if ok else None
            actions.append({
                'key': key,
                'role': ROLES['Dahil'],
                'collection': COLLECTIONS['Dahil'],
                'tags': [TAGS['Seçildi']],
                'remove_tags': [TAGS['Yedek']],
                'note_identity': 'reading-note:' + key,
                'note': raw,
            })
        elif status == 'Hariç':
            lines = exclusion_note_lines(r, data.get('onay'))
            actions.append({
                'key': key,
                'role': ROLES['Hariç'],
                'collection': COLLECTIONS['Hariç'],
                'tags': [r['gerekce_kodu'], TAGS['Seçildi']],
                'remove_tags': [TAGS['Yedek']],
                'note_identity': 'fulltext-exclusion-note:' + key,
                'note': '\n'.join(lines) if ok else None,
            })
        elif status == 'Yedek':
            actions.append({
                'key': key,
                'role': ROLES['Yedek'],
                'collection': COLLECTIONS['Yedek'],
                'tags': [TAGS['Yedek']],
                'remove_tags': [TAGS['Seçildi']],
                'note_identity': '',
                'note': None,
            })
    return actions


def summary(actions):
    return {
        'islem': len(actions),
        'koleksiyon': dict(sorted(Counter(a['collection'] for a in actions).items())),
        'etiket_eklenen': dict(sorted(Counter(t for a in actions for t in a['tags']).items())),
        'etiket_kaldirilan': dict(sorted(Counter(t for a in actions for t in a['remove_tags']).items())),
        'okuma_notu': sum(1 for a in actions if a['note'] and a['note_identity'].startswith('reading-note:')),
        'haric_notu': sum(1 for a in actions if a['note'] and a['note_identity'].startswith('fulltext-exclusion-note:')),
    }
