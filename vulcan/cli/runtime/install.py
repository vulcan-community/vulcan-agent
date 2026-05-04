import subprocess

import typer

from ._helpers import extras


def install(name: str) -> None:
    """Install a runtime by extra name."""
    if name not in extras():
        typer.echo(f"unknown runtime: {name}")
        raise typer.Exit(1)
    subprocess.run(["uv", "sync", "--extra", name], check=True)
