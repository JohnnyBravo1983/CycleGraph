# cyclegraph/settings.py

import os
from dataclasses import dataclass

# --- Helper for miljøvariabler ---
def _env_bool(name: str, default: bool) -> bool:
    v = os.getenv(name)
    if v is None:
        return default
    v = v.strip().lower()
    return v in ("1", "true", "yes", "y", "on")

# --- Analyzerelaterte toggles (trygge defaults) ---
ANALYZE_ALLOW_INLINE_DEFAULT = False
USE_STUB_FALLBACK_DEFAULT    = True

@dataclass
class Settings:
    publish_to_strava: bool
    strava_access_token: str | None

    # Nye toggles for analyze-flowet
    ANALYZE_ALLOW_INLINE: bool = ANALYZE_ALLOW_INLINE_DEFAULT
    USE_STUB_FALLBACK: bool    = USE_STUB_FALLBACK_DEFAULT


def get_settings() -> Settings:
    # Eksisterende felter
    flag = os.getenv("STRAVA_PUBLISH_ENABLED", "false").lower() in ("1", "true", "yes", "on")
    token = os.getenv("STRAVA_ACCESS_TOKEN")

    # Opprett settings-objekt
    settings = Settings(publish_to_strava=flag, strava_access_token=token)

    # Nye toggles med miljøvariabler
    analyze_allow_inline = _env_bool("CG_ANALYZE_ALLOW_INLINE", ANALYZE_ALLOW_INLINE_DEFAULT)
    use_stub_fallback    = _env_bool("CG_USE_STUB_FALLBACK",    USE_STUB_FALLBACK_DEFAULT)

    # Sett verdier på objektet
    settings.ANALYZE_ALLOW_INLINE = analyze_allow_inline
    settings.USE_STUB_FALLBACK    = use_stub_fallback

    return settings
