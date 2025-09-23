# cli/bridge.py
from __future__ import annotations
import sys

try:
    from cyclegraph_core import analyze_session as rust_analyze_session
except Exception:
    rust_analyze_session = None

def _analyze_session_bridge(samples, meta, cfg):
    """
    Kaller Rust-kjernen (cyclegraph_core.analyze_session) med watts/puls.
    Returnerer JSON-lik dict/str fra Rust, eller et hr_only-objekt ved feil.
    """
    if rust_analyze_session is None:
        raise ImportError(
            "Ingen analyze_session i cyclegraph_core. "
            "Bygg i core/: 'maturin develop --release'."
        )

    try:
        valid = [
            s for s in samples
            if "watts" in s and "hr" in s and s["watts"] is not None and s["hr"] is not None
        ]
        watts = [s["watts"] for s in valid]
        pulses = [s["hr"] for s in valid]
    except Exception as e:
        raise ValueError(f"Feil ved uthenting av watt/puls: {e}")

    try:
        result = rust_analyze_session(watts, pulses)
        print(f"DEBUG: rust_analyze_session output = {result}", file=sys.stderr)
        return result
    except ValueError as e:
        print("⚠️ Ingen effekt-data registrert – enkelte metrikker begrenset.", file=sys.stderr)
        print(f"DEBUG: rust_analyze_session feilet med: {e}", file=sys.stderr)
        avg_p = (sum(pulses) / len(pulses)) if pulses else None
        return {"mode": "hr_only", "status": "LIMITED", "avg_pulse": avg_p}