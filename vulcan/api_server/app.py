import uuid
from typing import TYPE_CHECKING

from litellm.proxy.proxy_server import app
from openai.types.conversations.message import Message
from openai.types.responses.response_input_text import ResponseInputText
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from ..consts import GATEWAY_CHANNEL_ID
from ..utils.logger import get_logger

if TYPE_CHECKING:
    from ..gateway.gateway import Gateway

logger = get_logger(__name__)


class MessageMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, gateway: "Gateway") -> None:
        super().__init__(app)
        self.gateway = gateway

    async def dispatch(self, request, call_next):
        if request.url.path != "/v1/chat/completions":
            return await call_next(request)

        body = await request.json()
        channel_id = GATEWAY_CHANNEL_ID
        session_id = request.headers.get("x-session-id", "default")
        text = body["messages"][-1]["content"]
        # The request's `model` is the runtime name. Treat it as an
        # explicit rebind: persist to session meta first, then let the
        # gateway pick it up normally. An empty / missing `model` leaves
        # the existing binding (or the config default) untouched.
        runtime_name = body.get("model")
        if runtime_name:
            self.gateway.session_manager.set_session_runtime(
                channel_id, session_id, runtime_name
            )
        logger.info(
            f"chat: model={runtime_name} session={session_id} "
            f"user_msg_len={len(text)}"
        )

        user_message = Message(
            id=str(uuid.uuid4()),
            type="message",
            role="user",
            status="completed",
            content=[ResponseInputText(type="input_text", text=text)],
        )

        completion = await self.gateway.invoke(
            channel_id, session_id, user_message
        )
        return JSONResponse(completion.model_dump())


class VulcanAPIServer:
    def __init__(self, gateway: "Gateway") -> None:
        self.app = app
        self.gateway = gateway
        self.app.add_middleware(MessageMiddleware, gateway=self.gateway)
