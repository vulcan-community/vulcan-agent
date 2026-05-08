"""Codex runtime — wraps the `openai-codex-sdk` which itself wraps the
bundled `codex` CLI binary over stdio JSONL.

The SDK has no system-prompt slot, so Vulcan's persona is prepended into
the prompt text. History (gateway-rendered) and current input are joined
and sent as one prompt via `thread.run_streamed()`; we then translate
each SDK event into a SessionItem.

Notes:
  * Codex wants a git-tracked cwd by default — we set
    `skip_git_repo_check=True` so Vulcan can run anywhere.
  * `approval_policy="never"` so the CLI doesn't block on interactive
    confirmations (Vulcan runs non-interactively).
  * Text/reasoning items arrive as full-buffer updates; we compute
    deltas by tracking per-item text length.
  * SDK imports are deferred into methods so this module still loads
    when the optional `openai-codex-sdk` isn't installed (is_installed()
    reports that without triggering the import).
"""

import importlib.util
import json
from collections.abc import AsyncIterator

from ...types.invocation import InvocationContext
from ...types.session import SessionItem
from ...utils.messages import (
    assistant_message,
    message_text,
    reasoning_item,
    tool_call_item,
    tool_output_item,
)
from ...utils.skills import load_skills, render_skills_prompt
from ..base_runtime import BaseRuntime


class CodexRuntime(BaseRuntime):
    def is_installed(self) -> bool:
        return importlib.util.find_spec("openai_codex_sdk") is not None

    async def invoke(
        self, ctx: InvocationContext
    ) -> AsyncIterator[SessionItem]:
        from openai_codex_sdk import Codex

        history_text = message_text(ctx.history_message)
        current_text = message_text(ctx.message)
        persona = self.agent_config.instruction.render()
        # Codex has no native skill mechanism; eagerly inject every
        # skill's SKILL.md into the prompt preamble so the agent sees
        # them. Cost scales with skill count — prune your skills dir.
        skills_blob = render_skills_prompt(load_skills(self.skills_dir))
        prompt = "\n\n".join(
            p for p in (persona, skills_blob, history_text, current_text) if p
        )

        model_cfg = self.agent_config.model
        codex = Codex(
            {
                "api_key": model_cfg.api_key or None,
                "base_url": model_cfg.base_url or None,
            }
        )
        thread = codex.start_thread(
            {
                "model": model_cfg.name or None,
                "skip_git_repo_check": True,
                "sandbox_mode": "workspace-write",
                "approval_policy": "never",
            }
        )

        streamed = await thread.run_streamed(prompt)
        # Per-item text length so streaming text/reasoning updates yield
        # only the new delta rather than the growing full buffer.
        seen_len: dict[str, int] = {}

        async for event in streamed.events:
            for item in self._event_to_items(event, seen_len):
                yield item

    def _event_to_items(
        self, event, seen_len: dict[str, int]
    ) -> list[SessionItem]:
        from openai_codex_sdk import (
            ItemCompletedEvent,
            ItemStartedEvent,
            ItemUpdatedEvent,
        )

        if isinstance(event, ItemStartedEvent):
            return self._on_item_started(event.item)
        if isinstance(event, ItemUpdatedEvent):
            return self._on_item_updated(event.item, seen_len)
        if isinstance(event, ItemCompletedEvent):
            return self._on_item_completed(event.item, seen_len)
        return []

    def _on_item_started(self, item) -> list[SessionItem]:
        from openai_codex_sdk import (
            CommandExecutionItem,
            McpToolCallItem,
            WebSearchItem,
        )

        if isinstance(item, CommandExecutionItem):
            return [
                tool_call_item(
                    call_id=item.id,
                    name="shell",
                    arguments={"command": item.command},
                )
            ]
        if isinstance(item, McpToolCallItem):
            return [
                tool_call_item(
                    call_id=item.id,
                    name=f"{item.server}.{item.tool}",
                    arguments=item.arguments or {},
                )
            ]
        if isinstance(item, WebSearchItem):
            return [
                tool_call_item(
                    call_id=item.id,
                    name="web_search",
                    arguments={"query": item.query},
                )
            ]
        return []

    def _on_item_updated(
        self, item, seen_len: dict[str, int]
    ) -> list[SessionItem]:
        from openai_codex_sdk import AgentMessageItem, ReasoningItem

        if isinstance(item, AgentMessageItem):
            delta = self._delta(item.id, item.text, seen_len)
            return [assistant_message(delta)] if delta else []
        if isinstance(item, ReasoningItem):
            delta = self._delta(item.id, item.text, seen_len)
            return [reasoning_item(delta)] if delta else []
        return []

    def _on_item_completed(
        self, item, seen_len: dict[str, int]
    ) -> list[SessionItem]:
        from openai_codex_sdk import (
            AgentMessageItem,
            CommandExecutionItem,
            ErrorItem,
            FileChangeItem,
            McpToolCallItem,
            ReasoningItem,
            WebSearchItem,
        )

        if isinstance(item, AgentMessageItem):
            delta = self._delta(item.id, item.text, seen_len)
            return [assistant_message(delta)] if delta else []
        if isinstance(item, ReasoningItem):
            delta = self._delta(item.id, item.text, seen_len)
            return [reasoning_item(delta)] if delta else []
        if isinstance(item, CommandExecutionItem):
            return [
                tool_output_item(
                    call_id=item.id,
                    output=item.aggregated_output,
                    is_error=item.status == "failed",
                )
            ]
        if isinstance(item, McpToolCallItem):
            if item.error is not None:
                output = getattr(item.error, "message", "") or str(item.error)
            elif item.result is not None:
                output = self._dump(item.result)
            else:
                output = ""
            return [
                tool_output_item(
                    call_id=item.id,
                    output=output,
                    is_error=item.status == "failed" or item.error is not None,
                )
            ]
        if isinstance(item, FileChangeItem):
            summary = self._dump(
                [{"path": c.path, "kind": c.kind} for c in (item.changes or [])]
            )
            # FileChangeItem has no started event, so emit a tool call +
            # tool output pair here so the chain is self-contained.
            return [
                tool_call_item(
                    call_id=item.id,
                    name="file_change",
                    arguments={"changes": summary},
                ),
                tool_output_item(
                    call_id=item.id,
                    output=summary,
                    is_error=item.status == "failed",
                ),
            ]
        if isinstance(item, WebSearchItem):
            return [
                tool_output_item(
                    call_id=item.id,
                    output=f"searched: {item.query}",
                    is_error=False,
                )
            ]
        if isinstance(item, ErrorItem):
            return [assistant_message(f"[codex error] {item.message}")]
        return []

    @staticmethod
    def _delta(item_id: str, full_text: str, seen_len: dict[str, int]) -> str:
        n = seen_len.get(item_id, 0)
        if len(full_text) <= n:
            return ""
        seen_len[item_id] = len(full_text)
        return full_text[n:]

    @staticmethod
    def _dump(obj) -> str:
        if hasattr(obj, "model_dump"):
            obj = obj.model_dump()
        try:
            return json.dumps(obj, ensure_ascii=False, default=str)
        except (TypeError, ValueError):
            return str(obj)
