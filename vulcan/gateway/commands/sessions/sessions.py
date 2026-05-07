from datetime import datetime
from typing import TYPE_CHECKING

from openai.types.chat import ChatCompletion

from ..base_command import BaseCommand

if TYPE_CHECKING:
    from ...gateway import Gateway


class SessionsCommand(BaseCommand):
    def __init__(self, gateway: "Gateway") -> None:
        super().__init__(
            command="sessions",
            description="List sessions: /sessions",
        )
        self._gateway = gateway

    def exec(
        self, args: list[str], channel_id: str, session_id: str
    ) -> ChatCompletion:
        session_dir = self._gateway.session_manager.session_dir
        rows: list[tuple[float, str]] = []
        if session_dir.exists():
            for channel_dir in session_dir.iterdir():
                if not channel_dir.is_dir():
                    continue
                for f in channel_dir.glob("*.jsonl"):
                    ts = f.stat().st_ctime
                    when = datetime.fromtimestamp(ts).isoformat(
                        timespec="seconds"
                    )
                    rows.append((ts, f"  {channel_dir.name}/{f.stem}  {when}"))
        rows.sort(reverse=True)
        text = "Sessions:\n" + (
            "\n".join(r for _, r in rows) if rows else "  (none)"
        )
        return self._reply(text)
