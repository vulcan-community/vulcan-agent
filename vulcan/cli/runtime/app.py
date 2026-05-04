import typer

from .install import install
from .list import list_runtimes
from .uninstall import uninstall

app = typer.Typer(help="Manage runtime backends")

app.command("list")(list_runtimes)
app.command("install")(install)
app.command("uninstall")(uninstall)
