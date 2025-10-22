# cli/__init__.py
from __future__ import annotations
import click

@click.group()
def cli():
    """CycleGraph CLI"""
    pass

def main():
    # ⚠️ Lazy imports – skjer først når vi faktisk kjører CLI'en
    from .session import sessions as sessions_cmd
    from .publish import publish as publish_cmd
    # Legg til flere når du trenger dem, f.eks. analyze-kommando-gruppe hvis du har
    try:
        from .analyze import analyze as analyze_cmd  # hvis du har en analyze-kommando (valgfritt)
        cli.add_command(analyze_cmd, name="analyze")
    except Exception:
        # analyze-modulen kan kjøres separat med `python -m cli.analyze`
        pass

    cli.add_command(sessions_cmd, name="sessions")
    cli.add_command(publish_cmd, name="publish")
    cli()

if __name__ == "__main__":
    main()
