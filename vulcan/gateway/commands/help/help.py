from typing import TYPE_CHECKING

from openai.types.chat import ChatCompletion

from ..base_command import BaseCommand

if TYPE_CHECKING:
    from ...gateway import Gateway


class HelpCommand(BaseCommand):
    def __init__(self, gateway: "Gateway") -> None:
        super().__init__(
            command="help",
            description="List all available slash commands: /help",
        )
        self._gateway = gateway

    def exec(
        self, args: list[str], channel_id: str, session_id: str
    ) -> ChatCompletion:
        rows = [
            f"  /{cmd.command} — {cmd.description}"
            for cmd in self._gateway.command_manager.list_commands()
        ]
        text = "Commands:\n" + ("\n".join(rows) if rows else "  (none)")
        return self._reply(text)
