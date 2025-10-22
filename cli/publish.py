# cli/publish.py
import click
from cyclegraph.publish import maybe_publish_to_strava
from cyclegraph.settings import get_settings
from cyclegraph.session_storage import load_session

@click.group(help="Publisering til Strava")
def publish():
    pass

@publish.command("run")
@click.argument("session_id")
@click.option("--token", envvar="STRAVA_ACCESS_TOKEN", help="Strava OAuth token.")
@click.option("--enabled/--disabled", default=None, help="Overstyr toggle for test.")
def run(session_id, token, enabled):
    s = get_settings()
    toggle = s.publish_to_strava if enabled is None else enabled
    tok = token or s.strava_access_token
    if not tok:
        click.echo("Mangler token. Sett STRAVA_ACCESS_TOKEN eller --token.")
        raise SystemExit(2)
    maybe_publish_to_strava(session_id, tok, toggle)
    sess = load_session(session_id)
    mark = "✓" if sess.get("publish_state") == "done" else ("…" if sess.get("publish_state") == "pending" else "✗")
    click.echo(f"{mark} {session_id}  state={sess.get('publish_state')}  time={sess.get('publish_time')}  hash={sess.get('publish_hash')}  err={sess.get('publish_error','') or ''}")
