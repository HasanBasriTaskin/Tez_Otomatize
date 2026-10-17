"""Strict Scopus RIS metadata reader. No network access or attachment handling."""
import re
from urllib.parse import unquote

from .storage import ValidationError


EID = re.compile(r'(?<![\w-])2-s2\.0-\d+(?![\w-])')
TYPES = {'JOUR': 'journalArticle', 'JFULL': 'journalArticle', 'EJOUR': 'journalArticle',
         'CONF': 'conferencePaper', 'CPAPER': 'conferencePaper', 'BOOK': 'book',
         'CHAP': 'bookSection', 'RPRT': 'report', 'THES': 'thesis',
         'GEN': 'document', 'UNPB': 'manuscript', 'ELEC': 'webpage'}


def normalize_doi(value):
    return re.sub(r'^(?:https?://(?:dx\.)?doi\.org/|doi:\s*)', '', value.strip(), flags=re.I).casefold()


def scopus_eids(data):
    """Use explicit identifiers/URLs only; titles and abstracts may cite other papers."""
    if 'itemType' in data:
        values = [data.get('url', '')]
        values += re.findall(r'(?im)^Scopus\s+EID:\s*(.+)$', data.get('extra', ''))
    else:
        values = [v for tag in ('AN', 'ID', 'UR', 'L1', 'L2') for v in data.get(tag, [])]
        values += [v for v in data.get('N1', []) if re.match(r'(?i)^\s*(?:Scopus\s+)?EID\s*:', v)]
    return set(EID.findall(unquote('\n'.join(values))))


def _record(fields, require_eid=True):
    def first(*tags):
        return next((v for tag in tags for v in fields.get(tag, []) if v), '')

    ids = scopus_eids(fields)
    if len(ids) != 1 and (require_eid or ids):
        raise ValidationError('RIS kaydında tek ve geçerli bir Scopus EID bulunmalı.')
    eid = ids.pop() if ids else ''
    kind = TYPES.get(first('TY').upper())
    if not kind:
        raise ValidationError('RIS yayın türü desteklenmiyor: ' + first('TY'))
    title = first('TI', 'T1', 'CT')
    if not title:
        raise ValidationError('RIS kaydının başlığı eksik.')
    item = dict(itemType=kind, title=title, creators=[], tags=[], collections=[], relations={})
    for name in fields.get('AU', fields.get('A1', [])):
        last, comma, given = name.partition(',')
        item['creators'].append(dict(creatorType='author', lastName=last.strip(), firstName=given.strip())
                                if comma else dict(creatorType='author', name=name))
    date = first('PY', 'Y1', 'DA')
    doi = first('DO')
    journal = first('JO', 'JF', 'T2', 'JA')
    if date:
        item['date'] = date
    if doi and kind in ('journalArticle', 'conferencePaper', 'document'):
        item['DOI'] = re.sub(r'^(?:https?://(?:dx\.)?doi\.org/|doi:\s*)', '', doi, flags=re.I)
    if journal:
        field = {'journalArticle': 'publicationTitle', 'conferencePaper': 'proceedingsTitle',
                 'bookSection': 'bookTitle', 'webpage': 'websiteTitle'}.get(kind)
        if field:
            item[field] = journal
    if first('AB', 'N2'):
        item['abstractNote'] = '\n'.join(fields.get('AB', fields.get('N2', [])))
    item['tags'] = [{'tag': value} for value in dict.fromkeys(fields.get('KW', [])) if value]
    urls = [v for v in fields.get('UR', []) if re.match(r'^https?://', v, re.I)]
    if urls:
        item['url'] = urls[0]
    extra = ['Scopus EID: ' + eid] if eid else []
    if doi and 'DOI' not in item:
        extra.append('DOI: ' + doi)
    if journal and not any(f in item for f in ('publicationTitle', 'proceedingsTitle', 'bookTitle', 'websiteTitle')):
        extra.append('Source title: ' + journal)
    extra.extend('URL: ' + url for url in urls[1:])
    extra.extend(fields.get('N1', []))
    item['extra'] = '\n'.join(extra)
    if kind in ('journalArticle', 'conferencePaper', 'book', 'bookSection'):
        if first('VL'):
            item['volume'] = first('VL')
        if kind == 'journalArticle' and first('IS'):
            item['issue'] = first('IS')
        start, end = first('SP'), first('EP')
        if start and kind != 'book':
            item['pages'] = start + ('-' + end if end and end != start else '')
        if first('SN'):
            item['ISSN' if kind == 'journalArticle' else 'ISBN'] = first('SN')
    if kind in ('book', 'bookSection', 'conferencePaper'):
        if first('PB'):
            item['publisher'] = first('PB')
        if first('CY', 'PP'):
            item['place'] = first('CY', 'PP')
    if first('LA'):
        item['language'] = first('LA')
    year = re.search(r'\b\d{4}\b', date)
    return dict(eid=eid, doi=normalize_doi(doi), title=title, year=year.group() if year else '',
                item=item, raw_fields=fields)


def parse_ris(data: bytes, require_eid=True, skipped=None) -> list:
    """Scopus RIS by default (each record must carry its EID). With require_eid=False any RIS (IEEE, ACM) is read;
    a record that cannot become a Zotero item is appended to `skipped` as (number, reason) when a list is given."""
    if not isinstance(data, bytes) or not data or len(data) > 128 * 1024 * 1024:
        raise ValidationError('RIS dosyası boş veya boyut sınırını aşıyor.')
    try:
        text = data.decode('utf-16' if data.startswith((b'\xff\xfe', b'\xfe\xff')) else 'utf-8-sig')
    except UnicodeError:
        raise ValidationError('RIS dosyası geçerli UTF-8 veya BOM içeren UTF-16 olmalı.') from None
    if '\x00' in text or re.search(r'<\s*(?:!doctype\s+html|html|head|body)\b', text, re.I):
        raise ValidationError('RIS yerine bozuk veya HTML içerik alındı.')
    result, fields, current = [], None, None
    for number, line in enumerate(text.splitlines(), 1):
        if not line.strip():
            continue
        match = re.fullmatch(r'([A-Z][A-Z0-9])  - ?(.*)', line)
        if not match:
            if fields is not None and current and line.startswith((' ', '\t')):
                fields[current][-1] += '\n' + line.strip()
                continue
            raise ValidationError(f'RIS yapısı bozuk; satır {number}.')
        tag, value = match.group(1), match.group(2).strip()
        if tag == 'TY':
            if fields is not None or not value:
                raise ValidationError('RIS kaydı kapanmadan yeni kayıt başladı.')
            fields, current = {'TY': [value]}, 'TY'
        elif tag == 'ER':
            if fields is None or value:
                raise ValidationError('RIS kayıt sonu geçersiz.')
            try:
                result.append(_record(fields, require_eid))
            except ValidationError as error:
                if skipped is None:
                    raise
                skipped.append((len(result) + len(skipped) + 1, str(error)))
            fields, current = None, None
        else:
            if fields is None:
                raise ValidationError('RIS alanı TY/ER kayıt sınırları dışında.')
            fields.setdefault(tag, []).append(value)
            current = tag
    if fields is not None or not result:
        raise ValidationError('RIS dosyası yarım veya kayıt içermiyor.')
    return result
