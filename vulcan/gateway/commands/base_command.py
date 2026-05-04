from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

from openai.types.chat import ChatCompletion
from pydantic import BaseModel

if TYPE_CHECKING:
    from ..gateway import Gateway


class CommandArgs(BaseModel): ...


class BaseCommand(ABC):
    def __init__(self, command: str, description: str) -> None:
        self.command = command
        self.description = description

        self._gateway: Gateway

    def match_command(self, command_text: str) -> bool:
        if not command_text.startswith("/"):
            return False
        if not command_text.split()[0][1:] == self.command:
            return False
        return True

    def parse_args(self, command_text: str) -> list[str]:
        return command_text.split()[1:]

    @abstractmethod
    def exec(self, args: list[str]) -> ChatCompletion: ...
