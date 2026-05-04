import time
import uuid
from typing import TYPE_CHECKING

from openai.types.chat import ChatCompletion
from openai.types.chat.chat_completion import Choice
from openai.types.chat.chat_completion_message import ChatCompletionMessage

from ..base_command import BaseCommand

if TYPE_CHECKING:
    from ...gateway import Gateway


class SessionCommand(BaseCommand):
    def __init__(self, gateway: "Gateway") -> None:
        super().__init__(
            command="session",
            description=(
                "Show a session's raw JSONL: /session <user>/<session_id>"
                " (or just <session_id> for an unambiguous match)"
            ),
        )
        self._gateway = gateway

    def exec(self, args: list[str]) -> ChatCompletion:
        spec = args[0]
        session_dir = self._gateway.session_manager.session_dir

        if "/" in spec:
            user_id, session_id = spec.split("/", 1)
            path = session_dir / user_id / f"{session_id}.jsonl"
        else:
            matches = list(session_dir.glob(f"*/{spec}.jsonl"))
            assert len(matches) == 1, (
                f"expected 1 match for session id '{spec}', got {len(matches)}"
            )
            path = matches[0]

        raw = path.read_text()
        text = f"{raw}\n"

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
