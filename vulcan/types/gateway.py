from pathlib import Path
from typing import Dict

from pydantic import BaseModel, ConfigDict, Field

from ..version import VERSION


class ModelConfig(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    name: str = Field(
        default="",
        alias="model",
        description="Model identifier, e.g., claude-sonnet-4-5",
    )
    provider: str = Field(
        default="openai", description="Model provider, e.g., openai"
    )
    base_url: str = Field(
        default="https://ark.cn-beijing.volces.com/api/v3/chat/completions",
        description="Base URL for the model API",
    )
    api_key: str = Field(default="", description="API key for the model")


class RuntimeConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    enable: bool = Field(
        default=False, description="Whether to enable this runtime"
    )
    model: ModelConfig = Field(default_factory=ModelConfig)


class ChannelConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    enable: bool = Field(
        default=False, description="Whether to enable this channel"
    )
    runtime: str = Field(..., description="Runtime to use for this channel")
    config: Dict = Field(
        default_factory=dict, description="Channel-specific configuration"
    )


class GatewayConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    version: str = VERSION
    runtimes: Dict[str, RuntimeConfig] = Field(default_factory=dict)
    channels: Dict[str, ChannelConfig] = Field(default_factory=dict)

    def dump(self, home_dir: Path) -> None:
        config_path = home_dir / "vulcan.json"
        with open(config_path, "w") as f:
            f.write(self.model_dump_json(indent=4))
