"""Base runtime for OpenAI-compatible Chat Completions endpoints.

Drives the model via the openai Python SDK with `stream=True` and yields
each text delta as a `Message` SessionItem. Subclass to:
  - override `build_messages` to inject custom prompt structure
  - override `invoke` to handle additional response surfaces (tool calls,
    reasoning, etc.) — the base only translates text deltas
"""

import json
from collections.abc import AsyncIterator

from openai import AsyncOpenAI
from openai.types.chat import (
    ChatCompletionAssistantMessageParam,
    ChatCompletionMessageParam,
    ChatCompletionSystemMessageParam,
    ChatCompletionUserMessageParam,
)
from openai.types.conversations.message import Message

from ...types.agent import AgentConfig
from ...types.invocation import InvocationContext
from ...types.session import SessionItem
from ...utils.messages import assistant_message, message_text
from ..base_runtime import BaseRuntime


class BaseOpenAIRuntime(BaseRuntime):
    def __init__(
        self,
        name: str,
        agent_config: AgentConfig,
        description: str = "",
    ) -> None:
        super().__init__(
            name=name, agent_config=agent_config, description=description
        )
        # AsyncOpenAI validates api_key eagerly at construction, so defer
        # it to first invoke() — otherwise registering base-openai without
        # credentials (e.g. when it's just being probed for status) would
        # crash.
        self._client: AsyncOpenAI | None = None

    def is_installed(self) -> bool:
        # `openai` is a core dependency of vulcan, so this runtime is
        # always available.
        return True

    @property
    def client(self) -> AsyncOpenAI:
        if self._client is None:
            cfg = self.agent_config.model
            self._client = AsyncOpenAI(
                api_key=cfg.api_key or None,
                base_url=cfg.base_url or None,
            )
        return self._client

    async def invoke(
        self, ctx: InvocationContext
    ) -> AsyncIterator[SessionItem]:
        provider = self.agent_config.model.provider
        if provider != "openai":
            raise ValueError(
                f"BaseOpenAIRuntime only supports provider='openai', but "
                f"runtime '{self.name}' is configured with "
                f"provider='{provider}'. Fix vulcan.json or use a "
                f"different runtime."
            )
        messages = self.build_messages(ctx)
        stream = await self.client.chat.completions.create(
            model=self.agent_config.model.name,
            messages=messages,
            stream=True,
        )
        async for chunk in stream:
            if not chunk.choices:
                continue
            text = chunk.choices[0].delta.content
            if not text:
                continue
            yield assistant_message(text)

    def build_messages(
        self, ctx: InvocationContext
    ) -> list[ChatCompletionMessageParam]:
        """Compose ChatCompletion messages: persona system prompt + replayed
        history (user/assistant turns parsed back out of the gateway's
        pre-rendered history message) + the current user input.

        The gateway hands us a single user-role Message whose text is
        `<previous_conversations>\\n<json>\\n<json>\\n...\\n
        </previous_conversations>` (raw JSONL of prior SessionItems). Chat
        Completions supports real multi-turn, so we split it back here and
        drop items that don't map to a chat role (tool calls, reasoning,
        etc. — this base runtime doesn't surface those).
        """
        messages: list[ChatCompletionMessageParam] = []

        system_text = self.agent_config.instruction.render()
        if system_text:
            messages.append(
                ChatCompletionSystemMessageParam(
                    role="system", content=system_text
                )
            )

        messages.extend(self._split_history(ctx.history_message))
        messages.append(
            ChatCompletionUserMessageParam(
                role="user", content=message_text(ctx.message)
            )
        )
        return messages

    @staticmethod
    def _split_history(
        history_message: Message,
    ) -> list[ChatCompletionMessageParam]:
        text = message_text(history_message)
        if not text:
            return []

        inner = text.removeprefix("<previous_conversations>\n").removesuffix(
            "\n</previous_conversations>"
        )

        out: list[ChatCompletionMessageParam] = []
        for line in inner.splitlines():
            line = line.strip()
            if not line:
                continue
            obj = json.loads(line)
            if obj.get("type") != "message":
                continue
            role = obj.get("role")
            content_text = "".join(
                c.get("text", "") for c in obj.get("content", [])
            )
            if role == "user":
                out.append(
                    ChatCompletionUserMessageParam(
                        role="user", content=content_text
                    )
                )
            elif role == "assistant":
                out.append(
                    ChatCompletionAssistantMessageParam(
                        role="assistant", content=content_text
                    )
                )
        return out
