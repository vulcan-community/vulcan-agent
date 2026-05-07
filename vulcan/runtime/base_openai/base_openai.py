"""Base runtime for OpenAI-compatible Chat Completions endpoints.

Drives the model via the openai Python SDK with `stream=True` and yields
each text delta as a `Message` SessionItem. Subclass to:
  - override `build_messages` to inject custom prompt structure
  - override `invoke` to handle additional response surfaces (tool calls,
    reasoning, etc.) — the base only translates text deltas
"""

import json
import uuid
from typing import AsyncIterator

from openai import AsyncOpenAI
from openai.types.chat import (
    ChatCompletionAssistantMessageParam,
    ChatCompletionMessageParam,
    ChatCompletionSystemMessageParam,
    ChatCompletionUserMessageParam,
)
from openai.types.conversations.message import Message
from openai.types.responses.response_output_text import ResponseOutputText

from ...types.agent import AgentConfig
from ...types.invocation import InvocationContext
from ...types.session import SessionItem
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
        cfg = agent_config.model
        self.client = AsyncOpenAI(
            api_key=cfg.api_key or None,
            base_url=cfg.base_url or None,
        )

    async def invoke(
        self, ctx: InvocationContext
    ) -> AsyncIterator[SessionItem]:
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
            yield Message(
                id=str(uuid.uuid4()),
                type="message",
                role="assistant",
                status="completed",
                content=[
                    ResponseOutputText(
                        type="output_text",
                        text=text,
                        annotations=[],
                    )
                ],
            )

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

        i = self.agent_config.instruction
        system_text = "\n\n".join(
            s for s in (i.identity, i.soul, i.tool) if s.strip()
        )
        if system_text:
            messages.append(
                ChatCompletionSystemMessageParam(
                    role="system", content=system_text
                )
            )

        messages.extend(self._split_history(ctx.history_message))

        messages.append(
            ChatCompletionUserMessageParam(
                role="user", content=self._message_text(ctx.message)
            )
        )

        return messages

    @staticmethod
    def _split_history(
        history_message: Message,
    ) -> list[ChatCompletionMessageParam]:
        text = "".join(getattr(c, "text", "") for c in history_message.content)
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

    @staticmethod
    def _message_text(msg: Message) -> str:
        return "".join(getattr(c, "text", "") for c in msg.content)
