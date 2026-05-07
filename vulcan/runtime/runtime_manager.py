from typing import Literal

from ..types.agent import AgentConfig
from ..types.gateway import RuntimeConfig
from ..utils.logger import get_logger
from .base_runtime import BaseRuntime

logger = get_logger(__name__)

RuntimeStatus = Literal["enabled", "disabled", "uninstalled"]


class RuntimeManager:
    """Registry of runtime instances + their installation/enabled status.

    The manager does NOT own a "current runtime" — runtime selection is
    per-session and lives in the session's sidecar meta file. Use
    `get_runtime(name)` to look one up.
    """

    def __init__(self):
        self._runtimes: dict[str, BaseRuntime] = {}
        # Tracks every known runtime type (not just the ones we registered):
        #   - "enabled"     → installed + configured + live in self._runtimes
        #   - "disabled"    → installed but not enabled in vulcan.json
        #   - "uninstalled" → optional SDK dep not importable
        self.status: dict[str, RuntimeStatus] = {}

    def register(
        self,
        name: str,
        cls: type[BaseRuntime],
        cfg: RuntimeConfig | None,
        agent_config: AgentConfig,
    ) -> None:
        """Probe one runtime type and record its status.

        Instantiates the class (cheap — constructors don't touch the SDK
        binary) so it can call the instance's `is_installed()`. A runtime
        is only added to `self._runtimes` when it is both installed and
        enabled in config; otherwise we just record the status.
        """
        instance = cls(name=name, agent_config=agent_config)

        if not instance.is_installed():
            self.status[name] = "uninstalled"
            logger.info(f"runtime uninstalled, skip: {name}")
            return

        if cfg is None or not cfg.enable:
            self.status[name] = "disabled"
            logger.info(f"runtime disabled, skip: {name}")
            return

        self._runtimes[name] = instance
        self.status[name] = "enabled"
        logger.info(f"registered runtime: {name} ({cls.__name__})")

    def get_runtime(self, name: str) -> BaseRuntime | None:
        return self._runtimes.get(name)

    def list_runtimes(self) -> list[BaseRuntime]:
        return list(self._runtimes.values())
