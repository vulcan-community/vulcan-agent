import typer

from ._helpers import extras, is_installed


def list_runtimes() -> None:
    """List all known runtimes and their installation status."""
    for name, pkgs in extras().items():
        installed = all(is_installed(p) for p in pkgs)
        mark = "✓" if installed else " "
        typer.echo(f"[{mark}] {name}")
