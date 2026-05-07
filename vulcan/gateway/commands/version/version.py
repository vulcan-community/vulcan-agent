import time
import uuid
from typing import TYPE_CHECKING

from openai.types.chat import ChatCompletion
from openai.types.chat.chat_completion import Choice
from openai.types.chat.chat_completion_message import ChatCompletionMessage

from ....version import VERSION
from ..base_command import BaseCommand

if TYPE_CHECKING:
    from ...gateway import Gateway


class VersionCommand(BaseCommand):
    def __init__(self, gateway: "Gateway") -> None:
        super().__init__(
            command="version",
            description="Show the installed vulcan-agent version: /version",
        )
        self._gateway = gateway

    def exec(self, args: list[str]) -> ChatCompletion:
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
                        content=f"vulcan-agent {VERSION}",
                    ),
                )
            ],
        )
