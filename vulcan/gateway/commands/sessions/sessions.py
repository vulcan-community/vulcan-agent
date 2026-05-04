import time
import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from openai.types.chat import ChatCompletion
from openai.types.chat.chat_completion import Choice
from openai.types.chat.chat_completion_message import ChatCompletionMessage

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

    def exec(self, args: list[str]) -> ChatCompletion:
        session_dir = self._gateway.session_manager.session_dir
        rows: list[tuple[float, str]] = []
        if session_dir.exists():
            for user_dir in session_dir.iterdir():
                if not user_dir.is_dir():
                    continue
                for f in user_dir.glob("*.jsonl"):
                    ts = f.stat().st_ctime
                    when = datetime.fromtimestamp(ts).isoformat(
                        timespec="seconds"
                    )
                    rows.append(
                        (ts, f"  {user_dir.name}/{f.stem}  {when}")
                    )
        rows.sort(reverse=True)
        text = "Sessions:\n" + (
            "\n".join(r for _, r in rows) if rows else "  (none)"
        )

        return ChatCompletion(
            id=str(uuid.uuid4()),
            object="chat.completion",
            created=int(time.time()),
            model="vulcan-system",
            choices=[
                Choice(
                    index=0,
                    finish_reason="stop",
                    message=ChatCompletionMessage(
                        role="assistant",
                        content=text,
                    ),
                )
            ],
        )
