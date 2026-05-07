from abc import ABC
from collections.abc import AsyncIterator
from typing import TYPE_CHECKING, final

from openai.types.chat import ChatCompletion
from openai.types.conversations.message import Message

from ...types.session import SessionItem

if TYPE_CHECKING:
    from ..gateway import Gateway


class BaseChannel(ABC):
    def __init__(
        self,
        name: str,
        gateway: "Gateway",
        description: str = "",
        config: dict = {},
    ) -> None:
        self.name = name
        self.config = config
        self.gateway = gateway
        self.description = description

    @final
    async def invoke(
        self,
        conversation_id: str,
        user_message: Message,
    ) -> ChatCompletion:
        return await self.gateway.invoke(
            self.name, conversation_id, user_message
        )

    @final
    async def invoke_stream(
        self,
        conversation_id: str,
        user_message: Message,
    ) -> AsyncIterator[SessionItem]:
        async for item in self.gateway.invoke_stream(
            self.name, conversation_id, user_message
        ):
            yield item
