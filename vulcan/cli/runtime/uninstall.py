import subprocess

import typer

from ._helpers import extras


def uninstall(name: str) -> None:
    """Uninstall a runtime by extra name."""
    pkgs = extras().get(name)
    if not pkgs:
        typer.echo(f"unknown runtime: {name}")
        raise typer.Exit(1)
    subprocess.run(["uv", "pip", "uninstall", *pkgs], check=True)
