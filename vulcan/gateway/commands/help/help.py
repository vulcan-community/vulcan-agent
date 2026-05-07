import time
import uuid
from typing import TYPE_CHECKING

from openai.types.chat import ChatCompletion
from openai.types.chat.chat_completion import Choice
from openai.types.chat.chat_completion_message import ChatCompletionMessage

from ..base_command import BaseCommand

if TYPE_CHECKING:
    from ...gateway import Gateway


class HelpCommand(BaseCommand):
    def __init__(self, gateway: "Gateway") -> None:
        super().__init__(
            command="help",
            description="List all available slash commands: /help",
        )
        self._gateway = gateway

    def exec(self, args: list[str]) -> ChatCompletion:
        rows: list[str] = []
        for cmd in self._gateway.command_manager.list_commands():
            rows.append(f"  /{cmd.command} — {cmd.description}")
        text = "Commands:\n" + ("\n".join(rows) if rows else "  (none)")

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
