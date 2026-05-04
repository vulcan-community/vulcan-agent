import json
import uuid
from typing import AsyncIterator

from claude_agent_sdk import (
    AssistantMessage,
    ClaudeAgentOptions,
    ClaudeSDKClient,
    TextBlock,
    ThinkingBlock,
    ToolResultBlock,
    ToolUseBlock,
    UserMessage,
)
from openai.types.conversations.message import Message
from openai.types.responses.response_function_tool_call_item import (
    ResponseFunctionToolCallItem,
)
from openai.types.responses.response_function_tool_call_output_item import (
    ResponseFunctionToolCallOutputItem,
)
from openai.types.responses.response_output_text import ResponseOutputText
from openai.types.responses.response_reasoning_item import (
    Content as ReasoningContent,
    ResponseReasoningItem,
)

from ...types.invocation import InvocationContext
from ...types.session import SessionItem
from ..base_runtime import BaseRuntime


class ClaudeCodeRuntime(BaseRuntime):
    async def invoke(
        self, ctx: InvocationContext
    ) -> AsyncIterator[SessionItem]:
        items = ctx.session.items
        history = self._render_history(items[:-1])
        new_msg = self._text(items[-1])

        model_cfg = self.agent_config.model
        env: dict[str, str] = {}
        if model_cfg.base_url:
            env["ANTHROPIC_BASE_URL"] = model_cfg.base_url
        if model_cfg.api_key:
            env["ANTHROPIC_API_KEY"] = model_cfg.api_key

        # When we inject custom auth, isolate from local CC settings
        # so user's OAuth / apiKeyHelper does not override our config.
        setting_sources = [] if env else None

        options = ClaudeAgentOptions(
            model=model_cfg.name or None,
            env=env,
            setting_sources=setting_sources,
            max_thinking_tokens=4000,
            system_prompt={
                "type": "preset",
                "preset": "claude_code",
                "append": self._persona_prompt(history),
            },
        )
        async with ClaudeSDKClient(options=options) as client:
            await client.query(new_msg)
            async for msg in client.receive_response():
                # AssistantMessage holds the model's blocks: text, thinking,
                # and tool-use calls.
                if isinstance(msg, AssistantMessage):
                    for block in msg.content:
                        item = self._block_to_item(block)
                        if item is not None:
                            yield item
                # UserMessage echoes tool results from the agent's tool runs.
                elif isinstance(msg, UserMessage):
                    content = msg.content
                    if isinstance(content, list):
                        for block in content:
                            item = self._block_to_item(block)
                            if item is not None:
                                yield item

    def _block_to_item(self, block) -> SessionItem | None:
        if isinstance(block, TextBlock):
            return Message(
                id=str(uuid.uuid4()),
                type="message",
                role="assistant",
                status="completed",
                content=[
                    ResponseOutputText(
                        type="output_text",
                        text=block.text,
                        annotations=[],
                    )
                ],
            )
        if isinstance(block, ThinkingBlock):
            return ResponseReasoningItem(
                id=str(uuid.uuid4()),
                type="reasoning",
                summary=[],
                content=[
                    ReasoningContent(
                        type="reasoning_text", text=block.thinking
                    )
                ],
            )
        if isinstance(block, ToolUseBlock):
            return ResponseFunctionToolCallItem(
                id=str(uuid.uuid4()),
                type="function_call",
                call_id=block.id,
                name=block.name,
                arguments=json.dumps(block.input, ensure_ascii=False),
                status="completed",
            )
        if isinstance(block, ToolResultBlock):
            content = block.content
            if isinstance(content, list):
                output = json.dumps(content, ensure_ascii=False)
            else:
                output = content or ""
            return ResponseFunctionToolCallOutputItem(
                id=str(uuid.uuid4()),
                type="function_call_output",
                call_id=block.tool_use_id,
                output=output,
                status="incomplete" if block.is_error else "completed",
            )
        return None

    def _persona_prompt(self, history: str) -> str:
        """Compose Vulcan's persona (identity + soul + tool guidance) and
        append the prior conversation, to be injected after Claude Code's
        default system prompt."""
        i = self.agent_config.instruction
        sections = [i.identity, i.soul, i.tool]
        if history:
            sections.append(f"# Prior conversation\n\n{history}")
        return "\n\n".join(s for s in sections if s.strip())

    @staticmethod
    def _text(item: SessionItem) -> str:
        if isinstance(item, Message):
            return "".join(getattr(c, "text", "") for c in item.content)
        return ""

    def _render_history(self, items: list[SessionItem]) -> str:
        return "\n".join(
            f"{i.role}: {self._text(i)}"
            for i in items
            if isinstance(i, Message)
        )
