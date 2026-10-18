"""Reviewed Zotero corrections kept in the project (03_Calisma/Eleme/zotero_duzeltmeleri.json).

The file lists, item by item, a field, the value Zotero holds now and the corrected value with the page it was checked
against (e.g. a conference's official proceedings page), plus empty working collections to remove. Nothing here is
guessed: a correction is written only while Zotero still holds the listed old value, and a collection is removed only
when it is empty and its name matches.
"""
import json
from pathlib import Path

from .storage import ValidationError

RELATIVE = Path('03_Calisma') / 'Eleme' / 'zotero_duzeltmeleri.json'


def load(root):
    path = Path(root) / RELATIVE
    if not path.is_file():
        return {'sema': 1, 'kunye': [], 'bos_koleksiyonlar': []}
    try:
        data = json.loads(path.read_text(encoding='utf-8'))
    except ValueError as error:
        raise ValidationError(f'Zotero düzeltme dosyası okunamadı: {error}') from None
    if data.get('sema') != 1:
        raise ValidationError('Zotero düzeltme dosyasının biçimi tanınmadı (sema 1 bekleniyor).')
    for entry in data.get('kunye', []):
        if not all(isinstance(entry.get(k), str) and entry[k] for k in ('key', 'alan', 'yeni')):
            raise ValidationError('Zotero düzeltme dosyasında key/alan/yeni eksik bir satır var.')
    for entry in data.get('bos_koleksiyonlar', []):
        if not all(isinstance(entry.get(k), str) and entry[k] for k in ('key', 'ad')):
            raise ValidationError('Zotero düzeltme dosyasında key/ad eksik bir koleksiyon satırı var.')
    return data


def corrections(data):
    return list(data.get('kunye', []))


def empty_collections(data):
    return list(data.get('bos_koleksiyonlar', []))


def summary(data):
    return {'kunye': len(corrections(data)), 'bos_koleksiyon': len(empty_collections(data))}
