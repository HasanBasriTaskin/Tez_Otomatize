"""Title/abstract screening decisions (03_Calisma/Eleme/eleme_kararlari.json) → checks, PRISMA counts, Zotero plan.

The decisions file is prepared outside the program and holds one record per 01_Aday item with a status:
Hariç (with a reason code and a verbatim evidence quote), Geçti (Seçildi or Yedek for full text) or Özet okunmadı.
Nothing is written to Zotero until the file carries the user's approval (onay.onaylandi, onaylayan, tarih); until then
only `check` and `plan` (a dry run) are available. Records left unread stay in 01_Aday without a code.
"""
import json
from collections import Counter
from pathlib import Path

from .storage import ValidationError

RELATIVE = Path('03_Calisma') / 'Eleme' / 'eleme_kararlari.json'
STATUSES = ('Hariç', 'Geçti', 'Özet okunmadı')
CODES = ('H1', 'H2', 'H5', 'H6')  # H3 and H4 belong to the full-text stage
FULL_TEXT = ('Seçildi', 'Yedek')
COLLECTIONS = {'Hariç': '05_Haric_BaslikOzet', 'Geçti': '02_BaslikOzet_Gecen'}
TAGS = {'Seçildi': 'TamMetin-Secildi', 'Yedek': 'TamMetin-Yedek'}


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
        'ozet_incelenen': sum(1 for r in records if r.get('bakilan') == 'Özet'),
        'haric': len(excluded),
        'haric_kod': dict(sorted(Counter(r['gerekce_kodu'] for r in excluded).items())),
        'gecen': status['Geçti'],
        'tam_metin_secilen': sum(1 for r in records if r.get('tam_metin') == 'Seçildi'),
        'yedek': sum(1 for r in records if r.get('tam_metin') == 'Yedek'),
        'ozet_okunmadi': status['Özet okunmadı'],
    }


def approved(data):
    approval = data.get('onay') or {}
    return bool(approval.get('onaylandi') and str(approval.get('onaylayan', '')).strip() and approval.get('tarih'))


def note(record, approval):
    """Exclusion note in the project's note template; only written once the decisions are approved."""
    return '\n'.join([
        'Aşama: Başlık-özet',
        f'Gerekçe kodu: {record["gerekce_kodu"]}',
        f'Gerekçe: {record.get("gerekce", "")}',
        f'Kanıt: "{record.get("kanit_alinti", "")}" ({record.get("bakilan", "")})',
        f'Karar veren: {approval["onaylayan"]}',
        f'Karar tarihi: {approval["tarih"]}',
    ])


def plan(data):
    """Zotero actions per item (dry run): collection to add, tags, note text (None before approval)."""
    ok = approved(data)
    actions = []
    for r in data['kayitlar']:
        if r['durum'] == 'Özet okunmadı':
            continue
        tags = [r['gerekce_kodu']] if r['durum'] == 'Hariç' else [TAGS[r['tam_metin']]]
        actions.append({'key': r['key'], 'collection': COLLECTIONS[r['durum']], 'tags': tags,
                        'note': note(r, data['onay']) if ok and r['durum'] == 'Hariç' else None})
    return actions
