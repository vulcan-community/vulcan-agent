from ..utils.logger import get_logger
from .base_runtime import BaseRuntime

logger = get_logger(__name__)


class RuntimeManager:
    def __init__(self):
        self._runtimes: dict[str, BaseRuntime] = {}
        self.curr_runtime: BaseRuntime | None = None

    def register_runtime(self, runtime: BaseRuntime) -> None:
        self._runtimes[runtime.name] = runtime
        if self.curr_runtime is None:
            self.curr_runtime = runtime
            logger.info(
                f"registered runtime: {runtime.name} (set as curr_runtime)"
            )
        else:
            logger.info(f"registered runtime: {runtime.name}")

    def get_runtime(self, name: str) -> BaseRuntime | None:
        return self._runtimes.get(name)

    def list_runtimes(self) -> list[BaseRuntime]:
        return list(self._runtimes.values())

    def switch_runtime(self, name: str) -> BaseRuntime:
        runtime = self._runtimes.get(name)
        if runtime is None:
            raise ValueError(f"Runtime '{name}' not found")
        self.curr_runtime = runtime
        logger.info(f"switched curr_runtime to: {name}")
        return runtime
