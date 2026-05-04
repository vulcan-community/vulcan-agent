import time
import uuid
from typing import TYPE_CHECKING

from openai.types.chat import ChatCompletion
from openai.types.chat.chat_completion import Choice
from openai.types.chat.chat_completion_message import ChatCompletionMessage

from ..base_command import BaseCommand

if TYPE_CHECKING:
    from ...gateway import Gateway


class RuntimesCommand(BaseCommand):
    def __init__(self, gateway: "Gateway") -> None:
        super().__init__(
            command="runtimes",
            description="List registered runtimes: /runtimes",
        )
        self._gateway = gateway

    def exec(self, args: list[str]) -> ChatCompletion:
        mgr = self._gateway.runtime_manager

        rows: list[str] = []
        for rt in mgr.list_runtimes():
            mark = "*" if rt is mgr.curr_runtime else " "
            suffix = f" — {rt.description}" if rt.description else ""
            rows.append(f"  [{mark}] {rt.name}{suffix}")
        text = "Runtimes:\n" + ("\n".join(rows) if rows else "  (none)")

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
