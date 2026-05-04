from .base_runtime import BaseRuntime


def get_runtime_cls(name: str) -> type[BaseRuntime]:
    if name == "claude-code":
        from .claude_code.claude_code import ClaudeCodeRuntime

        return ClaudeCodeRuntime
    raise ValueError(f"Unsupported runtime: {name}")
