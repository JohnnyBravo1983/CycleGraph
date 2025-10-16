# app.py
from datetime import datetime, timedelta, timezone
from fastapi import FastAPI  # type: ignore
from fastapi.middleware.cors import CORSMiddleware  # type: ignore
from fastapi.responses import Response

app = FastAPI(title="CycleGraph Stub API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # stram inn senere ved behov
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def ts_ms(dt: datetime) -> int:
    """Returner tidspunkt som millisekunder siden epoch."""
    return int(dt.timestamp() * 1000)


@app.get("/api/trends")
def trends(bucket: str = "day", from_: str | None = None, to: str | None = None):
    """
    Returnerer et sett med dummy trendpunkter for testing.
    Første punkt (stub-0) har en unik verdi for å bekrefte LIVE-data.
    """
    now = datetime.now(timezone.utc)
    days = 14
    out = []

    for i in range(days):
        d = now - timedelta(days=days - i)

        # Fingeravtrykk for testing av LIVE (kun første punkt)
        if i == 0:
            out.append({
                "id": f"stub-{i}",
                "timestamp": ts_ms(d),
                "np": 321,
                "pw": 111,
                "source": "API",
                "calibrated": True,
            })
            continue

        # Normal generering for resten av punktene
        has_power = (i % 7 != 3)
        out.append({
            "id": f"stub-{i}",
            "timestamp": ts_ms(d),
            "np": 220 + (i % 5) * 3 if has_power else None,
            "pw": 210 + (i % 3) * 4 if has_power else None,
            "source": "API",
            "calibrated": (i % 4 != 0),
        })
    return out


@app.get("/api/sessions/summary")
def sessions_summary():
    """
    Returnerer en enkel summering for testing av fallback-endepunktet.
    """
    now = datetime.now(timezone.utc)
    sessions = []
    for i in range(6):
        d = now - timedelta(days=6 - i)
        sessions.append({
            "id": f"s{i+1}",
            "timestamp": ts_ms(d),
            "np": 200 + i * 5,
            "pw": 195 + i * 5,
            "calibrated": True,
        })
    return {"sessions": sessions}


@app.get("/favicon.ico")
def favicon():
    """Returnerer tomt svar slik at favicon 404 ikke spamer loggen."""
    return Response(status_code=204)
