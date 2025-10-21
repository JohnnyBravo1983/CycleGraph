import click

# sessions-kommanden (den trenger vi garantert)
from .session import sessions as sessions_cmd

# analyze er valgfri – hvis den ikke finnes (eller heter noe annet), hopper vi over
try:
    from .analyze import analyze as analyze_cmd
except Exception:
    analyze_cmd = None

@click.group()
def cli():
    pass

# registrer valgfri analyze
if analyze_cmd is not None:
    cli.add_command(analyze_cmd)

# registrer sessions (viktig!)
cli.add_command(sessions_cmd)