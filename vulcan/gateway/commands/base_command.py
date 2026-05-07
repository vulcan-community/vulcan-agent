from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

from openai.types.chat import ChatCompletion

from ...utils.completions import system_completion

if TYPE_CHECKING:
    from ..gateway import Gateway


class BaseCommand(ABC):
    def __init__(self, command: str, description: str) -> None:
        self.command = command
        self.description = description

        self._gateway: "Gateway"

    def match_command(self, command_text: str) -> bool:
        if not command_text.startswith("/"):
            return False
        if not command_text.split()[0][1:] == self.command:
            return False
        return True

    def parse_args(self, command_text: str) -> list[str]:
        return command_text.split()[1:]

    @staticmethod
    def _reply(text: str) -> ChatCompletion:
        """Wrap `text` into the conventional `vulcan-system` ChatCompletion
        — every command replies with this shape, so subclasses just build
        a string and call `self._reply(...)`."""
        return system_completion(text)

    @abstractmethod
    def exec(
        self, args: list[str], channel_id: str, session_id: str
    ) -> ChatCompletion:
        """Run the command.

        `channel_id` + `session_id` identify the session that issued the
        command. Commands that mutate session state (e.g. `/switch`) need
        them; stateless commands (e.g. `/version`, `/help`) can ignore.
        """
        ...
