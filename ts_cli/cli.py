"""ts — trimmed ThoughtSpot CLI for the ts-convert-from-sisense skill.

Only the command groups the skill uses are registered: sisense, tml, auth, profiles.
"""
from __future__ import annotations

import typer

from ts_cli.commands import auth, profiles, sisense, tml

app = typer.Typer(
    name="ts",
    help="ThoughtSpot CLI (Sisense conversion subset).",
    no_args_is_help=True,
    pretty_exceptions_show_locals=False,
)

app.add_typer(auth.app, name="auth")
app.add_typer(profiles.app, name="profiles")
app.add_typer(sisense.app, name="sisense")
app.add_typer(tml.app, name="tml")


def main() -> None:
    app()


if __name__ == "__main__":
    main()
