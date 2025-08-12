# cli/strava_import.py
import os
import sys
import json
import time
import csv
import requests
import argparse
import calendar
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv, find_dotenv

# ---- Konfig ----
API_BASE = "https://www.strava.com/api/v3"
TOK_FILE = "data/strava_tokens.json"
SAFE_HEADROOM = 3  # antall kall du vil ha i “margin” før hard 15-min limit (økes i presstester)

# --- Last .env trygt fra prosjektrot ---
load_dotenv(find_dotenv(usecwd=True), override=True)


# =========================
#  Token-håndtering (M6.3)
# =========================
def load_tokens():
    """Les tokens fra disk med vennlige feilmeldinger og enkel validering."""
    if not os.path.exists(TOK_FILE):
        print(f"❌ Fant ikke tokenfil: {TOK_FILE}")
        print("➡️  Kjør autorisering først i to terminaler:")
        print("    Terminal A: python -u tools\\callback_server.py  (la stå åpen)")
        print("    Nettleser:  authorize-URL → kopier code")
        print("    Terminal B: python cli\\strava_auth.py <code>")
        raise SystemExit(1)
    try:
        with open(TOK_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        for k in ("access_token", "refresh_token", "expires_at"):
            if k not in data:
                raise ValueError(f"Mangler nøkkel '{k}' i {TOK_FILE}")
        return data
    except Exception as e:
        print(f"❌ Klarte ikke å lese tokenfilen: {e}")
        print("➡️  Slett filen og autoriser på nytt hvis den er korrupt:")
        print(f"    del {TOK_FILE}")
        print("    python -u tools\\callback_server.py  → authorize → code")
        print("    python cli\\strava_auth.py <code>")
        raise SystemExit(1)


def save_tokens(toks: dict):
    os.makedirs(os.path.dirname(TOK_FILE), exist_ok=True)
    with open(TOK_FILE, "w", encoding="utf-8") as f:
        json.dump(toks, f, indent=2)


def refresh_tokens(tokens: dict, client_id: str, client_secret: str) -> dict:
    """Utfør refresh_token-flow hos Strava og returner ny token-dict."""
    try:
        r = requests.post(
            "https://www.strava.com/api/v3/oauth/token",
            data={
                "client_id": client_id,
                "client_secret": client_secret,
                "grant_type": "refresh_token",
                "refresh_token": tokens["refresh_token"],
            },
            timeout=20,
        )
    except requests.RequestException as e:
        print(f"❌ Nett/requests-feil under refresh: {e}")
        raise SystemExit(1)

    if r.status_code != 200:
        print(f"❌ Refresh feilet (HTTP {r.status_code}): {r.text}")
        print("➡️  Prøv å autorisere på nytt:")
        print("    python -u tools\\callback_server.py → authorize → code")
        print("    python cli\\strava_auth.py <code>")
        raise SystemExit(1)

    new_t = r.json()
    save_tokens(new_t)  # viktig: Strava roterer refresh_token
    eta = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(new_t.get("expires_at", 0)))
    print(f"✅ Token fornyet. Utløper ca: {eta}")
    return new_t


def refresh_if_needed(tokens: dict, client_id: str, client_secret: str, leeway_secs: int = 3600) -> dict:
    """
    Forny access token hvis det utløper innen 'leeway_secs' (preemptivt).
    Strava roterer refresh_token → lagre alltid responsen til disk.
    """
    now = int(time.time())
    exp = int(tokens.get("expires_at", 0))
    if exp - now <= leeway_secs:
        print("🔁 Access token nær utløp — forsøker refresh...")
        return refresh_tokens(tokens, client_id, client_secret)
    return tokens


def auth_headers(access_token: str) -> dict:
    return {"Authorization": f"Bearer {access_token}"}


# =======================
#  Rate limit & GET-wrap
# =======================
def parse_rate_headers(resp):
    usage = resp.headers.get("X-RateLimit-Usage", "0,0")
    limit = resp.headers.get("X-RateLimit-Limit", "0,0")
    try:
        used_15, used_day = map(int, usage.split(","))
        lim_15, lim_day = map(int, limit.split(","))
    except Exception:
        used_15 = used_day = lim_15 = lim_day = 0
    return used_15, used_day, lim_15, lim_day


def seconds_until_next_15m_window():
    # Strava ruller hvert kvarter på wall-clock (0, 15, 30, 45 min)
    now = int(time.time())
    return 900 - (now % 900) + 2  # +2 sek margin

def strava_get(path_or_url: str, tokens: dict, params: dict = None, timeout: int = 30) -> dict | list:
    """Sikker GET mot Strava API som håndterer 401/403/429/5xx og nettverksfeil, med vennlige hint."""
    if path_or_url.startswith("http"):
        url = path_or_url
    else:
        url = API_BASE + path_or_url

    backoff = 2  # sek
    attempts = 0

    while True:
        try:
            r = requests.get(url, headers=auth_headers(tokens["access_token"]), params=params, timeout=timeout)
        except requests.RequestException as e:
            attempts += 1
            if attempts > 3:
                print(f"❌ Nettverksfeil mot Strava etter flere forsøk: {e}")
                print("➡️  Sjekk tilkobling/VPN/proxy og prøv igjen.")
                raise SystemExit(1)
            print(f"⚠️ Nettverksfeil ({e}). Prøver igjen om {backoff}s…")
            time.sleep(backoff)
            backoff = min(backoff * 2, 30)
            continue

        # 401: alltid tving refresh og prøv igjen
        if r.status_code == 401:
            cid = os.getenv("STRAVA_CLIENT_ID"); csec = os.getenv("STRAVA_CLIENT_SECRET")
            print("🔐 401 Unauthorized → prøver token-refresh…")
            new_t = refresh_tokens(tokens, cid, csec)
            tokens.update(new_t)
            continue

        # 403: sannsynlig manglende scope
        if r.status_code == 403:
            try:
                detail = r.json()
            except Exception:
                detail = r.text
            print("⛔ 403 Forbidden – ser ut som manglende scope (ofte 'activity:read_all').")
            print("➡️  Løsning: re-autoriser:")
            print("    1) python -u tools\\callback_server.py (la stå åpen)")
            print("    2) Kjør authorize-URL (med activity:read_all), logg inn, kopier code")
            print("    3) python cli\\strava_auth.py <code>")
            print(f"   (Detaljer: {detail})")
            raise SystemExit(1)

        # 429: vent til nytt 15-minutters-vindu
        if r.status_code == 429:
            used_15, _, lim_15, _ = parse_rate_headers(r)
            wait = seconds_until_next_15m_window()
            print(f"⏳ 429 Too Many Requests ({used_15}/{lim_15}). Venter {wait}s til nytt 15m-vindu…")
            time.sleep(wait)
            continue

        # 5xx: serverhikke → eksponentiell backoff og retry
        if 500 <= r.status_code < 600:
            attempts += 1
            if attempts > 5:
                print(f"❌ Vedvarende serverfeil {r.status_code} fra Strava. Avbryter.")
                raise SystemExit(1)
            print(f"⚠️ Serverfeil {r.status_code}. Prøver igjen om {backoff}s…")
            time.sleep(backoff)
            backoff = min(backoff * 2, 60)
            continue

        # Andre feil → vis kort og avbryt
        if r.status_code >= 400:
            try:
                msg = r.json()
            except Exception:
                msg = r.text
            print(f"❌ HTTP {r.status_code} fra Strava: {msg}")
            raise SystemExit(1)

        # OK
        # Ratelimit-headroom-logg (80% brukt)
        used_15, _, lim_15, _ = parse_rate_headers(r)
        if lim_15 and used_15 >= int(lim_15 * 0.8):
            wait = seconds_until_next_15m_window()
            print(f"⚠️ Nær 15-min rate limit ({used_15}/{lim_15}) – vurder å pause {wait}s…")

        try:
            return r.json()
        except ValueError:
            return {}



# ================
#  Hjelpefunksjoner
# ================
def iso_to_epoch(s: str) -> int:
    """Konverter ISO8601 'start_date' / 'start_date_local' til epoch (sekunder)."""
    if not s:
        return 0
    try:
        # Strava bruker som regel Z (UTC)
        if s.endswith("Z"):
            dt = datetime.strptime(s, "%Y-%m-%dT%H:%M:%SZ")
            return calendar.timegm(dt.timetuple())
        # Fallback: prøv fromisoformat (kan inneholde offset)
        dt = datetime.fromisoformat(s)
        # Hvis tzinfo finnes, konverter til UTC:
        if dt.tzinfo:
            return int(dt.timestamp())
        # Uten tz: anta lokal, gjør best effort
        return int(dt.timestamp())
    except Exception:
        return 0


def ensure_dir(path: str | Path):
    Path(path).mkdir(parents=True, exist_ok=True)


# ======================================
#  State for inkrementell sync (M6.4)
# ======================================
def state_path() -> Path:
    return Path.home() / ".config" / "cyclegraph" / "state.json"


def load_after_from_state() -> int:
    sp = state_path()
    if sp.exists():
        try:
            with open(sp, "r", encoding="utf-8") as f:
                return int(json.load(f).get("last_after", 0))
        except Exception:
            return 0
    return 0


def save_after_to_state(epoch_after: int):
    sp = state_path()
    sp.parent.mkdir(parents=True, exist_ok=True)
    with open(sp, "w", encoding="utf-8") as f:
        json.dump({"last_after": int(epoch_after)}, f)


# ==========================================
#  Aktiviteter: paging + since (M6.4)
# ==========================================
def fetch_activities(tokens: dict, after_epoch: int = 0, per_page: int = 200) -> list:
    all_acts = []
    page = 1
    while True:
        resp = strava_get(f"/athlete/activities?after={after_epoch}&page={page}&per_page={per_page}", tokens)
        if not resp:
            break
        # resp er liste med aktiviteter
        if isinstance(resp, list):
            if not resp:
                break
            all_acts.extend(resp)
            print(f"Hentet {len(all_acts)} aktiviteter…")
            page += 1
            # Slutt hvis vi fikk mindre enn per_page (ingen flere sider)
            if len(resp) < per_page:
                break
        else:
            break
    return all_acts


def cmd_activities(args, tokens: dict):
    if args.since:
        try:
            after = int(datetime.strptime(args.since, "%Y-%m-%d").timestamp())
        except ValueError:
            print("❌ --since må være på format YYYY-MM-DD, f.eks. 2025-07-01")
            raise SystemExit(1)
    else:
        after = load_after_from_state()

    acts = fetch_activities(tokens, after_epoch=after)
    ensure_dir(Path(args.out).parent)
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(acts, f, indent=2)

    # Oppdater state til seneste aktivitet
    if acts:
        # Bruk start_date_local primært, ellers start_date
        newest = max(acts, key=lambda a: iso_to_epoch(a.get("start_date_local") or a.get("start_date")))
        dt_iso = newest.get("start_date_local") or newest.get("start_date")
        newest_epoch = iso_to_epoch(dt_iso)
        if newest_epoch:
            save_after_to_state(newest_epoch)

    print(f"✅ Saved {len(acts)} aktiviteter → {args.out}")


# ==========================================
#  Streams → CSV (M6.5)
# ==========================================
def fetch_streams_for_activity(activity_id: int, tokens: dict) -> dict:
    keys = ["time", "heartrate", "watts", "moving", "altitude"]
    resp = strava_get(f"/activities/{activity_id}/streams?keys={','.join(keys)}&key_by_type=true", tokens)
    # resp forventes som dict pr nøkkel → {"time":{"data":[...]}, ...}
    def data_of(k): return (resp.get(k) or {}).get("data", [])
    return {
        "time": data_of("time"),
        "hr": data_of("heartrate"),
        "watts": data_of("watts"),
        "moving": data_of("moving"),
        "alt": data_of("altitude"),
    }


def write_stream_csv(activity_id: int, streams: dict, out_dir: str | Path) -> str:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{activity_id}.csv"

    T = streams["time"]; HR = streams["hr"]; W = streams["watts"]; M = streams["moving"]; A = streams["alt"]
    n = max(len(T), len(HR), len(W), len(M), len(A))

    with open(out_path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["activity_id", "index", "time_s", "hr", "watts", "moving", "altitude"])
        for i in range(n):
            w.writerow([
                activity_id,
                i,
                T[i] if i < len(T) else "",
                HR[i] if i < len(HR) else "",
                W[i] if i < len(W) else "",
                M[i] if i < len(M) else "",
                A[i] if i < len(A) else "",
            ])
    return str(out_path)


def cmd_streams(args, tokens: dict):
    # Samle mål-aktiviteter
    targets = []
    if args.activity_id:
        targets = [int(args.activity_id)]
    else:
        with open(args.from_activities, "r", encoding="utf-8") as f:
            acts = json.load(f)
        for a in acts:
            if args.type and a.get("type") != args.type:
                continue
            targets.append(int(a["id"]))
        if args.limit:
            targets = targets[: args.limit]

    written = 0
    for aid in targets:
        s = fetch_streams_for_activity(aid, tokens)
        p = write_stream_csv(aid, s, args.out)
        print(f"✓ {aid} → {p}")
        written += 1
    print(f"✅ Skrev {written} CSV-filer til {args.out}")


# ==========================
#  CLI (argparse) wiring
# ==========================
def build_cli():
    p = argparse.ArgumentParser(prog="strava_import")
    sub = p.add_subparsers(dest="cmd", required=True)

    a = sub.add_parser("activities", help="Hent aktiviteter (paging + since)")
    a.add_argument("--since", help='YYYY-MM-DD (valgfri)')
    a.add_argument("--out", default="data/activities.json")

    s = sub.add_parser("streams", help="Hent streams for aktiviteter")
    g = s.add_mutually_exclusive_group(required=True)
    g.add_argument("--activity-id", type=int)
    g.add_argument("--from-activities")  # path til activities.json
    s.add_argument("--type", default=None, help="Filtrer type (Ride/Run/...)")
    s.add_argument("--limit", type=int, default=None)
    s.add_argument("--out", default="data/streams")
    return p


# ==========================
#  Main
# ==========================
if __name__ == "__main__":
    CID = os.getenv("STRAVA_CLIENT_ID")
    CSECRET = os.getenv("STRAVA_CLIENT_SECRET")
    if not CID or not CSECRET:
        print("❌ STRAVA_CLIENT_ID / STRAVA_CLIENT_SECRET ikke satt i .env")
        raise SystemExit(1)

    tokens = load_tokens()
    tokens = refresh_if_needed(tokens, CID, CSECRET)  # M6.3

    # Info til konsoll
    exp_human = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(tokens.get("expires_at", 0)))
    athlete_id = (tokens.get("athlete") or {}).get("id")
    print(f"👤 Athlete ID: {athlete_id or 'ukjent'} | Token utløper ca: {exp_human}")

    parser = build_cli()
    args = parser.parse_args()

    if args.cmd == "activities":
        cmd_activities(args, tokens)    # M6.4
    elif args.cmd == "streams":
        cmd_streams(args, tokens)       # M6.5
