from typing import List

from pydantic import BaseModel, Field

from .gateway import ModelConfig
from .skill import Skill


class Instruction(BaseModel):
    identity: str
    soul: str
    tool: str


class AgentConfig(BaseModel):
    instruction: Instruction
    model: ModelConfig
    skills: List[Skill] = Field(default_factory=list)
