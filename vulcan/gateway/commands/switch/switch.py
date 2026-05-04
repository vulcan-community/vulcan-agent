import time
import uuid
from typing import TYPE_CHECKING

from openai.types.chat import ChatCompletion
from openai.types.chat.chat_completion import Choice
from openai.types.chat.chat_completion_message import ChatCompletionMessage

from ..base_command import BaseCommand

if TYPE_CHECKING:
    from ...gateway import Gateway


class SwitchCommand(BaseCommand):
    def __init__(self, gateway: "Gateway") -> None:
        super().__init__(
            command="switch",
            description="Switch the current runtime: /switch <runtime_name>",
        )
        self._gateway = gateway

    def exec(self, args: list[str]) -> ChatCompletion:
        name = args[0]
        self._gateway.runtime_manager.switch_runtime(name)

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
                        content=f"Switched to runtime: {name}",
                    ),
                )
            ],
        )
