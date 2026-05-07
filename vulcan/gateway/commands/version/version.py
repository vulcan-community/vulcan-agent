from typing import TYPE_CHECKING

from openai.types.chat import ChatCompletion

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

    def exec(
        self, args: list[str], channel_id: str, conversation_id: str
    ) -> ChatCompletion:
        return self._reply(f"vulcan-agent {VERSION}")
