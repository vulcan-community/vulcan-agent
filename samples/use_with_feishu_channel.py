from pathlib import Path

from vulcan.gateway.gateway import Gateway

gateway = Gateway(home_dir=Path("~/.vulcan").expanduser())

gateway.start()
