from .base_openai.base_openai import BaseOpenAIRuntime
from .base_runtime import BaseRuntime
from .claude_code.claude_code import ClaudeCodeRuntime
from .codex.codex import CodexRuntime

# Name → concrete BaseRuntime subclass. Modules defer their optional SDK
# imports into method bodies, so this top-level import works even when
# `claude-agent-sdk` / `openai-codex-sdk` aren't installed; each class's
# `is_installed()` reports whether its dependencies are actually present.
KNOWN_RUNTIMES: dict[str, type[BaseRuntime]] = {
    "base-openai": BaseOpenAIRuntime,
    "claude-code": ClaudeCodeRuntime,
    "codex": CodexRuntime,
}


def get_runtime_cls(name: str) -> type[BaseRuntime]:
    if name not in KNOWN_RUNTIMES:
        raise ValueError(f"Unsupported runtime: {name}")
    return KNOWN_RUNTIMES[name]
