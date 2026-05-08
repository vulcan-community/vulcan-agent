import importlib.util
import json
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Literal

from ...types.invocation import InvocationContext
from ...types.session import SessionItem
from ...utils.logger import get_logger
from ...utils.messages import (
    assistant_message,
    message_text,
    reasoning_item,
    tool_call_item,
    tool_output_item,
)
from ..base_runtime import BaseRuntime

logger = get_logger(__name__)


class ClaudeCodeRuntime(BaseRuntime):
    def is_installed(self) -> bool:
        return importlib.util.find_spec("claude_agent_sdk") is not None

    async def invoke(
        self, ctx: InvocationContext
    ) -> AsyncIterator[SessionItem]:
        # Deferred import so the class module can be loaded even when the
        # optional `claude-agent-sdk` isn't installed (is_installed()
        # reports that state without triggering the import).
        from claude_agent_sdk import (
            AssistantMessage,
            ClaudeAgentOptions,
            ClaudeSDKClient,
            StreamEvent,
            UserMessage,
        )

        history_text = message_text(ctx.history_message)
        current_text = message_text(ctx.message)

        model_cfg = self.agent_config.model
        env: dict[str, str] = {}
        if model_cfg.base_url:
            env["ANTHROPIC_BASE_URL"] = model_cfg.base_url
        if model_cfg.api_key:
            env["ANTHROPIC_API_KEY"] = model_cfg.api_key

        cwd, setting_sources, skills_flag = self._resolve_skills_workspace(
            has_env=bool(env)
        )

        options = ClaudeAgentOptions(
            model=model_cfg.name or None,
            env=env,
            cwd=str(cwd) if cwd else None,
            setting_sources=setting_sources,
            skills=skills_flag,
            max_thinking_tokens=4000,
            # Ask the SDK to forward the raw Anthropic stream events so
            # we can yield per-chunk text/thinking deltas — otherwise the
            # SDK only emits one `AssistantMessage` at the end with the
            # fully assembled text, which looks like "no streaming".
            include_partial_messages=True,
            system_prompt={
                "type": "preset",
                "preset": "claude_code",
                "append": self.agent_config.instruction.render(),
            },
        )
        async with ClaudeSDKClient(options=options) as client:
            # The SDK's `query` takes a single user-message string. Prepend
            # the gateway-prepared history (if any) so the model sees prior
            # context before the current turn.
            query = (
                f"{history_text}\n\n{current_text}"
                if history_text
                else current_text
            )
            await client.query(query)
            async for msg in client.receive_response():
                # StreamEvent carries raw Anthropic API events; we pull
                # text_delta / thinking_delta out of them for progressive
                # rendering in channels.
                if isinstance(msg, StreamEvent):
                    item = self._stream_event_to_item(msg.event)
                    if item is not None:
                        yield item
                # AssistantMessage arrives with fully-assembled blocks at
                # block-completion boundaries. We already streamed text
                # and thinking via deltas, so here we only surface
                # non-text artifacts (tool_use).
                elif isinstance(msg, AssistantMessage):
                    for block in msg.content:
                        item = self._non_text_block_to_item(block)
                        if item is not None:
                            yield item
                # UserMessage echoes tool results from the agent's tool
                # runs. These are block-granular; no delta needed.
                elif isinstance(msg, UserMessage):
                    content = msg.content
                    if isinstance(content, list):
                        for block in content:
                            item = self._block_to_item(block)
                            if item is not None:
                                yield item

    def _stream_event_to_item(self, event: dict) -> SessionItem | None:
        """Translate a raw Anthropic stream event into a delta SessionItem.
        Only `content_block_delta` events with `text_delta` /
        `thinking_delta` are surfaced; everything else (start/stop, tool
        input json deltas, message-level events) is ignored and picked up
        later via the assembled `AssistantMessage`.
        """
        if event.get("type") != "content_block_delta":
            return None
        delta = event.get("delta") or {}
        dtype = delta.get("type")
        if dtype == "text_delta":
            text = delta.get("text") or ""
            return assistant_message(text) if text else None
        if dtype == "thinking_delta":
            thinking = delta.get("thinking") or ""
            return reasoning_item(thinking) if thinking else None
        return None

    def _non_text_block_to_item(self, block) -> SessionItem | None:
        """Filter variant of `_block_to_item` that skips text/thinking —
        those are streamed via deltas to avoid double-emission."""
        from claude_agent_sdk import TextBlock, ThinkingBlock

        if isinstance(block, (TextBlock, ThinkingBlock)):
            return None
        return self._block_to_item(block)

    def _block_to_item(self, block) -> SessionItem | None:
        from claude_agent_sdk import (
            TextBlock,
            ThinkingBlock,
            ToolResultBlock,
            ToolUseBlock,
        )

        if isinstance(block, TextBlock):
            return assistant_message(block.text)
        if isinstance(block, ThinkingBlock):
            return reasoning_item(block.thinking)
        if isinstance(block, ToolUseBlock):
            return tool_call_item(
                call_id=block.id,
                name=block.name,
                arguments=block.input,
            )
        if isinstance(block, ToolResultBlock):
            content = block.content
            if isinstance(content, list):
                output = json.dumps(content, ensure_ascii=False)
            else:
                output = content or ""
            return tool_output_item(
                call_id=block.tool_use_id,
                output=output,
                is_error=block.is_error or False,
            )
        return None

    def _resolve_skills_workspace(
        self, has_env: bool
    ) -> tuple[
        Path | None,
        list[Literal["user", "project", "local"]] | None,
        Literal["all"] | None,
    ]:
        """Wire the SDK to discover skills from Vulcan's `skills_dir/`.

        Claude Code's SDK only looks in `<cwd>/.claude/skills/` (project
        setting_source) or the user's `~/.claude/skills/` (user source).
        To expose Vulcan's `<home_dir>/skills/` we symlink
        `<home_dir>/.claude/skills` → `<home_dir>/skills` and point the
        SDK at `<home_dir>` as cwd. The user source is always excluded
        so Vulcan doesn't leak the local `~/.claude/` into isolated
        deployments.

        Returns (cwd, setting_sources, skills_flag). When `skills_dir`
        is None, falls back to the previous isolation behavior (empty
        setting_sources iff custom env is injected, else SDK defaults).
        """
        if self.skills_dir is None:
            return None, ([] if has_env else None), None

        home = self.skills_dir.parent
        project_skills = home / ".claude" / "skills"
        project_skills.parent.mkdir(parents=True, exist_ok=True)
        if not project_skills.exists():
            try:
                project_skills.symlink_to(
                    self.skills_dir, target_is_directory=True
                )
            except OSError as e:
                logger.warning(
                    f"could not symlink {project_skills} → "
                    f"{self.skills_dir}: {e}. skills may not load."
                )
        return home, ["project"], "all"
