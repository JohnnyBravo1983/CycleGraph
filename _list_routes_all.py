from app import app
for r in app.routes:
    path = getattr(r, "path", None)
    methods = sorted(list(getattr(r, "methods", [])))
    if path:
        print(f"{path} {methods}")
