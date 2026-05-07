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
                "Start a fresh session on this conversation. Allocates a"
                " new session id and points the conversation at it;"
                " inherits the runtime from the previous session: /new"
            ),
        )
        self._gateway = gateway

    def exec(
        self, args: list[str], channel_id: str, conversation_id: str
    ) -> ChatCompletion:
        del args
        try:
            new_session = self._gateway.session_manager.rotate_current_session(
                channel_id,
                conversation_id,
                self._gateway.config.default_runtime,
            )
        except Exception as e:
            return self._reply(
                f"Failed to start new session: {type(e).__name__}: {e}"
            )
        runtime = self._gateway.session_manager.get_session_runtime(
            channel_id, new_session
        )
        return self._reply(
            f"Started new session {new_session} (runtime: {runtime})."
        )
