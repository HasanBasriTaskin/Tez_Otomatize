"""Search-log descriptions prepared in one file (03_Calisma/arama_aciklamalari.json) and written to the matching
searches once. The previous texts are saved in Yedekler first; a later edit in the manager is never overwritten,
because the same file content is applied only one time."""
import json
from datetime import datetime
from pathlib import Path

from .storage import ValidationError, digest, json_text

RELATIVE = Path('03_Calisma') / 'arama_aciklamalari.json'


def apply(store):
    path = store.path(RELATIVE.as_posix())
    if not path.is_file():
        return 0
    content = path.read_bytes()
    stamp = digest(content)
    with store.lock:
        if store.db.execute("SELECT 1 FROM audit_events WHERE event='descriptions_applied' AND subject=?", (stamp,)).fetchone():
            return 0
    try:
        data = json.loads(content.decode('utf-8'))
    except ValueError as error:
        raise ValidationError(f'Arama açıklamaları dosyası okunamadı: {error}') from None
    texts = data.get('aciklamalar') if data.get('sema') == 1 else None
    if not isinstance(texts, dict) or not all(isinstance(k, str) and isinstance(v, str) for k, v in texts.items()):
        raise ValidationError('Arama açıklamaları dosyasının biçimi tanınmadı (sema 1, aciklamalar: {S001: "…"}).')
    runs = {r['display_id']: r for r in store.list_runs()}
    unknown = sorted(set(texts) - set(runs))
    if unknown:
        raise ValidationError('Arama açıklamaları dosyasında kaydı olmayan arama: ' + ', '.join(unknown[:10]))
    changes = {code: text.strip() for code, text in texts.items() if (runs[code]['notes'] or '').strip() != text.strip()}
    if changes:
        backup = f"Yedekler/arama_aciklamalari_onceki_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        store._atomic_write(backup, json_text({code: runs[code]['notes'] or '' for code in changes}).encode('utf-8'))
        for code, text in changes.items():
            store.update_run(runs[code]['id'], {'notes': text})
    with store.lock, store.db:
        store.audit('descriptions_applied', stamp, {'changed': len(changes)})
    return len(changes)
