from typing import TYPE_CHECKING

from openai.types.chat import ChatCompletion

from ..base_command import BaseCommand

if TYPE_CHECKING:
    from ...gateway import Gateway


class RuntimeCommand(BaseCommand):
    def __init__(self, gateway: "Gateway") -> None:
        super().__init__(
            command="runtime",
            description=(
                "List every known runtime and its status"
                " (enabled / disabled / uninstalled)."
                " The `*` marks this session's current runtime: /runtime"
            ),
        )
        self._gateway = gateway

    def exec(
        self, args: list[str], channel_id: str, session_id: str
    ) -> ChatCompletion:
        mgr = self._gateway.runtime_manager
        sess = self._gateway.session_manager
        curr = (
            sess.get_session_runtime(channel_id, session_id)
            or self._gateway.config.default_runtime
        )
        rows: list[str] = []
        for name, status in mgr.status.items():
            mark = "*" if status == "enabled" and name == curr else " "
            rows.append(f"  [{mark}] {name:<16s} — {status}")
        text = "Runtimes:\n" + ("\n".join(rows) if rows else "  (none)")
        return self._reply(text)
