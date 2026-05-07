from .base_runtime import BaseRuntime

KNOWN_RUNTIMES: tuple[str, ...] = ("base-openai", "claude-code")


def list_runtime_names() -> list[str]:
    return list(KNOWN_RUNTIMES)


def get_runtime_cls(name: str) -> type[BaseRuntime]:
    if name == "base-openai":
        from .base_openai.base_openai import BaseOpenAIRuntime

        return BaseOpenAIRuntime
    if name == "claude-code":
        from .claude_code.claude_code import ClaudeCodeRuntime

        return ClaudeCodeRuntime
    raise ValueError(f"Unsupported runtime: {name}")


def is_runtime_installed(name: str) -> bool:
    """Attempt to import the runtime class. Returns False if the optional
    dependency isn't installed (ImportError) or the name isn't known."""
    try:
        get_runtime_cls(name)
    except (ImportError, ValueError):
        return False
    return True
