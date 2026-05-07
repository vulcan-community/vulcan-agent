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
from ..base_runtime import BaseRuntime


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
