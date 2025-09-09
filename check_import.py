import importlib, sys
for m in ['cyclegraph','cyclegraph_core','cg_core']:
    try:
        importlib.import_module(m)
        print("OK python import:", m)
        sys.exit(0)
    except Exception:
        pass
sys.exit(1)
