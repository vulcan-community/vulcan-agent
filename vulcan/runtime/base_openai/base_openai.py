"""Base runtime for OpenAI-compatible Chat Completions endpoints.

Drives the model via the openai Python SDK with `stream=True` and yields
each text delta as a `Message` SessionItem. Subclass to:
  - override `build_messages` to inject custom prompt structure
  - override `invoke` to handle additional response surfaces (tool calls,
    reasoning, etc.) — the base only translates text deltas
"""

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
        """Convert the session transcript + active turn into ChatCompletion
        messages. The persona prompt (identity + soul + tool guidance) goes
        in as a single system message at the head."""
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

        for item in ctx.session.items:
            if not isinstance(item, Message):
                continue
            text = "".join(getattr(c, "text", "") for c in item.content)
            if item.role == "user":
                messages.append(
                    ChatCompletionUserMessageParam(role="user", content=text)
                )
            elif item.role == "assistant":
                messages.append(
                    ChatCompletionAssistantMessageParam(
                        role="assistant", content=text
                    )
                )
            elif item.role == "system":
                messages.append(
                    ChatCompletionSystemMessageParam(
                        role="system", content=text
                    )
                )

        return messages
