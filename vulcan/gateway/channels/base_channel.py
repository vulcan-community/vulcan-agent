from abc import ABC
from typing import AsyncIterator, final

from openai.types.chat import ChatCompletion
from openai.types.conversations.message import Message
from typing_extensions import TYPE_CHECKING

from ...types.session import SessionItem

if TYPE_CHECKING:
    from ...runtime.base_runtime import BaseRuntime
    from ..gateway import Gateway


class BaseChannel(ABC):
    def __init__(
        self,
        name: str,
        gateway: "Gateway",
        default_runtime: "BaseRuntime",
        description: str = "",
        config: dict = {},
    ) -> None:
        self.name = name
        self.config = config
        self.gateway = gateway
        self.description = description

        self.runtime = default_runtime

    @final
    async def invoke(
        self,
        session_id: str,
        user_message: Message,
    ) -> ChatCompletion:
        return await self.gateway.invoke(self.name, session_id, user_message)

    @final
    async def invoke_stream(
        self,
        session_id: str,
        user_message: Message,
    ) -> AsyncIterator[SessionItem]:
        async for item in self.gateway.invoke_stream(
            self.name, session_id, user_message
        ):
            yield item
