# API inventory

Generated: 2026-02-07 16:12:44

## Endpoints

| Method | Path | File | Line |
|---|---|---|---:|
| POST | /api/auth/login | server\routes\auth_local.py | 111 |
| POST | /api/auth/logout | server\routes\auth_local.py | 146 |
| GET | /api/auth/me | server\routes\auth_local.py | 185 |
| POST | /api/auth/signup | server\routes\auth_local.py | 59 |
| GET | /api/auth/strava/callback | server\routes\auth_strava.py | 408 |
| GET | /api/auth/strava/login | server\routes\auth_strava.py | 387 |
| GET | /api/profile/get | server\routes\profile_router.py | 13 |
| PUT | /api/profile/save | server\routes\profile_router.py | 24 |
| GET | /api/sessions/{session_id} | server\routes\sessions.py | 3540 |
| POST | /api/sessions/{sid}/analyze | server\routes\sessions.py | 2016 |
| POST | /api/sessions/{sid}/analyze_sessionspy | server\routes\sessions.py | 3504 |
| POST | /api/sessions/debug/rb | server\routes\sessions.py | 1722 |
| GET | /api/sessions/list | server\routes\sessions.py | 1121 |
| GET | /api/sessions/list | server\routes\sessions_list_router.py | 1075 |
| GET | /api/sessions/list/_debug_paths | server\routes\sessions_list_router.py | 1170 |
| GET | /api/sessions/list/all | server\routes\sessions_list_router.py | 1130 |
| POST | /api/strava/import/{rid} | server\routes\strava_import_router.py | 1090 |
| POST | /api/strava/import/{rid} | server\routes\strava_import_router_for_commit.py | 925 |
| POST | /api/strava/sync | server\routes\strava_import_router.py | 761 |
| POST | /api/strava/sync | server\routes\strava_import_router_for_commit.py | 629 |
| GET | /callback | server\routes\auth_strava.py | 315 |
| GET | /login | server\routes\auth_strava.py | 275 |
| GET | /status | server\routes\auth_strava.py | 244 |
