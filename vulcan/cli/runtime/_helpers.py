import re
import tomllib
from importlib.metadata import PackageNotFoundError, distribution
from pathlib import Path

_PYPROJECT = Path(__file__).resolve().parents[3] / "pyproject.toml"


def extras() -> dict[str, list[str]]:
    """{extra_name: [package_names]} from pyproject.toml."""
    data = tomllib.loads(_PYPROJECT.read_text())
    raw = data["project"].get("optional-dependencies", {})
    return {
        name: [re.split(r"[<>=!~\[;\s]", s, maxsplit=1)[0] for s in specs]
        for name, specs in raw.items()
    }


def is_installed(pkg: str) -> bool:
    try:
        distribution(pkg)
        return True
    except PackageNotFoundError:
        return False
