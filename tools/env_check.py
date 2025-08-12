# tools/env_check.py
import os, sys, io, pathlib
from dotenv import load_dotenv, find_dotenv, dotenv_values

root = pathlib.Path.cwd()  # nåværende mappe
env_file = root / ".env"

print("Working dir:", root)
print(".env path exists:", env_file.exists(), "-", env_file)
if env_file.exists():
    # Vis rå bytes (første 16 bytes er nok til å se BOM)
    raw = env_file.read_bytes()
    print("First 16 raw bytes:", raw[:16])
    print("--- .env lines (repr) ---")
    for i, line in enumerate(raw.splitlines(), 1):
        print(i, repr(line))

print("\nFØR load_dotenv:", repr(os.environ.get("STRAVA_CLIENT_ID")))
print("dotenv_values(.env):", dotenv_values(str(env_file)))
# Prøv å finne .env automatisk fra cwd:
dotfile = find_dotenv(usecwd=True)
print("find_dotenv(usecwd=True) ->", dotfile)

# Last og OVERRIDE eksisterende miljøvariabler
load_dotenv(dotfile or str(env_file), override=True)

print("ETTER load_dotenv:", repr(os.environ.get("STRAVA_CLIENT_ID")))
print("SECRET length:", len(os.environ.get("STRAVA_CLIENT_SECRET") or ""))
