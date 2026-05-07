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
        """Wrap `text` into the conventional `vulcan-system` ChatCompletion.
        Every command replies with this shape, so subclasses just build a
        string and call `self._reply(...)`.
        """
        return system_completion(text)

    def _current_session_id(self, channel_id: str, conversation_id: str) -> str:
        """Resolve the current session id for the calling conversation,
        creating a fresh one if this is the first touch. Commands that
        mutate session-level state (`/switch`, `/status`, `/runtime`)
        use this to avoid duplicating the `resolve_current_session` call
        pattern at each site.
        """
        gw = self._gateway
        return gw.session_manager.resolve_current_session(
            channel_id, conversation_id, gw.config.default_runtime
        )

    @abstractmethod
    def exec(
        self, args: list[str], channel_id: str, conversation_id: str
    ) -> ChatCompletion:
        """Run the command.

        `channel_id` identifies the front-end transport (API server,
        Feishu, ...). `conversation_id` is the user-facing stable address
        — the same across `/new` rotations. Commands that need the
        concrete session can resolve it via `self._current_session_id()`.
        """
        ...
