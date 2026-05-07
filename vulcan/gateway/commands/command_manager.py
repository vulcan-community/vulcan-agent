from openai.types.chat import ChatCompletion

from .base_command import BaseCommand


class CommandManager:
    def __init__(self):
        self._commands: list[BaseCommand] = []

    def register_command(self, command: BaseCommand) -> None:
        self._commands.append(command)

    def list_commands(self) -> list[BaseCommand]:
        return list(self._commands)

    def match_command(self, command_text: str) -> BaseCommand | None:
        for command in self._commands:
            if command.match_command(command_text):
                return command
        return None

    def exec_command(
        self, command_text: str, channel_id: str, conversation_id: str
    ) -> ChatCompletion:
        command = self.match_command(command_text)
        if command is None:
            raise ValueError(f"Command '{command_text}' not found")

        args = command.parse_args(command_text)
        return command.exec(args, channel_id, conversation_id)
