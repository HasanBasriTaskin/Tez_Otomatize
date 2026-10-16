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
        "LEFT JOIN search_runs c ON c.id = r.child_run_id WHERE r.state = 'captured' "
        "ORDER BY r.year_from DESC, r.created_at DESC LIMIT 1").fetchone()
    if not row or not 1990 <= row['year_from'] <= 2026:
        return None, None
    return row['year_from'], f"{row['display_id']} → {row['child'] or '?'}"


def propose(store, run, context):
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
            note = f"{parent['display_id']} devamı: {parent['reason']}"
            old_note = run['notes'] or ''
            store.db.execute('UPDATE search_runs SET notes=? WHERE id=?', ('\n'.join(x for x in (old_note, note) if x), run['id']))
            store.audit('refinement_captured', parent['id'], {'child': run['id']})
            initial_count = parent['initial_count']
            if json.loads(parent['context_json']).get('project_window'):
                return None  # A topic query takes the project window in one step; never narrow it further.
            if years != (2022, 2026) or initial_count <= 1000 or run['count_value'] <= 500:
                return None
            year_from = 2024
            reason = f"İlk sorgu {initial_count:,} sonuç; 2022–2026 sonucu {run['count_value']:,} > 500. 2024–2026 öneriliyor."
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
                reason = f"Yıl sınırı olmayan sorgu {initial_count:,} sonuç > 300. Rehbere göre 2022–2026 öneriliyor."
        identity = str(uuid.uuid4())
        query = base + f' AND PUBYEAR > {year_from - 1} AND PUBYEAR < 2027'
        store.db.execute('INSERT INTO search_refinements VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',
                         (identity, run['id'], run['display_id'], initial_count, year_from, 2026,
                          run['query_raw'], run['count_value'], query, reason, json_text(context),
                          'offered', utcnow(), None, None))
        store.audit('refinement_offered', identity, {'run': run['id'], 'year_from': year_from, 'year_to': 2026})
        return get_proposal(store, identity)
