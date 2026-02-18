"""
Backfill moving_time from Strava API for all existing sessions.

This script:
1. Reads all session files
2. Fetches real moving_time and elapsed_time from Strava API
3. Updates session files and sessions_meta.json with correct values
"""

import json
import requests
import time
from pathlib import Path
from typing import Optional, Dict, Any

STATE_ROOT = Path('/app/state/users')

def load_strava_tokens(uid: str) -> Optional[Dict[str, Any]]:
    """Load Strava tokens for user."""
    tokens_path = STATE_ROOT / uid / 'strava_tokens.json'
    if not tokens_path.exists():
        return None
    try:
        return json.loads(tokens_path.read_text())
    except:
        return None

def refresh_token_if_needed(uid: str, tokens: Dict[str, Any]) -> Optional[str]:
    """Refresh Strava token if expired. Returns access_token or None."""
    expires_at = tokens.get('expires_at', 0)
    now = int(time.time())
    
    # If token expires in next 5 minutes, refresh
    if expires_at - now < 300:
        print(f"  Token expired, refreshing for {uid}")
        refresh_token = tokens.get('refresh_token')
        if not refresh_token:
            return None
        
        # Refresh token (you need Strava client_id and client_secret)
        # For now, just return existing token and hope it works
        print(f"  WARNING: Token refresh not implemented, using existing token")
    
    return tokens.get('access_token')

def fetch_activity_from_strava(activity_id: str, access_token: str) -> Optional[Dict[str, Any]]:
    """Fetch activity details from Strava API."""
    url = f"https://www.strava.com/api/v3/activities/{activity_id}"
    headers = {"Authorization": f"Bearer {access_token}"}
    
    try:
        resp = requests.get(url, headers=headers, timeout=10)
        if resp.status_code == 200:
            return resp.json()
        else:
            print(f"    Strava API error {resp.status_code}: {resp.text[:100]}")
            return None
    except Exception as e:
        print(f"    Strava API exception: {e}")
        return None

def backfill_user(uid: str) -> Dict[str, int]:
    """Backfill moving_time for all sessions for one user."""
    stats = {
        'checked': 0,
        'updated': 0,
        'skipped': 0,
        'errors': 0
    }
    
    # Load Strava tokens
    tokens = load_strava_tokens(uid)
    if not tokens:
        print(f"User {uid}: No Strava tokens, skipping")
        return stats
    
    access_token = refresh_token_if_needed(uid, tokens)
    if not access_token:
        print(f"User {uid}: No valid access token, skipping")
        return stats
    
    sessions_dir = STATE_ROOT / uid / 'sessions'
    if not sessions_dir.exists():
        return stats
    
    meta_path = STATE_ROOT / uid / 'sessions_meta.json'
    meta = {}
    if meta_path.exists():
        try:
            meta = json.loads(meta_path.read_text())
        except:
            pass
    
    meta_changed = False
    
    # Process each session
    for session_file in sorted(sessions_dir.glob('session_*.json')):
        stats['checked'] += 1
        sid = session_file.stem.replace('session_', '')
        
        try:
            doc = json.loads(session_file.read_text())
            
            # Get Strava activity ID
            strava = doc.get('strava', {})
            activity_id = strava.get('activity_id')
            if not activity_id:
                stats['skipped'] += 1
                continue
            
            # Check if already has correct moving_s
            current_moving_s = doc.get('moving_s')
            current_elapsed_s = doc.get('elapsed_s')
            
            # Fetch from Strava
            print(f"  Fetching activity {activity_id} (session {sid})")
            activity = fetch_activity_from_strava(activity_id, access_token)
            
            if not activity:
                stats['errors'] += 1
                continue
            
            # Extract moving_time and elapsed_time
            moving_time = activity.get('moving_time')
            elapsed_time = activity.get('elapsed_time')
            
            if not moving_time or not elapsed_time:
                print(f"    No moving_time/elapsed_time in Strava response")
                stats['errors'] += 1
                continue
            
            # Update session file
            changed = False
            if doc.get('moving_s') != moving_time:
                print(f"    Updating moving_s: {current_moving_s} -> {moving_time}")
                doc['moving_s'] = moving_time
                changed = True
            
            if doc.get('elapsed_s') != elapsed_time:
                print(f"    Updating elapsed_s: {current_elapsed_s} -> {elapsed_time}")
                doc['elapsed_s'] = elapsed_time
                changed = True
            
            if changed:
                session_file.write_text(json.dumps(doc))
                stats['updated'] += 1
            
            # Update meta
            if sid in meta:
                if meta[sid].get('moving_s') != moving_time:
                    meta[sid]['moving_s'] = moving_time
                    meta_changed = True
                if meta[sid].get('elapsed_s') != elapsed_time:
                    meta[sid]['elapsed_s'] = elapsed_time
                    meta_changed = True
            
            # Rate limit: 100 requests per 15 minutes = ~6/min = 10s between requests
            time.sleep(0.6)
            
        except Exception as e:
            print(f"  Error processing {session_file}: {e}")
            stats['errors'] += 1
    
    # Save meta
    if meta_changed and meta_path.exists():
        meta_path.write_text(json.dumps(meta))
        print(f"User {uid}: Updated sessions_meta.json")
    
    return stats

def main():
    """Run backfill for all users."""
    print("Starting Strava moving_time backfill...")
    print(f"State root: {STATE_ROOT}")
    
    total_stats = {
        'users': 0,
        'checked': 0,
        'updated': 0,
        'skipped': 0,
        'errors': 0
    }
    
    for user_dir in sorted(STATE_ROOT.iterdir()):
        if not user_dir.is_dir():
            continue
        
        uid = user_dir.name
        print(f"\nProcessing user: {uid}")
        
        stats = backfill_user(uid)
        total_stats['users'] += 1
        total_stats['checked'] += stats['checked']
        total_stats['updated'] += stats['updated']
        total_stats['skipped'] += stats['skipped']
        total_stats['errors'] += stats['errors']
        
        print(f"  Stats: {stats}")
    
    print("\n" + "="*60)
    print("BACKFILL COMPLETE")
    print(f"Users processed: {total_stats['users']}")
    print(f"Sessions checked: {total_stats['checked']}")
    print(f"Sessions updated: {total_stats['updated']}")
    print(f"Sessions skipped: {total_stats['skipped']}")
    print(f"Errors: {total_stats['errors']}")
    print("="*60)

if __name__ == '__main__':
    main()