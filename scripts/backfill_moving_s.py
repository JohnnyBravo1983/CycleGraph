import json
from pathlib import Path

state_root = Path('/app/state/users')
total_sessions = 0
patched = 0

for user_dir in state_root.iterdir():
    if not user_dir.is_dir():
        continue
    sessions_dir = user_dir / 'sessions'
    meta_path = user_dir / 'sessions_meta.json'
    if not sessions_dir.exists():
        continue

    meta = {}
    if meta_path.exists():
        try:
            meta = json.loads(meta_path.read_text())
        except:
            pass

    meta_changed = False

    for sf in sessions_dir.glob('session_*.json'):
        sid = sf.stem.replace('session_', '')
        total_sessions += 1
        try:
            doc = json.loads(sf.read_text())
            samples = doc.get('samples', [])
            if not samples:
                continue

            t_vals = [s.get('t') for s in samples if s.get('t') is not None]
            elapsed_s = int(round(max(t_vals))) if t_vals else None

            moving_count = sum(1 for s in samples if s.get('moving') is True)
            moving_s = moving_count if moving_count > 0 else elapsed_s

            changed = False
            if doc.get('elapsed_s') is None and elapsed_s:
                doc['elapsed_s'] = elapsed_s
                changed = True
            if doc.get('moving_s') is None and moving_s:
                doc['moving_s'] = moving_s
                changed = True

            if changed:
                sf.write_text(json.dumps(doc))
                patched += 1

            if sid in meta:
                if meta[sid].get('elapsed_s') is None and elapsed_s:
                    meta[sid]['elapsed_s'] = elapsed_s
                    meta_changed = True
                if meta[sid].get('moving_s') is None and moving_s:
                    meta[sid]['moving_s'] = moving_s
                    meta_changed = True

        except Exception as e:
            print(f'FEIL {sf}: {e}')

    if meta_changed and meta_path.exists():
        meta_path.write_text(json.dumps(meta))

print(f'Ferdig! Sjekket {total_sessions} sessions, patched {patched}')