from dataclasses import dataclass
from typing import Optional, Dict

STRAVA_COMMENT_MAX = 280
STRAVA_DESC_HEADER_MAX = 140

ARROWS = {"up":"↑", "down":"↓"}
ELLIPSIS = "…"

@dataclass
class PublishPieces:
    comment: str
    desc_header: str
    desc_body: Optional[str]

def _pct(v: Optional[float], decimals=1) -> Optional[str]:
    if v is None: return None
    return f"{v:.{decimals}f}%"

def _num(v: Optional[float], decimals=2) -> Optional[str]:
    if v is None: return None
    return f"{v:.{decimals}f}"

def _trim(s: str, limit: int) -> str:
    if len(s) <= limit: return s
    return s[:max(0, limit-1)] + ELLIPSIS

def _lang_labels(lang: str):
    if lang == "en":
        return {
            "cgs":"CGS", "how_hard":"How hard", "how_long":"How long",
            "how_even":"How even & efficient", "trend":"Trend",
            "w_per_beat":"W/beat", "pa_hr":"Pa:Hr", "vi":"VI"
        }
    # default: norsk
    return {
        "cgs":"CGS", "how_hard":"Hvor hardt", "how_long":"Hvor lenge",
        "how_even":"Hvor jevnt & effektivt", "trend":"Trend",
        "w_per_beat":"W/slag", "pa_hr":"Pa:Hr", "vi":"VI"
    }

def build_publish_texts(report: Dict, lang: str="no") -> PublishPieces:
    L = _lang_labels(lang)

    # Hent felter med fallbacks
    s = report
    scores = s.get("scores", {})
    cgs = scores.get("cgs")
    intensity = scores.get("intensity")
    duration = scores.get("duration")
    quality = scores.get("quality")

    vi = s.get("vi")
    pa = s.get("pa_hr_pct")
    wpb = s.get("w_per_beat")
    wpb_base = s.get("w_per_beat_baseline")
    trend = (s.get("trend") or {}).get("cgs_delta_vs_last3")

    # Delta W/beat
    wpb_delta_pct = None
    if wpb is not None and wpb_base:
        wpb_delta_pct = (wpb - wpb_base) / wpb_base * 100.0

    # Kort kommentar (≤280)
    parts = []
    if cgs is not None: parts.append(f"CycleGraph {L['cgs']} {int(round(cgs))}")
    if s.get("if") is not None: parts.append(f"· IF {_num(s['if'],2)}")
    if vi is not None: parts.append(f"· {L['vi']} {_num(vi,2)}")
    if pa is not None: parts.append(f"· {L['pa_hr']} {_num(pa,1)}%")
    if wpb is not None:
        wpb_piece = f"· {L['w_per_beat']} {_num(wpb,2)}"
        if wpb_delta_pct is not None:
            arrow = ARROWS["up"] if wpb_delta_pct >= 0 else ARROWS["down"]
            wpb_piece += f" ({arrow}{_num(abs(wpb_delta_pct),0)}%)"
        parts.append(wpb_piece)
    if trend is not None:
        arrow = ARROWS["up"] if trend >= 0 else ARROWS["down"]
        parts.append(f"· {L['trend']} {arrow}{_num(abs(trend),0)}%")

    comment = _trim(" ".join(parts), STRAVA_COMMENT_MAX)

    # Lang beskrivelse (topp‑linje ≤140 + valgfri body)
    header_parts = []
    if cgs is not None:
        header_parts.append(f"{L['cgs']} {int(round(cgs))}")
    if intensity is not None and duration is not None and quality is not None:
        header_parts.append(
            f"– {L['how_hard']}:{int(round(intensity))} | "
            f"{L['how_long']}:{int(round(duration))} | "
            f"{L['how_even']}:{int(round(quality))}."
        )

    header_parts2 = []
    if vi is not None:
        header_parts2.append(f"{L['vi']} {_num(vi,2)}")
    if pa is not None:
        header_parts2.append(f"{L['pa_hr']} {_num(pa,1)}%")
    if wpb is not None:
        wpb_ex = f"{L['w_per_beat']} {_num(wpb,2)}"
        if wpb_delta_pct is not None:
            arrow = ARROWS["up"] if wpb_delta_pct >= 0 else ARROWS["down"]
            wpb_ex += f" ({arrow}{_num(abs(wpb_delta_pct),0)}%)."
        header_parts2.append(wpb_ex)

    # ← FIX: bare legg til separator hvis vi har del 2
    if header_parts2:
        header_str = " ".join(header_parts) + " · " + " ".join(header_parts2)
    else:
        header_str = " ".join(header_parts)

    desc_header = _trim(header_str, STRAVA_DESC_HEADER_MAX)

    # Body valgfri (kan utvides senere)
    desc_body = None
    return PublishPieces(comment=comment, desc_header=desc_header, desc_body=desc_body)
