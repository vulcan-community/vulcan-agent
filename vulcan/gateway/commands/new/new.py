from typing import TYPE_CHECKING

from openai.types.chat import ChatCompletion

from ..base_command import BaseCommand

if TYPE_CHECKING:
    from ...gateway import Gateway


class NewCommand(BaseCommand):
    def __init__(self, gateway: "Gateway") -> None:
        super().__init__(
            command="new",
            description=(
                "Clear the current session (deletes its .jsonl and"
                " .meta.json). Next message starts fresh: /new"
            ),
        )
        self._gateway = gateway

    def exec(
        self, args: list[str], channel_id: str, session_id: str
    ) -> ChatCompletion:
        del args  # Unused.
        try:
            self._gateway.session_manager.delete_session(channel_id, session_id)
        except FileNotFoundError:
            return self._reply(
                f"No session to clear for {channel_id}/{session_id}."
            )
        except Exception as e:
            return self._reply(
                f"Failed to clear session: {type(e).__name__}: {e}"
            )
        return self._reply(
            f"Cleared session {channel_id}/{session_id}."
            " Next message starts fresh."
        )
