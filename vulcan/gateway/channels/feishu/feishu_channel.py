import asyncio
import json
import threading
import uuid

import lark_oapi as lark
from lark_oapi.api.im.v1 import P2ImMessageReceiveV1
from openai.types.conversations.message import Message
from openai.types.responses.response_function_tool_call_item import (
    ResponseFunctionToolCallItem,
)
from openai.types.responses.response_function_tool_call_output_item import (
    ResponseFunctionToolCallOutputItem,
)
from openai.types.responses.response_input_text import ResponseInputText
from openai.types.responses.response_reasoning_item import ResponseReasoningItem

from ....utils.logger import get_logger
from ...gateway import Gateway
from ..base_channel import BaseChannel
from .card_session import CardSession
from .send_reaction import send_reaction
from .send_streaming_msg import send_streaming_msg
from .send_streaming_thinking import send_streaming_thinking
from .send_tool import send_tool_call, send_tool_result

logger = get_logger(__name__)


def _log_task_exception(task: asyncio.Task) -> None:
    """asyncio.Task done-callback that surfaces any unretrieved exception
    to our logger. Without this, exceptions in tasks spawned by
    `create_task` are silently eaten until the task is garbage-collected,
    and even then show up only as "Task exception was never retrieved"
    in stderr — which is effectively invisible.
    """
    if task.cancelled():
        return
    exc = task.exception()
    if exc is not None:
        logger.error(
            "feishu handle_event task failed",
            exc_info=(type(exc), exc, exc.__traceback__),
        )


class FeishuChannel(BaseChannel):
    def __init__(
        self,
        name: str,
        gateway: "Gateway",
        config: dict = {},
    ) -> None:
        super().__init__(
            name=name,
            gateway=gateway,
            config=config,
        )
        self.app_id: str = config["app_id"]
        self.app_secret: str = config["app_secret"]
        self.client: lark.Client = (
            lark.Client.builder()
            .app_id(self.app_id)
            .app_secret(self.app_secret)
            .build()
        )
        logger.info(f"feishu channel '{self.name}' init, app_id={self.app_id}")

        dispatcher = (
            lark.EventDispatcherHandler.builder("", "")
            .register_p2_im_message_receive_v1(self.on_message)
            # Swallow reaction-echo events triggered by our own send_reaction.
            .register_p2_im_message_reaction_created_v1(lambda e: None)
            .register_p2_im_message_reaction_deleted_v1(lambda e: None)
            .build()
        )
        self.ws = lark.ws.Client(
            app_id=self.app_id,
            app_secret=self.app_secret,
            event_handler=dispatcher,
        )
        threading.Thread(target=self.ws.start, daemon=True).start()
        logger.info(f"feishu channel '{self.name}' listening")

    # Hard ceiling on a single runtime turn. If the SDK hangs (stuck
    # network I/O with no exception), this is what rescues the user from
    # an indefinitely-spinning card.
    INVOKE_TIMEOUT_SECONDS = 180

    def on_message(self, event: P2ImMessageReceiveV1) -> None:
        """Lark dispatches callbacks from inside its WS event loop. Schedule
        the async handler on the running loop instead of starting a new one.

        The done-callback is essential — without it, any uncaught exception
        in `handle_event` is silently eaten by the asyncio task machinery
        (and only logged on GC, which is effectively invisible).
        """
        task = asyncio.get_running_loop().create_task(self.handle_event(event))
        task.add_done_callback(_log_task_exception)

    async def handle_event(self, event: P2ImMessageReceiveV1) -> None:
        """One incoming Feishu message: react, drive the runtime via the
        gateway stream, and progressively render each event into a single
        Feishu Card (text / thinking / tool panels)."""
        assert event.event is not None
        assert event.event.message is not None
        message = event.event.message
        assert message.chat_id is not None
        assert message.message_id is not None
        assert message.content is not None

        conversation_id = message.chat_id
        message_id = message.message_id
        text = json.loads(message.content)["text"]
        logger.info(f"feishu recv: chat={conversation_id} msg_len={len(text)}")

        # 1. acknowledge with reaction
        send_reaction(self.client, message_id)

        # 2. build user message
        user_message = Message(
            id=str(uuid.uuid4()),
            type="message",
            role="user",
            status="completed",
            content=[ResponseInputText(type="input_text", text=text)],
        )

        # 3. start a streaming card and dispatch each yielded SessionItem
        session = CardSession(self.client, message_id)
        await session.start()
        try:
            try:
                async with asyncio.timeout(self.INVOKE_TIMEOUT_SECONDS):
                    async for item in self.invoke_stream(
                        conversation_id, user_message
                    ):
                        await self._render_item(session, item)
            except TimeoutError:
                logger.warning(
                    f"feishu invoke timeout ({self.INVOKE_TIMEOUT_SECONDS}s):"
                    f" chat={conversation_id}"
                )
                await self._render_error(
                    session,
                    f"Runtime timed out after "
                    f"{self.INVOKE_TIMEOUT_SECONDS}s — no response.",
                )
            except Exception as e:
                logger.exception(
                    f"feishu invoke_stream error: chat={conversation_id}"
                )
                await self._render_error(session, f"{type(e).__name__}: {e}")
        finally:
            await session.finish()

        logger.info(f"feishu reply done: chat={conversation_id}")

    async def _render_item(self, session: CardSession, item) -> None:
        if isinstance(item, Message) and item.role == "assistant":
            for c in item.content:
                chunk = getattr(c, "text", "")
                await send_streaming_msg(session, chunk)
        elif isinstance(item, ResponseReasoningItem):
            if item.content is not None:
                for rc in item.content:
                    await send_streaming_thinking(session, rc.text)
        elif isinstance(item, ResponseFunctionToolCallItem):
            await send_tool_call(
                session, item.call_id, item.name, item.arguments
            )
        elif isinstance(item, ResponseFunctionToolCallOutputItem):
            if isinstance(item.output, str):
                output_text = item.output
            else:
                output_text = json.dumps(
                    [c.model_dump() for c in item.output],
                    ensure_ascii=False,
                )
            await send_tool_result(
                session,
                item.call_id,
                output_text,
                is_error=item.status == "incomplete",
            )

    async def _render_error(self, session: CardSession, detail: str) -> None:
        """Best-effort error surface onto the open card so users see
        something — swallows nested failures so `finish()` still runs."""
        try:
            await send_streaming_msg(session, f"\n\n**Error:** {detail}")
        except Exception:
            logger.exception("failed to render error onto feishu card")
