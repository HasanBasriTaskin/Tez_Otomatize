"""Title/abstract screening decisions (03_Calisma/Eleme/eleme_kararlari.json) → checks, approval, PRISMA counts, Zotero plan.

The decisions file is prepared outside the program and holds one record per 01_Aday item with a status:
Hariç (with a reason code and a verbatim evidence quote), Geçti (Seçildi or Yedek for full text) or Özet okunmadı.
Nothing is written to Zotero until the user approves the file. The approval records who approved, when, and a digest
of the decisions; if the decisions change afterwards the approval no longer counts. Records left unread stay in
01_Aday without a code.
"""
import hashlib
import html
import json
import os
import shutil
from collections import Counter
from datetime import datetime
from pathlib import Path

from .storage import ValidationError

RELATIVE = Path('03_Calisma') / 'Eleme' / 'eleme_kararlari.json'
STATUSES = ('Hariç', 'Geçti', 'Özet okunmadı')
CODES = ('H1', 'H2', 'H5', 'H6')  # H3 and H4 belong to the full-text stage
FULL_TEXT = ('Seçildi', 'Yedek')
# Collection roles of the project's mapping (Zotero bölümü → koleksiyon eşleştirmesi).
ROLES = {'Hariç': 'excluded_title', 'Geçti': 'title_abstract'}
COLLECTIONS = {'Hariç': '05_Haric_BaslikOzet', 'Geçti': '02_BaslikOzet_Gecen'}
ACCESS_COLLECTION = '06_Erisim_Kontrol'
TAGS = {'Seçildi': 'TamMetin-Secildi', 'Yedek': 'TamMetin-Yedek'}
DECISION_FIELDS = ('key', 'baslik', 'durum', 'bakilan', 'gerekce_kodu', 'gerekce', 'kanit_alinti', 'tam_metin',
                   'erisim_on_kontrol')


def load(path):
    path = Path(path)
    if not path.is_file():
        raise ValidationError(f'Eleme karar dosyası yok: {path}')
    try:
        data = json.loads(path.read_text(encoding='utf-8'))
    except ValueError as error:
        raise ValidationError(f'Eleme karar dosyası okunamadı: {error}') from None
    if data.get('sema') != 1 or not isinstance(data.get('kayitlar'), list):
        raise ValidationError('Eleme karar dosyasının biçimi tanınmadı (sema 1 bekleniyor).')
    return data


def digest(data):
    """SHA-256 of the decisions themselves (not of notes or layout), so an approval covers exactly these decisions."""
    rows = sorted(({f: r.get(f, '') for f in DECISION_FIELDS} for r in data['kayitlar']), key=lambda r: str(r['key']))
    text = json.dumps(rows, ensure_ascii=False, sort_keys=True, separators=(',', ':'))
    return hashlib.sha256(text.encode('utf-8')).hexdigest()


def check(data, candidates):
    """Problems with the decisions against {zotero_key: title} of 01_Aday; an empty list means usable."""
    problems = []
    records = data['kayitlar']
    keys = Counter(r.get('key') for r in records)
    problems += [f'{k}: birden çok karar' for k, n in keys.items() if n > 1]
    problems += [f'{k}: 01_Aday içinde yok' for k in keys if k not in candidates]
    problems += [f'{k}: karar dosyasında yok' for k in candidates if k not in keys]
    for r in records:
        key, status = r.get('key'), r.get('durum')
        if status not in STATUSES:
            problems.append(f'{key}: bilinmeyen durum {status!r}')
            continue
        if key in candidates and candidates[key] != r.get('baslik'):
            problems.append(f'{key}: başlık Zotero kaydıyla aynı değil')
        quote = r.get('kanit_alinti') or ''
        if status == 'Hariç':
            if r.get('gerekce_kodu') not in CODES:
                problems.append(f'{key}: başlık-özet aşamasında geçersiz gerekçe kodu {r.get("gerekce_kodu")!r}')
            source = r.get('baslik', '') if r.get('bakilan') == 'Başlık' else None
            if not quote:
                problems.append(f'{key}: kanıt alıntısı yok')
            elif source is not None and quote not in source:
                problems.append(f'{key}: kanıt alıntısı başlıkta geçmiyor')
        elif status == 'Geçti':
            if r.get('gerekce_kodu'):
                problems.append(f'{key}: geçen kayıtta gerekçe kodu var')
            if r.get('tam_metin') not in FULL_TEXT:
                problems.append(f'{key}: tam metin durumu Seçildi ya da Yedek olmalı')
        elif r.get('gerekce_kodu') or r.get('bakilan') == 'Özet':
            problems.append(f'{key}: özeti okunmayan kayıtta karar izi var')
    return problems


def counts(data):
    """PRISMA numbers for the title/abstract stage; each box follows from the previous one."""
    records = data['kayitlar']
    status = Counter(r['durum'] for r in records)
    excluded = [r for r in records if r['durum'] == 'Hariç']
    return {
        'aday': len(records),
        'baslik_incelenen': len(records),
        'baslik_haric': sum(1 for r in excluded if r.get('bakilan') == 'Başlık'),
        'ozet_incelenen': sum(1 for r in records if r.get('bakilan') == 'Özet'),
        'ozet_haric': sum(1 for r in excluded if r.get('bakilan') == 'Özet'),
        'haric': len(excluded),
        'haric_kod': dict(sorted(Counter(r['gerekce_kodu'] for r in excluded).items())),
        'gecen': status['Geçti'],
        'tam_metin_secilen': sum(1 for r in records if r.get('tam_metin') == 'Seçildi'),
        'yedek': sum(1 for r in records if r.get('tam_metin') == 'Yedek'),
        'ozet_okunmadi': status['Özet okunmadı'],
    }


def approved(data):
    approval = data.get('onay') or {}
    return bool(approval.get('onaylandi') and str(approval.get('onaylayan', '')).strip() and approval.get('tarih')
                and approval.get('ozet') == digest(data))


def approval_state(data):
    """Short Turkish status for the manager screen."""
    approval = data.get('onay') or {}
    if approved(data):
        return f"Onaylı: {approval['onaylayan']}, {approval['tarih']}"
    if approval.get('onaylandi') and approval.get('ozet') and approval.get('ozet') != digest(data):
        return 'Onay geçersiz: kararlar onaydan sonra değişmiş. Yeniden kontrol edip onaylayın.'
    return 'Onaylanmadı'


def approve(path, operator, candidates, backup_dir, today=None):
    """Record the user's approval in the decisions file. The decisions are not changed; the previous file is kept."""
    path = Path(path)
    operator = str(operator or '').strip()
    if not operator:
        raise ValidationError('Onaylayan kişi boş. Ayarlar → Kaydı yapan kişi alanını doldurun.')
    data = load(path)
    problems = check(data, candidates)
    if problems:
        raise ValidationError(f'Karar dosyasında {len(problems)} sorun var; önce düzeltin. İlk sorun: {problems[0]}')
    backup_dir = Path(backup_dir)
    backup_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    shutil.copy2(path, backup_dir / f'eleme_kararlari_onay_oncesi_{stamp}.json')
    data['onay'] = {'onaylandi': True, 'onaylayan': operator,
                    'tarih': today or datetime.now().strftime('%d.%m.%Y'), 'ozet': digest(data)}
    temporary = path.with_name(path.name + '.yazılıyor')
    temporary.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding='utf-8')
    os.replace(temporary, path)
    return data['onay']


def note_lines(record, approval):
    """Exclusion note with the field names of the program's exclusion template, so the note reader recognises them."""
    source = 'başlık' if record.get('bakilan') == 'Başlık' else 'özet'
    return [
        'Karar: Hariç',
        'Aşama: Başlık-özet',
        f'Gerekçe kodu: {record["gerekce_kodu"]}',
        f'Açıklama: {record.get("gerekce", "")}',
        f'Kanıt ({source}): "{record.get("kanit_alinti", "")}"',
        f'Karar veren: {approval["onaylayan"]}',
        f'Karar tarihi: {approval["tarih"]}',
    ]


def note_html(lines):
    return ''.join(f'<p>{html.escape(line, quote=False)}</p>' for line in lines)


def note(record, approval):
    return '\n'.join(note_lines(record, approval))


def needs_access_check(record):
    return record.get('tam_metin') == 'Seçildi' and str(record.get('erisim_on_kontrol', '')).startswith('Kontrol edilecek')


def plan(data):
    """Zotero actions per item: collection roles to add, tags, note text (None before approval)."""
    ok = approved(data)
    actions = []
    for r in data['kayitlar']:
        if r['durum'] == 'Özet okunmadı':
            continue
        tags = [r['gerekce_kodu']] if r['durum'] == 'Hariç' else [TAGS[r['tam_metin']]]
        actions.append({'key': r['key'], 'role': ROLES[r['durum']], 'collection': COLLECTIONS[r['durum']], 'tags': tags,
                        'access_check': needs_access_check(r),
                        'note': note(r, data['onay']) if ok and r['durum'] == 'Hariç' else None})
    return actions


def summary(actions):
    return {
        'islem': len(actions),
        'koleksiyon': dict(sorted(Counter(a['collection'] for a in actions).items())),
        'erisim_kontrol': sum(1 for a in actions if a['access_check']),
        'etiket': dict(sorted(Counter(t for a in actions for t in a['tags']).items())),
        'not': sum(1 for a in actions if a['note']),
    }
