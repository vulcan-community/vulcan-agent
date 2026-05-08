from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from pathlib import Path

from ..types.agent import AgentConfig
from ..types.invocation import InvocationContext
from ..types.session import SessionItem


class BaseRuntime(ABC):
    def __init__(
        self,
        name: str,
        agent_config: AgentConfig,
        skills_dir: Path | None = None,
        description: str = "",
    ) -> None:
        self.name = name
        self.description = description
        self.agent_config = agent_config
        # Absolute path to the shared skills directory
        # (`<home_dir>/skills`). Each subdirectory containing a `SKILL.md`
        # is one skill. Subclasses decide how to expose skills to their
        # backend — native mechanism (Claude Code) vs. persona injection
        # (Codex, base OpenAI). None disables skills entirely.
        self.skills_dir = skills_dir

    @abstractmethod
    def invoke(self, ctx: InvocationContext) -> AsyncIterator[SessionItem]: ...

    @abstractmethod
    def is_installed(self) -> bool: ...
