from typing import TYPE_CHECKING

from openai.types.chat import ChatCompletion

from ..base_command import BaseCommand

if TYPE_CHECKING:
    from ...gateway import Gateway


class SessionCommand(BaseCommand):
    def __init__(self, gateway: "Gateway") -> None:
        super().__init__(
            command="session",
            description=(
                "Show a session's raw JSONL: /session <channel>/<session_id>"
                " (or just <session_id> for an unambiguous match)"
            ),
        )
        self._gateway = gateway

    def exec(
        self, args: list[str], channel_id: str, conversation_id: str
    ) -> ChatCompletion:
        if not args:
            return self._reply(
                "Usage: /session <channel>/<session_id> or /session"
                " <session_id>. Run /sessions to see available ids."
            )
        spec = args[0]
        session_dir = self._gateway.session_manager.session_dir

        try:
            if "/" in spec:
                target_channel, target_session = spec.split("/", 1)
                path = session_dir / target_channel / f"{target_session}.jsonl"
                if not path.exists():
                    return self._reply(f"Session '{spec}' not found.")
            else:
                matches = list(session_dir.glob(f"*/{spec}.jsonl"))
                if len(matches) == 0:
                    return self._reply(f"Session '{spec}' not found.")
                if len(matches) > 1:
                    return self._reply(
                        f"Session id '{spec}' matches multiple channels:"
                        f" {[m.parent.name for m in matches]}."
                        " Use /session <channel>/<session_id>."
                    )
                path = matches[0]

            return self._reply(f"{path.read_text()}\n")
        except Exception as e:
            return self._reply(
                f"Failed to read session: {type(e).__name__}: {e}"
            )
