"""The project's approved 2022–2026 / 2024–2026 narrowing rules."""
import json
import re
import uuid

from .storage import ValidationError, json_text, utcnow

YEAR_TAIL = re.compile(r'\s+AND\s+PUBYEAR\s*([<>])\s*(\d{4})\s*$', re.I)


def canonical(query):
    # Preserve spaces inside quoted search phrases; ignore UI spacing elsewhere.
    return ''.join(re.findall(r'"(?:\\.|[^"\\])*"|\S', query))


def split_years(query):
    base = query.strip()
    lower, upper = [], []
    while match := YEAR_TAIL.search(base):
        (lower if match[1] == '>' else upper).append(int(match[2]))
        base = base[:match.start()].strip()
    unquoted = re.sub(r'"(?:\\.|[^"\\])*"', '', base)
    if re.search(r'\bPUBYEAR\b', unquoted, re.I):
        return None, None
    if lower or upper:
        if not lower or not upper or max(lower) + 1 > min(upper) - 1:
            return None, None
        return base, (max(lower) + 1, min(upper) - 1)
    return base, None


def get_proposal(store, identity):
    row = store.db.execute('SELECT * FROM search_refinements WHERE id=?', (identity,)).fetchone()
    if not row:
        raise ValidationError('Daraltma önerisi bulunamadı.')
    result = dict(row)
    result['context'] = json.loads(result.pop('context_json'))
    if result['context'].get('kind') == 'ieee':
        result['filters_label'] = ieee_label(result)
    return result


def approve(store, identity, profile):
    with store.lock, store.db:
        proposal = get_proposal(store, identity)
        if proposal['context'].get('profile') != profile or proposal['state'] != 'offered':
            raise ValidationError('Öneri bu Chrome oturumuna ait değil veya daha önce işlendi. Yeniden Ctrl+M yapın.')
        store.db.execute("UPDATE search_refinements SET state='approved',approved_at=? WHERE id=?", (utcnow(), identity))
        store.audit('refinement_approved', identity, {'from': proposal['run_id'], 'query': proposal['query']})
        return get_proposal(store, identity)


def project_window(store):
    """The year window already decided by a captured narrowing chain (CEN401 Tablo 4 decides it
    once, on the first query). Returns (year_from, 'S001 → S003') or (None, None)."""
    row = store.db.execute(
        "SELECT r.year_from, r.display_id, c.display_id AS child FROM search_refinements r "
        "LEFT JOIN search_runs c ON c.id = r.child_run_id WHERE r.state = 'captured' AND r.year_from >= 1990 "
        # The first chain that reached the window decided it; later topic chains only reuse it.
        "ORDER BY r.year_from DESC, r.created_at ASC LIMIT 1").fetchone()
    if not row or not 1990 <= row['year_from'] <= 2026:
        return None, None
    return row['year_from'], f"{row['display_id']} → {row['child'] or '?'}"


WINDOW_NOTE = re.compile(r'(Proje yıl penceresi \d{4}–2026 \()(S\d{3,} → (?:S\d{3,}|\?))( daraltmasıyla belirlendi\))')


def _n(value):
    return f'{value:,}'.replace(',', '.')


def applied(reason):
    """A proposal's reason as it reads in the search log once the user applied it."""
    return (reason.replace('öneriliyor', 'uygulandı').replace('bu sorguya da aynı pencere uygulanıyor', 'bu sorguya da aynı pencere uygulandı'))


def repair_window_notes(store):
    """0.3.2 named the latest topic chain instead of the deciding one in reasons and notes
    (e.g. "S004 → S005" where "S002 → S003" decided the window). Rewrites only that phrase."""
    window, chain = project_window(store)
    if window is None:
        return 0
    fixed = 0
    with store.lock, store.db:
        for table, key, column in (('search_runs', 'id', 'notes'), ('search_refinements', 'id', 'reason')):
            for row in store.db.execute(f"SELECT {key},{column} FROM {table} WHERE {column} LIKE '%daraltmasıyla belirlendi%'").fetchall():
                text = row[1] or ''
                new = WINDOW_NOTE.sub(lambda m: m[1] + chain + m[3], text)
                if new != text:
                    store.db.execute(f'UPDATE {table} SET {column}=? WHERE {key}=?', (new, row[0]))
                    fixed += 1
        if fixed:
            store.audit('window_notes_repaired', chain, {'rows': fixed})
    return fixed


IEEE = 'IEEE Xplore'
# Kılavuz: Scopus DOCTYPE ar/cp/re ↔ IEEE Journals + Conferences. Early Access stays out (user decision, 0.4.0).
IEEE_TYPES = ['Conferences', 'Journals']
IEEE_APPLIED_YEARS = re.compile(r'Yıl: (\d{4})–(\d{4})')
IEEE_RESULT_YEARS = re.compile(r'Yıl \(sonuç aralığı\): (\d{4})–(\d{4})')


def _filters(run):
    if 'filters' in run and isinstance(run['filters'], list):
        return run['filters']
    try:
        value = json.loads(run.get('filters_json') or '[]')
    except ValueError:
        return []
    return value if isinstance(value, list) else []


def ieee_filters(filters):
    """Reads the extension's IEEE filter labels: types, applied year range, result year range."""
    types, applied, natural = [], None, None
    for item in filters:
        item = str(item)
        if item.startswith('Tür: '):
            types.append(item[5:].strip())
        elif match := IEEE_APPLIED_YEARS.fullmatch(item):
            applied = (int(match[1]), int(match[2]))
        elif match := IEEE_RESULT_YEARS.fullmatch(item):
            natural = (int(match[1]), int(match[2]))
    return types, applied, natural


def _ieee_window(store):
    configured = store.settings().get('window_start')
    if isinstance(configured, int) and 1990 <= configured <= 2026:
        return configured, 'Ayarlar → yıl penceresi'
    return project_window(store)


def _within(years, year_from, year_to=2026):
    return years is not None and year_from <= years[0] <= years[1] <= year_to


def _ieee_label(types, apply_years, year_from, year_to):
    parts = ['Tür: ' + ', '.join(types)]
    if apply_years:
        parts.append(f'Yıl: {year_from}–{year_to}')
    return '; '.join(parts)


def _ieee_satisfies(filters, proposal):
    types, applied, natural = ieee_filters(filters)
    wanted = json.loads(proposal['context_json'])
    if sorted(types) != sorted(wanted.get('types') or []):
        return False
    if wanted.get('apply_years'):
        return _within(applied or natural, proposal['year_from'], proposal['year_to'])
    return True


def _propose_ieee(store, run, context):
    context = dict(context)
    filters = _filters(run)
    types, applied, natural = ieee_filters(filters)
    with store.lock, store.db:
        if store.db.execute('SELECT 1 FROM search_refinements WHERE run_id=?', (run['id'],)).fetchone():
            return None
        initial_count, parent = run['count_value'], None
        for row in store.db.execute("SELECT * FROM search_refinements WHERE state='approved' ORDER BY approved_at DESC"):
            prior = dict(row)
            prior_context = json.loads(prior['context_json'])
            if (prior_context.get('kind') == 'ieee'
                    and all(prior_context.get(k) == context.get(k) for k in ('profile', 'windowId', 'tabId'))
                    and canonical(prior['source_query']) == canonical(run['query_raw'])
                    and _ieee_satisfies(filters, prior)):
                parent = prior
                break
        if parent:
            store.db.execute("UPDATE search_refinements SET state='captured',child_run_id=? WHERE id=?", (run['id'], parent['id']))
            note = (f"{parent['display_id']} sorgusuna IEEE filtreleri uygulandı "
                    f"({_ieee_label(parent_types(parent), json.loads(parent['context_json']).get('apply_years'), parent['year_from'], parent['year_to'])}).")
            old_note = run['notes'] or ''
            store.db.execute('UPDATE search_runs SET notes=? WHERE id=?', ('\n'.join(x for x in (old_note, note) if x), run['id']))
            store.audit('refinement_captured', parent['id'], {'child': run['id']})
            parent_context = json.loads(parent['context_json'])
            # Tablo 4 second step, only when no project window decided the years.
            if (parent_context.get('project_window') or (parent['year_from'], parent['year_to']) != (2022, 2026)
                    or parent['initial_count'] <= 1000 or run['count_value'] <= 500):
                return None
            initial_count, year_from, apply_years, window_used = parent['initial_count'], 2024, True, False
            reason = (f"İlk sorgu {_n(initial_count)} sonuç; 2022–2026 sonucu {_n(run['count_value'])} (500'den fazla). "
                      f"Kılavuz Tablo 4'e göre 2024–2026 öneriliyor.")
        else:
            if run['count_value'] == 0:
                return None
            window, chain = _ieee_window(store)
            window_used = window is not None
            if window_used:
                year_from = window
                reason = f"Proje yıl penceresi {window}–2026 ({chain} daraltmasıyla belirlendi)."
                if chain.startswith('Ayarlar'):
                    reason = f"Proje yıl penceresi {window}–2026 (Ayarlar'da girildi)."
            elif applied is not None:
                year_from, reason = None, 'Yıl aralığı elle seçilmiş; yalnız yayın türü düzeltiliyor.'
            elif initial_count > 300:
                year_from = 2022
                reason = f"Yıl sınırı olmayan sorgu {_n(initial_count)} sonuç (300'den fazla). Kılavuz Tablo 4'e göre 2022–2026 öneriliyor."
            else:
                year_from, reason = None, f"Sonuç {_n(initial_count)} ≤ 300: kılavuza göre yıl sınırı gerekmiyor."
            if year_from is None:
                apply_years = False
            elif applied is not None:
                apply_years = not _within(applied, year_from)
            else:
                # IEEE's own default range is the span of the results; if it already fits, no year filter is needed.
                apply_years = not _within(natural, year_from)
            type_change = sorted(types) != sorted(IEEE_TYPES)
            if not apply_years and not type_change:
                return None
            if type_change:
                reason += (" Yayın türü yalnız Conferences + Journals olmalı (Scopus'taki makale/bildiri/derleme "
                           "karşılığı; Early Access hariç).")
        types_wanted = list(IEEE_TYPES)
        year_from_stored, year_to_stored = (year_from, 2026) if apply_years else (0, 0)
        context.update(kind='ieee', apply_years=apply_years, types=types_wanted, project_window=window_used)
        label = _ieee_label(types_wanted, apply_years, year_from, 2026)
        reason = f"{reason} Uygulanacak IEEE filtreleri: {label}."
        identity = str(uuid.uuid4())
        store.db.execute('INSERT INTO search_refinements VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',
                         (identity, run['id'], run['display_id'], initial_count, year_from_stored, year_to_stored,
                          run['query_raw'], run['count_value'], run['query_raw'], reason, json_text(context),
                          'offered', utcnow(), None, None))
        store.audit('refinement_offered', identity, {'run': run['id'], 'ieee': label})
        return get_proposal(store, identity)


def parent_types(proposal):
    return json.loads(proposal['context_json']).get('types') or []


def ieee_label(proposal):
    context = proposal['context']
    return _ieee_label(context.get('types') or [], context.get('apply_years'), proposal['year_from'], proposal['year_to'])


def propose(store, run, context):
    if run['database_name'] == IEEE and run['count_qualifier'] == 'exact':
        return _propose_ieee(store, run, context)
    if run['database_name'] != 'Scopus' or run['count_qualifier'] != 'exact':
        return None
    base, years = split_years(run['query_raw'])
    if base is None:
        return None
    context = dict(context)
    with store.lock, store.db:
        if store.db.execute('SELECT 1 FROM search_refinements WHERE run_id=?', (run['id'],)).fetchone():
            return None
        initial_count = run['count_value']
        parent = None
        if years:
            # New navigation is expected; never infer ancestry from query text alone.
            for row in store.db.execute("SELECT * FROM search_refinements WHERE state='approved' ORDER BY approved_at DESC"):
                prior = dict(row)
                prior_context = json.loads(prior['context_json'])
                prior_base, prior_years = split_years(prior['query'])
                if (all(prior_context.get(k) == context.get(k) for k in ('profile', 'windowId', 'tabId'))
                        and prior_base is not None and prior_years == years
                        and canonical(prior_base) == canonical(base)):
                    parent = prior
                    break
            if not parent:
                return None
            store.db.execute("UPDATE search_refinements SET state='captured',child_run_id=? WHERE id=?", (run['id'], parent['id']))
            note = f"{parent['display_id']} sorgusunun yıl sınırı uygulanmış hâli. {applied(parent['reason'])}"
            old_note = run['notes'] or ''
            store.db.execute('UPDATE search_runs SET notes=? WHERE id=?', ('\n'.join(x for x in (old_note, note) if x), run['id']))
            store.audit('refinement_captured', parent['id'], {'child': run['id']})
            initial_count = parent['initial_count']
            if json.loads(parent['context_json']).get('project_window'):
                return None  # A topic query takes the project window in one step; never narrow it further.
            if years != (2022, 2026) or initial_count <= 1000 or run['count_value'] <= 500:
                return None
            year_from = 2024
            reason = f"İlk sorgu {_n(initial_count)} sonuç; 2022–2026 sonucu {_n(run['count_value'])} (500'den fazla). Kılavuz Tablo 4'e göre 2024–2026 öneriliyor."
        else:
            window, chain = project_window(store)
            if window is not None:
                # The window was decided on the threshold query; topic queries reuse it whatever their size.
                if initial_count == 0:
                    return None
                year_from = window
                context['project_window'] = True
                reason = (f"Proje yıl penceresi {window}–2026 ({chain} daraltmasıyla belirlendi). "
                          f"Kılavuz Tablo 4'e göre pencere ilk sorguda bir kez belirlenir; bu sorguya da aynı pencere uygulanıyor.")
            elif initial_count <= 300:
                return None
            else:
                year_from = 2022
                reason = f"Yıl sınırı olmayan sorgu {_n(initial_count)} sonuç (300'den fazla). Kılavuz Tablo 4'e göre 2022–2026 öneriliyor."
        identity = str(uuid.uuid4())
        query = base + f' AND PUBYEAR > {year_from - 1} AND PUBYEAR < 2027'
        store.db.execute('INSERT INTO search_refinements VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',
                         (identity, run['id'], run['display_id'], initial_count, year_from, 2026,
                          run['query_raw'], run['count_value'], query, reason, json_text(context),
                          'offered', utcnow(), None, None))
        store.audit('refinement_offered', identity, {'run': run['id'], 'year_from': year_from, 'year_to': 2026})
        return get_proposal(store, identity)
