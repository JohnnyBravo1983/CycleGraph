from . import main as _entrypoint

def main():
    # Delegerer til main() definert i cli/__init__.py
    _entrypoint()

if __name__ == "__main__":
    main()
