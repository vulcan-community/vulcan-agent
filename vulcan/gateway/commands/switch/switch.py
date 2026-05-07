from typing import TYPE_CHECKING

from openai.types.chat import ChatCompletion

from ..base_command import BaseCommand

if TYPE_CHECKING:
    from ...gateway import Gateway


class SwitchCommand(BaseCommand):
    def __init__(self, gateway: "Gateway") -> None:
        super().__init__(
            command="switch",
            description=(
                "Switch this session's runtime: /switch <runtime_name>."
                " Only affects the current session — other sessions keep"
                " their own bindings."
            ),
        )
        self._gateway = gateway

    def exec(
        self, args: list[str], channel_id: str, conversation_id: str
    ) -> ChatCompletion:
        try:
            if not args:
                return self._reply(
                    "Usage: /switch <runtime_name>."
                    " Run /runtime to see enabled runtimes."
                )
            name = args[0]
            if self._gateway.runtime_manager.get_runtime(name) is None:
                return self._reply(
                    f"Runtime '{name}' is not enabled. See /runtime."
                )
            session_id = self._current_session_id(channel_id, conversation_id)
            self._gateway.session_manager.set_session_runtime(
                channel_id, session_id, name
            )
            return self._reply(f"Switched this session to runtime: {name}.")
        except Exception as e:
            return self._reply(f"Failed to switch: {type(e).__name__}: {e}")
