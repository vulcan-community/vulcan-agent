from typing import TYPE_CHECKING

from openai.types.chat import ChatCompletion

from ..base_command import BaseCommand

if TYPE_CHECKING:
    from ...gateway import Gateway


class ResumeCommand(BaseCommand):
    def __init__(self, gateway: "Gateway") -> None:
        super().__init__(
            command="resume",
            description=(
                "Point this conversation at an existing session:"
                " /resume <session_id>"
            ),
        )
        self._gateway = gateway

    def exec(
        self, args: list[str], channel_id: str, conversation_id: str
    ) -> ChatCompletion:
        try:
            if not args:
                return self._reply(
                    "Usage: /resume <session_id>."
                    " Run /sessions to see available ids."
                )
            sid = args[0]
            session_manager = self._gateway.session_manager
            if not session_manager.session_exists(channel_id, sid):
                return self._reply(
                    f"Session '{sid}' not found in channel '{channel_id}'."
                )
            actual = session_manager.get_session_conversation(channel_id, sid)
            if actual is None:
                return self._reply(
                    f"Session '{sid}' has no meta — cannot confirm"
                    " it belongs to this conversation."
                )
            if actual != conversation_id:
                return self._reply(
                    f"Session '{sid}' belongs to a different"
                    f" conversation ('{actual}'), not"
                    f" '{conversation_id}'."
                )
            session_manager.set_current_session_id(
                channel_id, conversation_id, sid
            )
            runtime_name = (
                session_manager.get_session_runtime(channel_id, sid) or "(none)"
            )
            return self._reply(
                f"Resumed session {sid} (runtime: {runtime_name})."
            )
        except Exception as e:
            return self._reply(f"Failed to resume: {type(e).__name__}: {e}")
