from abc import ABC, abstractmethod
from typing import AsyncIterator

from ..types.agent import AgentConfig
from ..types.invocation import InvocationContext
from ..types.session import SessionItem


class BaseRuntime(ABC):
    def __init__(
        self,
        name: str,
        agent_config: AgentConfig,
        description: str = "",
    ) -> None:
        self.name = name
        self.description = description
        self.agent_config = agent_config

    @abstractmethod
    def invoke(
        self, ctx: InvocationContext
    ) -> AsyncIterator[SessionItem]: ...
