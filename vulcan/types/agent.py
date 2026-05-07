from pydantic import BaseModel, Field

from .gateway import ModelConfig
from .skill import Skill


class Instruction(BaseModel):
    identity: str
    soul: str
    tool: str

    def render(self) -> str:
        """Join non-empty sections into a single persona prompt.

        Runtimes call this when they need the whole persona as one blob —
        either to inject via a system-prompt append (Claude Code) or to
        prepend into the user prompt when the SDK exposes no system
        slot (Codex).
        """
        return "\n\n".join(
            s for s in (self.identity, self.soul, self.tool) if s.strip()
        )


class AgentConfig(BaseModel):
    instruction: Instruction
    model: ModelConfig
    skills: list[Skill] = Field(default_factory=list)
