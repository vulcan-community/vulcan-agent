import time
import uuid
from typing import TYPE_CHECKING

from openai.types.chat import ChatCompletion
from openai.types.chat.chat_completion import Choice
from openai.types.chat.chat_completion_message import ChatCompletionMessage

from ....runtime import is_runtime_installed, list_runtime_names
from ..base_command import BaseCommand

if TYPE_CHECKING:
    from ...gateway import Gateway


class RuntimeCommand(BaseCommand):
    def __init__(self, gateway: "Gateway") -> None:
        super().__init__(
            command="runtime",
            description=(
                "List every known runtime and its status"
                " (current / enabled / disabled / not installed /"
                " not configured): /runtime"
            ),
        )
        self._gateway = gateway

    def exec(self, args: list[str]) -> ChatCompletion:
        mgr = self._gateway.runtime_manager
        cfg = self._gateway.config.runtimes

        rows: list[str] = []
        for name in list_runtime_names():
            registered = mgr.get_runtime(name)
            if registered is not None and registered is mgr.curr_runtime:
                mark, status = "*", "current"
            elif registered is not None:
                mark, status = " ", "enabled"
            elif not is_runtime_installed(name):
                mark, status = " ", "not installed"
            elif name not in cfg:
                mark, status = " ", "not configured"
            elif not cfg[name].enable:
                mark, status = " ", "disabled"
            else:
                mark, status = " ", "registration failed"
            rows.append(f"  [{mark}] {name:<16s} — {status}")

        text = "Runtimes:\n" + ("\n".join(rows) if rows else "  (none)")

        return ChatCompletion(
            id=str(uuid.uuid4()),
            object="chat.completion",
            created=int(time.time()),
            model="vulcan-system",
            choices=[
                Choice(
                    index=0,
                    finish_reason="stop",
                    message=ChatCompletionMessage(
                        role="assistant",
                        content=text,
                    ),
                )
            ],
        )
