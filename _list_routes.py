from app import app

rows = []
for r in app.routes:
    path = getattr(r, "path", None)
    if path and ("strava" in path or "auth" in path):
        methods = sorted(list(getattr(r, "methods", [])))
        rows.append((path, methods))

for p, m in sorted(rows):
    print(p, m)
