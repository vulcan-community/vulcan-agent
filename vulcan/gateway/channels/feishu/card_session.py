"""Coordinator for a single Feishu card lifecycle.

A `CardSession` holds the card_id, the running element-id sequence, the
"open text element" pointer (so consecutive text chunks accumulate into
one markdown block), and the call_id → inner-element mapping for tool
panels. The send_*.py modules read/write this state to render specific
event types into the card.
"""

import json
import time

import lark_oapi as lark
from lark_oapi.api.cardkit.v1 import (
    ContentCardElementRequest,
    ContentCardElementRequestBody,
    CreateCardElementRequest,
    CreateCardElementRequestBody,
    CreateCardRequest,
    CreateCardRequestBody,
    SettingsCardRequest,
    SettingsCardRequestBody,
)
from lark_oapi.api.im.v1 import ReplyMessageRequest, ReplyMessageRequestBody

from ....utils.logger import get_logger

logger = get_logger(__name__)


def initial_card_schema() -> dict:
    return {
        "schema": "2.0",
        "config": {
            "streaming_mode": True,
            "summary": {"content": "Vulcan 回复中..."},
            "streaming_config": {
                "print_frequency_ms": {"default": 30},
                "print_step": {"default": 2},
                "print_strategy": "fast",
            },
        },
        "body": {"elements": []},
    }


class CardSession:
    """Live card state shared by all send_* helpers in this package."""

    def __init__(self, client: lark.Client, reply_to_message_id: str) -> None:
        self.client = client
        self.reply_to_message_id = reply_to_message_id
        self.card_id: str | None = None
        self.sequence: int = 1
        self.element_counter: int = 0
        # Most recently opened markdown element for streaming text. Cleared
        # whenever a non-text event lands so the next text chunk starts a
        # fresh element rather than appending to a stale one.
        self.open_text_id: str | None = None
        self.open_text_buf: str = ""
        # Running concat of every text chunk ever streamed into this card,
        # across text-element rotations. Used by `finish()` to set the
        # card summary once the stream ends — so the chat preview shows
        # the final reply instead of "Vulcan is replying...".
        self.full_text: str = ""
        # call_id → (inner_markdown_element_id, args_json) — used by
        # send_tool.send_tool_result to update the matching panel body.
        self.tool_state: dict[str, tuple[str, str]] = {}

    async def start(self) -> None:
        assert self.client.cardkit is not None
        assert self.client.im is not None

        create_req = (
            CreateCardRequest.builder()
            .request_body(
                CreateCardRequestBody.builder()
                .type("card_json")
                .data(json.dumps(initial_card_schema(), ensure_ascii=False))
                .build()
            )
            .build()
        )
        create_resp = await self.client.cardkit.v1.card.acreate(create_req)
        assert create_resp.data is not None
        assert create_resp.data.card_id is not None
        self.card_id = create_resp.data.card_id
        logger.info(f"cardkit card created: card_id={self.card_id}")

        reply_req = (
            ReplyMessageRequest.builder()
            .message_id(self.reply_to_message_id)
            .request_body(
                ReplyMessageRequestBody.builder()
                .msg_type("interactive")
                .content(
                    json.dumps(
                        {"type": "card", "data": {"card_id": self.card_id}}
                    )
                )
                .build()
            )
            .build()
        )
        await self.client.im.v1.message.areply(reply_req)

    async def finish(self) -> None:
        """Flip streaming mode off and replace the card summary so the
        chat preview shows the final reply instead of "Vulcan is
        replying...". Summary is derived from every text chunk streamed
        into this card; truncated to a single-line preview.
        """
        assert self.client.cardkit is not None
        assert self.card_id is not None

        summary = self._build_summary()
        req = (
            SettingsCardRequest.builder()
            .card_id(self.card_id)
            .request_body(
                SettingsCardRequestBody.builder()
                .uuid(f"{self.card_id}-finish-{int(time.time() * 1000)}")
                .settings(
                    json.dumps(
                        {
                            "config": {
                                "streaming_mode": False,
                                "summary": {"content": summary},
                            }
                        },
                        ensure_ascii=False,
                    )
                )
                .sequence(self.next_sequence())
                .build()
            )
            .build()
        )
        await self.client.cardkit.v1.card.asettings(req)
        logger.info(f"cardkit card finished: card_id={self.card_id}")

    def _build_summary(self, max_len: int = 80) -> str:
        """Turn accumulated `full_text` into a single-line preview."""
        text = self.full_text.strip()
        if not text:
            return "Vulcan replied."
        # Collapse whitespace (newlines + runs of spaces) so the chat
        # preview stays on one line.
        flat = " ".join(text.split())
        if len(flat) <= max_len:
            return flat
        return flat[: max_len - 1].rstrip() + "…"

    def next_sequence(self) -> int:
        seq = self.sequence
        self.sequence += 1
        return seq

    def new_id(self, prefix: str) -> str:
        self.element_counter += 1
        return f"{prefix}_{self.element_counter}"

    async def insert_element(self, element: dict) -> None:
        """Append a new element to the end of the card body."""
        assert self.client.cardkit is not None
        assert self.card_id is not None

        seq = self.next_sequence()
        req = (
            CreateCardElementRequest.builder()
            .card_id(self.card_id)
            .request_body(
                CreateCardElementRequestBody.builder()
                .type("append")
                .uuid(f"{self.card_id}-ins-{seq}")
                .sequence(seq)
                .elements(json.dumps([element], ensure_ascii=False))
                .build()
            )
            .build()
        )
        await self.client.cardkit.v1.card_element.acreate(req)

    async def set_content(self, element_id: str, content: str) -> None:
        """Replace the markdown content of an existing element."""
        assert self.client.cardkit is not None
        assert self.card_id is not None

        seq = self.next_sequence()
        req = (
            ContentCardElementRequest.builder()
            .card_id(self.card_id)
            .element_id(element_id)
            .request_body(
                ContentCardElementRequestBody.builder()
                .uuid(f"{self.card_id}-{element_id}-{seq}")
                .content(content)
                .sequence(seq)
                .build()
            )
            .build()
        )
        await self.client.cardkit.v1.card_element.acontent(req)
