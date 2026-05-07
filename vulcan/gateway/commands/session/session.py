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
        self, args: list[str], channel_id: str, session_id: str
    ) -> ChatCompletion:
        spec = args[0]
        session_dir = self._gateway.session_manager.session_dir

        if "/" in spec:
            target_channel, target_session = spec.split("/", 1)
            path = session_dir / target_channel / f"{target_session}.jsonl"
        else:
            matches = list(session_dir.glob(f"*/{spec}.jsonl"))
            assert len(matches) == 1, (
                f"expected 1 match for session id '{spec}', got {len(matches)}"
            )
            path = matches[0]

        return self._reply(f"{path.read_text()}\n")
