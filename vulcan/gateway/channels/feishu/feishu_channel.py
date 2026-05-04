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

from ....runtime.base_runtime import BaseRuntime
from ....utils.logger import get_logger
from ...gateway import Gateway
from ..base_channel import BaseChannel
from .card_session import CardSession
from .send_reaction import send_reaction
from .send_streaming_msg import send_streaming_msg
from .send_streaming_thinking import send_streaming_thinking
from .send_tool import send_tool_call, send_tool_result

logger = get_logger(__name__)


class FeishuChannel(BaseChannel):
    def __init__(
        self,
        name: str,
        gateway: "Gateway",
        default_runtime: "BaseRuntime",
        config: dict = {},
    ) -> None:
        super().__init__(
            name=name,
            gateway=gateway,
            default_runtime=default_runtime,
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

    def on_message(self, event: P2ImMessageReceiveV1) -> None:
        """Lark dispatches callbacks from inside its WS event loop. Schedule
        the async handler on the running loop instead of starting a new one."""
        asyncio.get_running_loop().create_task(self.handle_event(event))

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

        user_id = self.name
        session_id = message.chat_id
        message_id = message.message_id
        text = json.loads(message.content)["text"]
        logger.info(f"feishu recv: chat={session_id} msg_len={len(text)}")

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
            async for item in self.invoke_stream(
                user_id, session_id, user_message
            ):
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
        finally:
            await session.finish()

        logger.info(f"feishu reply done: chat={session_id}")
