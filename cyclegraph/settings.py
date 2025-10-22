# cyclegraph/settings.py
import os
from dataclasses import dataclass

@dataclass
class Settings:
    publish_to_strava: bool
    strava_access_token: str | None

def get_settings() -> Settings:
    flag = os.getenv("STRAVA_PUBLISH_ENABLED", "false").lower() in ("1","true","yes","on")
    token = os.getenv("STRAVA_ACCESS_TOKEN")
    return Settings(publish_to_strava=flag, strava_access_token=token)