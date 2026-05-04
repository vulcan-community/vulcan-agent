import typer

from .runtime.app import app as runtime_app

app = typer.Typer(help="Vulcan Agent CLI")
app.add_typer(runtime_app, name="runtime")


if __name__ == "__main__":
    app()
